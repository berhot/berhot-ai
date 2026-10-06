"""Append-only, atomic publication of checksummed inspection records."""
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from paths import STORAGE_DIR, QUARANTINE_DIR
from src.corpus_factory.inspection.result import InspectionResult

INSPECTOR_VERSION = '2.0.0'
INSPECTIONS_DIR = STORAGE_DIR / 'catalog' / 'inspections'


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def publish_record(root: Path, record_id: str, filename: str, record: dict) -> Path:
    """Publish both files together; historical nonempty directories cannot be replaced."""
    root.mkdir(parents=True, exist_ok=True)
    destination = root / record_id
    if destination.exists():
        raise FileExistsError(destination)
    temporary = Path(tempfile.mkdtemp(prefix='.pending-', dir=root))
    try:
        data = (json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        for name, payload in ((filename, data), (filename + '.sha256', (hashlib.sha256(data).hexdigest() + '\n').encode('ascii'))):
            with (temporary / name).open('xb') as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
        os.rename(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return destination / filename


def write_inspection_report(batch_dir: Path, result: InspectionResult,
                            catalog_dir: Path = INSPECTIONS_DIR) -> Path:
    inspection_id = 'inspection_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_' + uuid4().hex
    artifacts = [{**asdict(a), 'errors': list(a.errors)} for a in result.artifacts]
    record = {
        'schema_version': '2.0.0', 'record_type': 'inspection_report',
        'inspection_id': inspection_id, 'inspector_version': INSPECTOR_VERSION,
        'created_at': utc_now(), 'batch_id': result.batch_id,
        'incoming_batch': str(Path(batch_dir).absolute()),
        'source_manifest_sha256': result.source_manifest_sha256,
        'batch_status': 'valid' if result.batch_valid else 'quarantined',
        'policy': result.policy, 'summary': result.summary,
        'checks': [asdict(c) for c in result.checks], 'errors': list(result.errors),
        'artifacts': artifacts, 'duplicate_groups': result.duplicate_groups,
        'next_stage': 'ingestion' if result.batch_valid and result.summary['accepted'] else 'quarantine',
        'eligible_artifact_ids': [a.artifact_id for a in result.artifacts if a.decision.value == 'accepted_for_ingestion'],
    }
    return publish_record(catalog_dir, inspection_id, 'manifest.json', record)


def completed_batches(policy, catalog_dir: Path = INSPECTIONS_DIR,
                      quarantine_dir: Path = QUARANTINE_DIR):
    """Legacy batch-local reports never satisfy the current inspection contract."""
    completed = set()
    for path in catalog_dir.glob('inspection_*/manifest.json'):
        try:
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != path.with_suffix('.json.sha256').read_text().strip():
                continue
            record = json.loads(data)
            if not isinstance(record, dict):
                continue
            if (record.get('schema_version') == '2.0.0' and record.get('inspector_version') == INSPECTOR_VERSION
                    and record.get('policy') == policy):
                if record['inspection_id'] != path.parent.name:
                    continue
                if record['errors'] or record['summary']['quarantined'] or record['summary']['rejected']:
                    reference = quarantine_dir / record['batch_id'] / record['inspection_id'] / 'quarantine.json'
                    reference_bytes = reference.read_bytes()
                    if hashlib.sha256(reference_bytes).hexdigest() != reference.with_suffix('.json.sha256').read_text().strip():
                        continue
                completed.add(record['incoming_batch'])
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return completed
