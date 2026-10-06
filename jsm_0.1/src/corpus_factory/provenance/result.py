from dataclasses import dataclass
from enum import Enum


class TrainingUse(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class RightsDecision:
    training_use: TrainingUse
    basis: str
    authority: str
    decision_source: str

    @property
    def allowed(self) -> bool:
        return self.training_use is TrainingUse.ALLOWED