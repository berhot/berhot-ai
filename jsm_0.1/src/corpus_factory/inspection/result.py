"""Immutable evidence and monotonic artifact decisions."""
from dataclasses import dataclass
from enum import Enum


class InspectionDecision(str, Enum):
    ACCEPTED = "accepted_for_ingestion"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"


def more_restrictive_decision(current, candidate):
    order = tuple(InspectionDecision)
    return max((current, candidate), key=order.index)


class MalwareScanStatus(str, Enum):
    NOT_RUN = "not_run"
    UNAVAILABLE = "unavailable"
    CLEAN = "clean"
    INFECTED = "infected"
    ERROR = "error"


@dataclass(frozen=True)
class MalwareScanResult:
    status: MalwareScanStatus = MalwareScanStatus.NOT_RUN
    engine: str | None = None
    signature: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class CheckResult:
    name: str
    decision: InspectionDecision = InspectionDecision.ACCEPTED
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArtifactInspectionResult:
    artifact_id: str
    filename: str
    stored_relative_path: str
    decision: InspectionDecision = InspectionDecision.ACCEPTED
    size_bytes: int | None = None
    sha256: str | None = None
    detected_mime_type: str | None = None
    mime_detection_method: str | None = None
    encoding: str | None = None
    character_count: int | None = None
    line_count: int | None = None
    max_line_characters: int | None = None
    is_regular_file: bool = False
    is_symlink: bool = False
    malware_scan_status: MalwareScanStatus = MalwareScanStatus.NOT_RUN
    malware_engine: str | None = None
    malware_signature: str | None = None
    malware_error: str | None = None
    flags: tuple[str, ...] = ()
    checks: tuple[CheckResult, ...] = ()

    @property
    def errors(self):
        return tuple(error for check in self.checks for error in check.errors)


@dataclass(frozen=True)
class InspectionResult:
    batch_id: str
    source_manifest_sha256: str | None
    policy: dict
    artifacts: tuple[ArtifactInspectionResult, ...] = ()
    checks: tuple[CheckResult, ...] = ()

    @property
    def errors(self):
        return tuple(error for check in self.checks for error in check.errors)

    @property
    def batch_valid(self):
        return not self.errors

    @property
    def duplicate_groups(self):
        groups = {}
        for artifact in self.artifacts:
            if artifact.sha256:
                groups.setdefault(artifact.sha256, []).append(artifact.artifact_id)
        return tuple({"sha256": sha, "count": len(ids), "artifact_ids": ids}
                     for sha, ids in sorted(groups.items()) if len(ids) > 1)

    @property
    def summary(self):
        return {
            "total_artifacts": len(self.artifacts),
            "total_bytes": sum(a.size_bytes or 0 for a in self.artifacts),
            **{d.name.lower(): sum(a.decision == d for a in self.artifacts)
               for d in InspectionDecision},
            "duplicate_groups": len(self.duplicate_groups),
            **{f"malware_{s.value}": sum(a.malware_scan_status == s for a in self.artifacts)
               for s in MalwareScanStatus},
        }
