"""Bounded static validation. No extraction, conversion, or network requests."""
import codecs
import re
import shutil
import stat
import struct
import subprocess
import tempfile
import zipfile
import zlib
from html.parser import HTMLParser
from pathlib import PurePosixPath
from xml.parsers import expat

from src.corpus_factory.inspection.result import CheckResult, InspectionDecision as D

CHUNK = 64 * 1024
ZIP_FORMATS = {
    '.docx': ('word/document.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
    '.xlsx': ('xl/workbook.xml', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    '.pptx': ('ppt/presentation.xml', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'),
    '.odt': ('content.xml', 'application/vnd.oasis.opendocument.text'),
    '.ods': ('content.xml', 'application/vnd.oasis.opendocument.spreadsheet'),
    '.epub': ('META-INF/container.xml', 'application/epub+zip'),
}
DEEP_EXTENSIONS = set(ZIP_FORMATS) | {'.pdf', '.doc', '.rtf', '.xml', '.html', '.htm'}


class UnsafeContent(ValueError):
    """Definite policy violation, rather than uncertain/corrupt content."""


def bounded_zip(stream, policy):
    """Bound the central directory before ZipFile allocates member objects."""
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(max(0, size - 65557))
    tail = stream.read(65557)
    index = tail.rfind(b'PK\x05\x06')
    if index < 0 or len(tail) - index < 22:
        raise ValueError('ZIP end record missing')
    _, disk, start_disk, count_disk, count, directory_bytes, offset, comment = struct.unpack_from('<4s4H2LH', tail, index)
    if disk or start_disk or count != count_disk or count == 65535 or offset == 0xffffffff:
        raise ValueError('multi-volume/ZIP64 container validation unavailable')
    if count > policy['max_archive_files'] or directory_bytes > policy['max_structured_bytes']:
        raise UnsafeContent('archive directory exceeds resource limits')
    if index + 22 + comment != len(tail) or offset + directory_bytes > size:
        raise ValueError('invalid ZIP end record')
    stream.seek(0)
    archive = zipfile.ZipFile(stream)
    if len(archive.infolist()) != count:
        archive.close()
        raise ValueError('inconsistent archive entry count')
    return archive


def inspect_xml(stream, policy, relationships=False):
    """Expat handlers reject declarations before entity expansion; no tree retained."""
    parser = expat.ParserCreate(namespace_separator='}')
    depth = 0
    root = None

    def forbidden(*args):
        raise UnsafeContent('XML DTD/entity declarations are forbidden')

    def start(name, attrs):
        nonlocal depth, root
        depth += 1
        if root is None:
            root = name.rsplit('}', 1)[-1]
        if depth > policy['max_xml_depth']:
            raise UnsafeContent('XML nesting limit exceeded')
        if relationships and name.rsplit('}', 1)[-1] == 'Relationship':
            target = attrs.get('Target', '').strip()
            if (attrs.get('TargetMode', '').lower() == 'external'
                    or re.match(r'^(?:[a-zA-Z][\w+.-]*:|//|\\)', target)):
                raise UnsafeContent('external Office relationship')

    def end(name):
        nonlocal depth
        depth -= 1

    parser.StartDoctypeDeclHandler = forbidden
    parser.EntityDeclHandler = forbidden
    parser.ExternalEntityRefHandler = forbidden
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    total = 0
    while chunk := stream.read(CHUNK):
        total += len(chunk)
        if total > policy['max_structured_bytes']:
            raise ValueError('XML exceeds bounded structural validation limit')
        parser.Parse(chunk, False)
    parser.Parse(b'', True)
    return root


def _inspect_zip(stream, suffix, policy):
    with bounded_zip(stream, policy) as archive:
        entries = archive.infolist()
        names = set()
        total = 0
        for entry in entries:
            name = entry.filename
            parts = PurePosixPath(name).parts
            if ('\\' in name or name.startswith('/') or '..' in parts
                    or ':' in name or '\x00' in entry.orig_filename):
                raise UnsafeContent('unsafe archive member path')
            if name.casefold() in names:
                raise ValueError('duplicate archive member name')
            names.add(name.casefold())
            mode = entry.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise UnsafeContent('archive symlink or special file')
            if entry.flag_bits & 1:
                raise UnsafeContent('encrypted archive member')
            total += entry.file_size
            if (entry.file_size > policy['max_archive_member_bytes']
                    or total > policy['max_uncompressed_bytes']
                    or entry.file_size / max(1, entry.compress_size) > policy['max_compression_ratio']):
                raise UnsafeContent('archive expansion limit exceeded')
            lower = name.lower()
            if (PurePosixPath(lower).suffix in policy['blocked_extensions']
                    or 'vbaproject.bin' in lower or 'embeddings' in lower.split('/')):
                raise UnsafeContent('archive contains executable, macro, or embedded content')
        required, mime = ZIP_FORMATS[suffix]
        if required not in archive.namelist():
            raise ValueError(f'required container member missing: {required}')
        if suffix in {'.docx', '.xlsx', '.pptx'}:
            if '[Content_Types].xml' not in archive.namelist() or '_rels/.rels' not in archive.namelist():
                raise ValueError('Office package metadata missing')
        else:
            if archive.getinfo('mimetype').file_size > 255 or archive.read('mimetype') != mime.encode('ascii'):
                raise ValueError('container mimetype mismatch')
        # Read all members to EOF to validate CRC and decompression, including non-XML.
        for entry in entries:
            if entry.is_dir():
                continue
            with archive.open(entry) as member:
                if entry.filename.lower().endswith(('.xml', '.rels')):
                    root = inspect_xml(member, policy, relationships=entry.filename.endswith('.rels'))
                    expected_root = {'.docx': 'document', '.xlsx': 'workbook', '.pptx': 'presentation',
                                     '.odt': 'document-content', '.ods': 'document-content', '.epub': 'container'}
                    if entry.filename == required and root != expected_root[suffix]:
                        raise ValueError('unexpected document XML root')
                else:
                    seen = 0
                    while chunk := member.read(CHUNK):
                        seen += len(chunk)
                        if seen > policy['max_archive_member_bytes']:
                            raise UnsafeContent('expanded member exceeds limit')


class _HTMLInspection(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'iframe', 'object', 'embed', 'applet', 'base'}:
            raise UnsafeContent(f'active HTML element: {tag}')
        for name, value in attrs:
            compact = re.sub(r'\s+', '', value or '').lower()
            if name.startswith('on') or name == 'srcdoc' or compact.startswith(('javascript:', 'vbscript:', 'data:')):
                raise UnsafeContent('active HTML attribute')
        if tag == 'meta' and any(k == 'http-equiv' and (v or '').lower() == 'refresh' for k, v in attrs):
            raise UnsafeContent('HTML redirect')


def _inspect_html(stream, encoding, policy):
    parser = _HTMLInspection(convert_charrefs=True)
    decoder = codecs.getincrementaldecoder(encoding or 'utf-8-sig')()
    while chunk := stream.read(CHUNK):
        parser.feed(decoder.decode(chunk))
        if len(parser.rawdata) > policy['max_line_characters']:
            raise ValueError('HTML token exceeds structural limit')
    parser.feed(decoder.decode(b'', final=True))
    parser.close()


def _inspect_pdf(stream, policy):
    if stream.read(5) != b'%PDF-':
        raise ValueError('PDF signature missing')
    stream.seek(0)
    tail = b''
    active = re.compile(rb'/(?:JavaScript|JS|Launch|EmbeddedFile|OpenAction|AA)(?=[\s()<>\[\]{}/%])')
    while chunk := stream.read(CHUNK):
        data = tail + chunk
        decoded = re.sub(rb'#([0-9a-fA-F]{2})', lambda m: bytes([int(m[1], 16)]), data)
        if active.search(decoded):
            raise UnsafeContent('PDF active-content marker')
        tail = data[-1024:]
    decoded_tail = re.sub(rb'#([0-9a-fA-F]{2})', lambda m: bytes([int(m[1], 16)]), tail)
    if active.search(decoded_tail + b' '):
        raise UnsafeContent('PDF active-content marker')
    if b'%%EOF' not in tail or b'startxref' not in tail:
        raise ValueError('PDF trailer missing')
    validator = shutil.which('pdfinfo')
    if validator is None:
        if policy['require_deep_container_inspection']:
            raise ValueError('pdfinfo unavailable; PDF structure not validated')
        return ('pdf_validator_unavailable',)
    # Validators receive a private snapshot, never a mutable incoming pathname.
    with tempfile.TemporaryDirectory(prefix='jsm-pdf-') as directory:
        from pathlib import Path
        snapshot = Path(directory) / 'document.pdf'
        stream.seek(0)
        with snapshot.open('wb') as output:
            shutil.copyfileobj(stream, output, CHUNK)
        result = subprocess.run([validator, str(snapshot)], capture_output=True,
                                timeout=policy['pdf_timeout_seconds'], check=False)
        if result.returncode:
            raise ValueError('pdfinfo rejected PDF: ' + result.stderr[:500].decode('utf-8', 'replace'))
        if re.search(rb'^Encrypted:\s+yes', result.stdout, re.MULTILINE):
            raise UnsafeContent('encrypted PDF')
    return ()


def _inspect_rtf(stream):
    if not stream.read(5).lower().startswith(b'{\\rtf'):
        raise ValueError('RTF signature missing')
    stream.seek(0)
    depth = 0
    escaped = False
    tail = b''
    while chunk := stream.read(CHUNK):
        data = tail + chunk
        if re.search(rb'\\(?:object|objdata|field|bin)\b', data, re.IGNORECASE):
            raise UnsafeContent('RTF embedded/active/binary content')
        tail = data[-64:]
        for byte in chunk:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 123:
                depth += 1
            elif byte == 125:
                depth -= 1
                if depth < 0:
                    raise ValueError('unbalanced RTF braces')
    if depth or escaped:
        raise ValueError('unbalanced RTF structure')


def inspect_deep_container(stream, suffix, policy, encoding=None):
    flags = ()
    try:
        stream.seek(0)
        if suffix in ZIP_FORMATS:
            _inspect_zip(stream, suffix, policy)
        elif suffix == '.pdf':
            flags = _inspect_pdf(stream, policy)
        elif suffix == '.xml':
            inspect_xml(stream, policy)
        elif suffix in {'.html', '.htm'}:
            _inspect_html(stream, encoding, policy)
        elif suffix == '.rtf':
            _inspect_rtf(stream)
        elif suffix == '.doc':
            raise ValueError('legacy DOC: safe cross-platform validator unavailable')
        return CheckResult('deep_inspection'), flags
    except UnsafeContent as error:
        return CheckResult('deep_inspection', D.REJECTED, (str(error),)), flags
    except (OSError, ValueError, KeyError, RuntimeError, EOFError, NotImplementedError,
            zipfile.BadZipFile, zlib.error, expat.ExpatError, subprocess.TimeoutExpired) as error:
        return CheckResult('deep_inspection', D.QUARANTINED, (str(error),)), flags
