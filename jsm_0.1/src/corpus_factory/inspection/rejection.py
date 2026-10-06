"""Rejection is final: it records control references for cleanup, never copies or moves incoming objects."""
from pathlib import Path

from paths import REJECTED_DIR
from src.corpus_factory.inspection.quarantine import artifact_references
from src.corpus_factory.inspection.report import publish_record, utc_now
from src.corpus_factory.inspection.result import InspectionDecision as D, InspectionResult


def reject_batch(batch_dir: Path, result: InspectionResult, inspection_id: str,
                 rejected_dir: Path = REJECTED_DIR) -> Path | None:
    references = artifact_references(batch_dir, result, inspection_id, D.REJECTED)
    if not references:
        return None
    record = {
        'schema_version': '2.0.0', 'record_type': 'rejection_record',
        'inspection_id': inspection_id, 'batch_id': result.batch_id,
        'created_at': utc_now(), 'incoming_batch': str(Path(batch_dir).absolute()),
        'artifacts': references,
    }
    return publish_record(rejected_dir / result.batch_id, inspection_id, 'rejected.json', record)
