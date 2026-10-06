"""Quarantine holds control references, never copies or moves incoming objects."""
from pathlib import Path

from paths import QUARANTINE_DIR
from src.corpus_factory.inspection.report import publish_record, utc_now
from src.corpus_factory.inspection.result import InspectionDecision as D, InspectionResult


def quarantine_batch(batch_dir: Path, result: InspectionResult, inspection_id: str,
                     quarantine_dir: Path = QUARANTINE_DIR) -> Path | None:
    references = [
        {'batch_id': result.batch_id, 'artifact_id': a.artifact_id,
         'decision': a.decision, 'reason': a.errors,
         'inspection_id': inspection_id,
         'source_reference': str(Path(batch_dir).absolute() / a.stored_relative_path)}
        for a in result.artifacts if a.decision != D.ACCEPTED
    ]
    if not references and result.batch_valid:
        return None
    record = {
        'schema_version': '2.0.0', 'record_type': 'quarantine_record',
        'inspection_id': inspection_id, 'batch_id': result.batch_id,
        'created_at': utc_now(), 'incoming_batch': str(Path(batch_dir).absolute()),
        'batch_errors': result.errors, 'artifacts': references,
    }
    return publish_record(quarantine_dir / result.batch_id, inspection_id, 'quarantine.json', record)
