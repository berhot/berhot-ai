"""Filesystem, content, integrity, and chunked malware checks."""
import codecs
import errno
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
import zlib
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path, PurePosixPath

from src.corpus_factory.inspection.deep_inspection import (
    CHUNK, DEEP_EXTENSIONS, ZIP_FORMATS, UnsafeContent, bounded_zip,
    inspect_deep_container,
)
from src.corpus_factory.inspection.result import (
    ArtifactInspectionResult, CheckResult, InspectionDecision as D,
    MalwareScanResult, MalwareScanStatus as M, more_restrictive_decision,
)

TEXT_EXTENSIONS = {'.txt', '.text', '.md', '.markdown', '.csv', '.tsv', '.json',
                   '.jsonl', '.ndjson', '.html', '.htm', '.xml', '.yaml', '.yml', '.log'}


@contextmanager
def _windows_regular(path):
    """Open reparse points themselves; retain parents without delete sharing."""
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    information = kernel.GetFileInformationByHandle
    information.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
    information.restype = wintypes.BOOL
    parents = []
    leaf = None
    try:
        for component in (*reversed(path.parents), path):
            is_leaf = component == path
            # OPEN_EXISTING, BACKUP_SEMANTICS | OPEN_REPARSE_POINT.
            handle = create(str(component), 0x80000000 if is_leaf else 0,
                            1 if is_leaf else 3, None, 3, 0x02200000, None)
            if handle == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            if is_leaf:
                leaf = handle
            else:
                parents.append(handle)
            # BY_HANDLE_FILE_INFORMATION is thirteen DWORDs; attributes first.
            metadata = (wintypes.DWORD * 13)()
            if not information(handle, ctypes.byref(metadata)):
                raise ctypes.WinError(ctypes.get_last_error())
            if metadata[0] & 0x400:
                raise UnsafeContent('symlink/reparse point in artifact path')
            if not is_leaf and not metadata[0] & 0x10:
                raise UnsafeContent('non-directory parent in artifact path')
        descriptor = msvcrt.open_osfhandle(leaf, os.O_RDONLY | os.O_BINARY)
        leaf = None  # Ownership transferred to the CRT descriptor.
        with os.fdopen(descriptor, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise UnsafeContent('not a regular file')
            yield stream
    finally:
        if leaf is not None:
            close(leaf)
        for handle in reversed(parents):
            close(handle)


@contextmanager
def open_regular(path):
    """Reject links at every component; pin parent directories on POSIX."""
    path = Path(path).absolute()
    if os.name == 'nt':
        with _windows_regular(path) as stream:
            yield stream
        return
    descriptor = None
    parent = None
    try:
        if os.open in os.supports_dir_fd and hasattr(os, 'O_NOFOLLOW'):
            parent = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
            for part in path.parts[1:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                os.close(parent)
                parent = child
            descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        else:
            raise OSError('safe no-follow file opening unavailable on this platform')
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError('not a regular file')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            yield stream
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent is not None:
            os.close(parent)


def safe_artifact_path(batch_dir, relative):
    parts = PurePosixPath(relative).parts
    if (len(parts) != 2 or parts[0] != 'objects' or parts[1] in {'.', '..'}
            or '\\' in relative or ':' in relative or any(ord(c) < 32 for c in relative)
            or relative != '/'.join(parts)):
        raise UnsafeContent('unsafe stored_relative_path; expected objects/<filename>')
    return batch_dir / relative


def stream_hash(stream, max_bytes, destination=None):
    stream.seek(0)
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(CHUNK):
        size += len(chunk)
        if size > max_bytes:
            raise OSError('artifact grew during inspection')
        digest.update(chunk)
        if destination is not None:
            destination.write(chunk)
    return digest.hexdigest()


def read_manifest(batch_dir, policy):
    with open_regular(batch_dir / 'source.json') as stream:
        if os.fstat(stream.fileno()).st_size > policy['max_manifest_bytes']:
            raise ValueError('source.json exceeds manifest size limit')
        data = stream.read(policy['max_manifest_bytes'] + 1)
        if len(data) > policy['max_manifest_bytes']:
            raise ValueError('source.json exceeds manifest size limit')
    actual_hash = hashlib.sha256(data).hexdigest()
    with open_regular(batch_dir / 'source.json.sha256') as stream:
        expected_hash = stream.read(1024).decode('ascii').strip()
    if expected_hash != actual_hash:
        raise ValueError('source.json.sha256 mismatch')
    manifest = json.loads(data)
    if not isinstance(manifest, dict):
        raise ValueError('source.json must contain a JSON object')
    if manifest.get('batch_id') != batch_dir.name:
        raise ValueError('source.json batch_id does not match directory name')
    if manifest.get('schema_version') != '1.0.0' or manifest.get('record_type') != 'incoming_source_batch':
        raise ValueError('unsupported source manifest schema or record_type')
    if not isinstance(manifest.get('source'), dict) or not isinstance(manifest.get('license'), dict):
        raise ValueError('source and license must be objects')
    artifacts = manifest.get('artifacts')
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError('artifacts must be a nonempty list')
    ids, paths = set(), set()
    for item in artifacts:
        if not isinstance(item, dict):
            raise ValueError('each artifact must be an object')
        for key in ('artifact_id', 'original_filename', 'stored_relative_path', 'sha256'):
            if not isinstance(item.get(key), str) or not item[key]:
                raise ValueError(f'artifact {key} must be a nonempty string')
        if not re.fullmatch(r'[a-f0-9]{64}', item['sha256']):
            raise ValueError('artifact sha256 must contain 64 lowercase hex characters')
        if type(item.get('size_bytes')) is not int or item['size_bytes'] < 0:
            raise ValueError('artifact size_bytes must be a nonnegative integer')
        if item['artifact_id'] in ids or item['stored_relative_path'] in paths:
            raise ValueError('duplicate artifact ID or stored path in manifest')
        ids.add(item['artifact_id'])
        paths.add(item['stored_relative_path'])
    return manifest, actual_hash


def detect_encoding(prefix):
    if prefix.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        raise UnicodeError('UTF-32 is not supported')
    if prefix.startswith(codecs.BOM_UTF8):
        return 'utf-8-sig'
    if prefix.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return 'utf-16'
    return 'utf-8'


def _detect_mime(stream, policy):
    stream.seek(0)
    prefix = stream.read(8192)
    if prefix.startswith(b'MZ'):
        return 'application/x-dosexec', 'builtin-signature'
    if prefix.startswith(b'\x7fELF'):
        return 'application/x-elf', 'builtin-signature'
    if prefix[:4] in (b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe'):
        return 'application/x-mach-binary', 'builtin-signature'
    if prefix.startswith(b'#!'):
        return 'text/x-shellscript', 'builtin-signature'
    if prefix.startswith(b'%PDF-'):
        return 'application/pdf', 'builtin-signature'
    if prefix.lower().startswith(b'{\\rtf'):
        return 'application/rtf', 'builtin-signature'
    if prefix.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
        return 'application/x-ole-storage', 'builtin-signature'
    if prefix.startswith(b'PK'):
        with bounded_zip(stream, policy) as archive:
            names = archive.namelist()
            for required, mime in ZIP_FORMATS.values():
                if required in names:
                    if required == 'content.xml':
                        if 'mimetype' in names and archive.getinfo('mimetype').file_size < 256:
                            return archive.read('mimetype').decode('ascii'), 'builtin-container'
                        return 'application/zip', 'builtin-container'
                    return mime, 'builtin-container'
        return 'application/zip', 'builtin-container'
    try:
        text = codecs.getincrementaldecoder(detect_encoding(prefix))().decode(prefix, final=False)
        if any(ord(c) < 32 and c not in '\t\r\n\f' for c in text):
            raise UnicodeError('binary control bytes')
        stripped = text.lstrip().lower()
        if stripped.startswith(('<!doctype html', '<html', '<head', '<body')):
            return 'text/html', 'builtin-text'
        if stripped.startswith('<'):
            return 'application/xml', 'builtin-text'
        return 'text/plain', 'builtin-text'
    except UnicodeError:
        # Optional libmagic only supplements unknown binary signatures.
        try:
            import magic
            return magic.from_buffer(prefix, mime=True).lower(), 'libmagic'
        except (ImportError, AttributeError, OSError, RuntimeError):
            return None, 'unavailable'


def detect_mime_type(path, policy):
    with open_regular(path) as stream:
        return _detect_mime(stream, policy)[0]


def inspect_text(stream, encoding, policy):
    stream.seek(0)
    decoder = codecs.getincrementaldecoder(encoding)(errors='strict')
    characters = lines = longest = current = 0
    previous_cr = False
    while True:
        chunk = stream.read(CHUNK)
        text = decoder.decode(chunk, final=not chunk)
        characters += len(text)
        if any(ord(c) < 32 and c not in '\t\r\n\f' for c in text):
            raise ValueError('binary control characters in text')
        if previous_cr and text.startswith('\n'):
            text = text[1:]
        if text:
            previous_cr = text.endswith('\r')
            parts = re.split(r'\r\n|\r|\n', text)
            current += len(parts[0])
            longest = max(longest, current)
            if len(parts) > 1:
                lines += len(parts) - 1
                longest = max(longest, *(len(part) for part in parts[1:]))
                current = len(parts[-1])
        if not chunk:
            break
    return characters, lines + bool(current), longest


def _inspect_json(stream, suffix, encoding, size, policy):
    stream.seek(0)
    wrapper = io.TextIOWrapper(stream, encoding=encoding, errors='strict')
    def invalid_constant(value):
        raise ValueError(f'nonstandard JSON constant: {value}')
    try:
        if suffix == '.json':
            if size > policy['max_structured_bytes']:
                raise ValueError('JSON exceeds bounded structural validation limit')
            json.loads(wrapper.read(policy['max_structured_bytes'] + 1), parse_constant=invalid_constant)
        else:
            for line in wrapper:
                if line.strip():
                    json.loads(line, parse_constant=invalid_constant)
    finally:
        wrapper.detach()


def add_check(result, check, **evidence):
    return replace(result, decision=more_restrictive_decision(result.decision, check.decision),
                   checks=result.checks + (check,), **evidence)


def inspect_artifact(batch_dir, artifact, policy, remaining_bytes, within_count=True):
    result = ArtifactInspectionResult(artifact['artifact_id'], artifact['original_filename'], artifact['stored_relative_path'])
    try:
        path = safe_artifact_path(batch_dir, artifact['stored_relative_path'])
        for component in (*reversed(path.absolute().parents), path):
            metadata = component.lstat()
            if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400:
                return add_check(result, CheckResult('filesystem', D.REJECTED, ('symlink/reparse point in artifact path',)), is_symlink=True)
        info = path.lstat()
        result = replace(result, size_bytes=info.st_size, is_symlink=stat.S_ISLNK(info.st_mode),
                         is_regular_file=stat.S_ISREG(info.st_mode))
        if result.is_symlink or not result.is_regular_file:
            return add_check(result, CheckResult('filesystem', D.REJECTED, ('symlink or non-regular file',)))
        if not within_count or info.st_size > policy['max_file_size_bytes'] or info.st_size > remaining_bytes:
            return add_check(result, CheckResult('limits', D.REJECTED, ('file or remaining batch resource limit exceeded',)))
        suffix = Path(result.filename).suffix.lower()
        stored_suffix = path.suffix.lower()
        if suffix in policy['blocked_extensions'] or stored_suffix in policy['blocked_extensions']:
            return add_check(result, CheckResult('extension', D.REJECTED, ('blocked extension',)))
        if suffix != stored_suffix:
            result = add_check(result, CheckResult('extension', D.QUARANTINED, ('stored/original extension mismatch',)))
        if suffix not in policy['allowed_extensions']:
            decision = D.REJECTED if policy['unknown_file_policy'] == 'reject' else D.QUARANTINED
            result = add_check(result, CheckResult('extension', decision, ('unsupported extension',)))
        elif suffix not in TEXT_EXTENSIONS | DEEP_EXTENSIONS:
            result = add_check(result, CheckResult('extension', D.QUARANTINED, ('inspection handler unavailable',)))
        with open_regular(path) as source, tempfile.TemporaryFile() as stream:
            before = os.fstat(source.fileno())
            if (before.st_size, before.st_dev, before.st_ino) != (info.st_size, info.st_dev, info.st_ino):
                raise OSError('artifact changed while opening')
            result = add_check(result, CheckResult('filesystem'))
            if not info.st_size:
                return add_check(result, CheckResult('limits', D.QUARANTINED, ('empty file',)))
            # All content checks share the exact private snapshot that was hashed.
            result = replace(result, sha256=stream_hash(source, info.st_size, stream))
            integrity = ()
            if result.sha256 != artifact['sha256']:
                integrity += ('artifact sha256 mismatch',)
            if info.st_size != artifact['size_bytes']:
                integrity += ('artifact size mismatch',)
            result = add_check(result, CheckResult('integrity', D.QUARANTINED if integrity else D.ACCEPTED, integrity))
            mime, method = _detect_mime(stream, policy)
            result = replace(result, detected_mime_type=mime, mime_detection_method=method)
            if mime in policy['blocked_mime_types']:
                return add_check(result, CheckResult('mime', D.REJECTED, ('blocked executable MIME type',)))
            mismatch = mime not in policy['expected_mime_types'].get(suffix, ())
            result = add_check(result, CheckResult('mime', D.QUARANTINED if mismatch else D.ACCEPTED,
                               ('content MIME unavailable or inconsistent with extension',) if mismatch else ()))
            if suffix in TEXT_EXTENSIONS:
                stream.seek(0)
                encoding = detect_encoding(stream.read(4))
                result = replace(result, encoding=encoding)
                chars, lines, longest = inspect_text(stream, encoding, policy)
                result = replace(result, character_count=chars, line_count=lines, max_line_characters=longest)
                extreme = longest > policy['max_line_characters']
                result = add_check(result, CheckResult('text', D.QUARANTINED if extreme else D.ACCEPTED,
                                   ('maximum line length exceeded',) if extreme else ()))
                if suffix in {'.json', '.jsonl', '.ndjson'} and not extreme:
                    _inspect_json(stream, suffix, encoding, info.st_size, policy)
                    result = add_check(result, CheckResult('json_structure'))
            if suffix in DEEP_EXTENSIONS:
                check, flags = inspect_deep_container(stream, suffix, policy, result.encoding)
                result = add_check(result, check, flags=result.flags + flags)
            after = os.fstat(source.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise OSError('artifact changed during inspection')
        return result
    except UnsafeContent as error:
        return add_check(result, CheckResult('content', D.REJECTED, (str(error),)))
    except OSError as error:
        decision = D.REJECTED if error.errno in (errno.ELOOP, errno.ENOTDIR) else D.QUARANTINED
        return add_check(result, CheckResult('filesystem', decision, (str(error),)))
    except (ValueError, UnicodeError, RecursionError, RuntimeError, zipfile.BadZipFile, zlib.error) as error:
        return add_check(result, CheckResult('content_or_filesystem', D.QUARANTINED, (str(error),)))


def _scan_snapshots(paths, policy):
    engines = [engine for name in ('clamdscan', 'clamscan') if (engine := shutil.which(name))]
    if not engines:
        return {path: MalwareScanResult(M.UNAVAILABLE, error='clamdscan and clamscan unavailable') for path in paths}
    results = {}
    for engine in engines:
        pending = [path for path in paths if path not in results or results[path].status == M.ERROR]
        if not pending:
            break
        try:
            proc = subprocess.run([engine, '--no-summary', '--', *map(str, pending)], capture_output=True,
                                  text=True, errors='replace', timeout=policy['malware_timeout_seconds'], check=False)
            output = (proc.stdout + '\n' + proc.stderr).splitlines()
            for path in pending:
                verdicts = [line[len(str(path)) + 2:] for line in output if line.startswith(str(path) + ': ')]
                infected = [v[:-6] for v in verdicts if v.endswith(' FOUND')]
                if infected:
                    results[path] = MalwareScanResult(M.INFECTED, engine, infected[0])
                elif proc.returncode in (0, 1) and verdicts == ['OK']:
                    results[path] = MalwareScanResult(M.CLEAN, engine)
                else:
                    error = '; '.join(verdicts) or (proc.stderr.strip()[:500] or 'no per-file verdict')
                    results[path] = MalwareScanResult(M.ERROR, engine, error=f'exit {proc.returncode}: {error}')
        except (OSError, subprocess.TimeoutExpired) as error:
            for path in pending:
                results[path] = MalwareScanResult(M.ERROR, engine, error=str(error))
    return results


def scan_malware_batch(batch_dir, artifacts, policy):
    """Stage bounded, hash-verified snapshots so scanners cannot follow source links."""
    results = {}
    candidates = [a for a in artifacts if a.sha256 and a.decision != D.REJECTED]
    def chunks():
        chunk, size = [], 0
        for artifact in candidates:
            if chunk and (len(chunk) >= policy['malware_chunk_size']
                          or size + artifact.size_bytes > policy['max_malware_chunk_bytes']):
                yield chunk
                chunk, size = [], 0
            chunk.append(artifact)
            size += artifact.size_bytes
        if chunk:
            yield chunk

    for chunk in chunks():
        with tempfile.TemporaryDirectory(prefix='jsm-malware-') as directory:
            targets = {}
            for index, artifact in enumerate(chunk):
                snapshot = Path(directory).resolve() / f'{index:06d}{Path(artifact.filename).suffix.lower()}'
                try:
                    path = safe_artifact_path(batch_dir, artifact.stored_relative_path)
                    with open_regular(path) as source, snapshot.open('xb') as output:
                        digest = hashlib.sha256()
                        size = 0
                        while data := source.read(CHUNK):
                            size += len(data)
                            if size > artifact.size_bytes:
                                raise OSError('artifact changed before malware scan')
                            output.write(data)
                            digest.update(data)
                    if digest.hexdigest() != artifact.sha256:
                        raise OSError('artifact changed before malware scan')
                    targets[snapshot] = artifact.artifact_id
                except (OSError, ValueError) as error:
                    results[artifact.artifact_id] = MalwareScanResult(M.ERROR, error=str(error))
            for path, verdict in _scan_snapshots(list(targets), policy).items():
                results[targets[path]] = verdict
    return results


def apply_malware_result(artifact, malware, policy):
    decision = D.ACCEPTED
    if malware.status == M.INFECTED:
        decision = D.REJECTED
    elif malware.status != M.CLEAN and policy['require_malware_scan']:
        decision = D.QUARANTINED
    errors = (malware.error or malware.signature or malware.status.value,) if decision != D.ACCEPTED else ()
    return add_check(artifact, CheckResult('malware', decision, errors),
                     malware_scan_status=malware.status, malware_engine=malware.engine,
                     malware_signature=malware.signature, malware_error=malware.error)
