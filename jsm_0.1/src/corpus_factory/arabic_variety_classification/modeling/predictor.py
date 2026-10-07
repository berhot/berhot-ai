import hashlib
import json

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib

from src.corpus_factory.arabic_variety_classification.result import (
    ArabRegion,
    ArabicRegister,
    ModelDecision,
    SaudiRegion,
)
from src.corpus_factory.intake.hashing import (
    sha256_file,
)


MODEL_FILENAME = "model.joblib"
POLICY_FILENAME = "policy.json"
METADATA_FILENAME = "metadata.json"

REGISTER_TASK = "register"
ARAB_REGION_TASK = "arab_region"
SAUDI_REGION_TASK = "saudi_region"

NON_PREDICTABLE_LABELS = {
    "not_applicable",
    "undetermined",
}

TASK_LABELS = {
    REGISTER_TASK: frozenset(
        member.value
        for member in ArabicRegister
        if member.value
        not in NON_PREDICTABLE_LABELS
    ),
    ARAB_REGION_TASK: frozenset(
        member.value
        for member in ArabRegion
        if member.value
        not in NON_PREDICTABLE_LABELS
    ),
    SAUDI_REGION_TASK: frozenset(
        member.value
        for member in SaudiRegion
        if member.value
        not in NON_PREDICTABLE_LABELS
    ),
}


@dataclass(frozen=True)
class ModelArtifact:
    task: str

    model_version: str
    model_path: Path

    model_sha256: str
    policy_sha256: str
    metadata_sha256: str

    minimum_score: float
    minimum_margin: float


@dataclass(frozen=True)
class InferenceBundle:
    register: ModelArtifact
    arab_region: ModelArtifact
    saudi_region: ModelArtifact

    bundle_sha256: str


@dataclass(frozen=True)
class HierarchyPrediction:
    accepted: bool

    stopped_at: str | None

    register: str | None
    arab_region: str | None
    saudi_region: str | None

    register_decision: ModelDecision | None
    arab_region_decision: ModelDecision | None
    saudi_region_decision: ModelDecision | None


def require_file(
    path: Path,
) -> None:
    if path.is_symlink():
        raise ValueError(
            f"Model artifact cannot "
            f"be a symlink: {path}"
        )

    if not path.is_file():
        raise FileNotFoundError(
            f"Model artifact missing: "
            f"{path}"
        )


def load_json_object(
    path: Path,
) -> dict:
    value = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            f"{path} must contain "
            f"a JSON object"
        )

    return value


def read_threshold(
    policy: dict,
    field: str,
    path: Path,
) -> float:
    value = policy.get(
        field
    )

    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            (
                int,
                float,
            ),
        )
        or not 0.0 <= value <= 1.0
    ):
        raise ValueError(
            f"{path} has invalid "
            f"{field}"
        )

    return float(
        value
    )


def load_model_artifact(
    *,
    model_root: Path,
    task: str,
    version: str,
) -> ModelArtifact:
    if (
        not version
        or Path(version).name
        != version
    ):
        raise ValueError(
            f"Invalid {task} "
            f"model version: {version!r}"
        )

    model_dir = (
        model_root
        / task
        / version
    )

    model_path = (
        model_dir
        / MODEL_FILENAME
    )

    policy_path = (
        model_dir
        / POLICY_FILENAME
    )

    metadata_path = (
        model_dir
        / METADATA_FILENAME
    )

    for path in (
        model_path,
        policy_path,
        metadata_path,
    ):
        require_file(
            path
        )

    policy = load_json_object(
        policy_path
    )

    load_json_object(
        metadata_path
    )

    return ModelArtifact(
        task=task,
        model_version=version,
        model_path=(
            model_path.resolve()
        ),
        model_sha256=sha256_file(
            model_path
        ),
        policy_sha256=sha256_file(
            policy_path
        ),
        metadata_sha256=sha256_file(
            metadata_path
        ),
        minimum_score=read_threshold(
            policy,
            "minimum_score",
            policy_path,
        ),
        minimum_margin=read_threshold(
            policy,
            "minimum_margin",
            policy_path,
        ),
    )


def compute_bundle_sha256(
    artifacts: tuple[
        ModelArtifact,
        ...,
    ],
) -> str:
    payload = [
        {
            "task": artifact.task,
            "version": (
                artifact.model_version
            ),
            "model_sha256": (
                artifact.model_sha256
            ),
            "policy_sha256": (
                artifact.policy_sha256
            ),
            "metadata_sha256": (
                artifact.metadata_sha256
            ),
        }
        for artifact in artifacts
    ]

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        encoded
    ).hexdigest()


def build_inference_bundle(
    *,
    model_root: Path,
    register_version: str,
    arab_region_version: str,
    saudi_region_version: str,
) -> InferenceBundle:
    register = load_model_artifact(
        model_root=model_root,
        task=REGISTER_TASK,
        version=register_version,
    )

    arab_region = load_model_artifact(
        model_root=model_root,
        task=ARAB_REGION_TASK,
        version=arab_region_version,
    )

    saudi_region = load_model_artifact(
        model_root=model_root,
        task=SAUDI_REGION_TASK,
        version=saudi_region_version,
    )

    return InferenceBundle(
        register=register,
        arab_region=arab_region,
        saudi_region=saudi_region,
        bundle_sha256=(
            compute_bundle_sha256(
                (
                    register,
                    arab_region,
                    saudi_region,
                )
            )
        ),
    )


# The bundle only carries paths and hashes so it can be sent to worker
# processes; each worker loads a model once and keeps it here.
@lru_cache(maxsize=None)
def load_model(
    model_path: Path,
    model_sha256: str,
    task: str,
):
    if (
        sha256_file(
            model_path
        )
        != model_sha256
    ):
        raise ValueError(
            f"{task} model changed "
            f"after the bundle was built"
        )

    model = joblib.load(
        model_path
    )

    if not hasattr(
        model,
        "predict_proba",
    ):
        raise ValueError(
            f"{task} model does not "
            f"support predict_proba"
        )

    labels = tuple(
        str(label)
        for label in model.classes_
    )

    unknown = (
        set(labels)
        - TASK_LABELS[task]
    )

    if unknown:
        raise ValueError(
            f"{task} model has "
            f"unknown labels: "
            f"{sorted(unknown)}"
        )

    return (
        model,
        labels,
    )


def decide(
    *,
    text: str,
    artifact: ModelArtifact,
) -> ModelDecision:
    (
        model,
        labels,
    ) = load_model(
        artifact.model_path,
        artifact.model_sha256,
        artifact.task,
    )

    scores = model.predict_proba(
        [text]
    )[0]

    ranked = sorted(
        zip(
            labels,
            (
                float(score)
                for score in scores
            ),
        ),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    )

    (
        top_label,
        top_score,
    ) = ranked[0]

    if len(ranked) > 1:
        (
            second_label,
            second_score,
        ) = ranked[1]

    else:
        second_label = None
        second_score = 0.0

    margin = (
        top_score
        - second_score
    )

    accepted = (
        top_score
        >= artifact.minimum_score
        and margin
        >= artifact.minimum_margin
    )

    return ModelDecision(
        task=artifact.task,
        model_version=(
            artifact.model_version
        ),
        model_sha256=(
            artifact.model_sha256
        ),
        policy_sha256=(
            artifact.policy_sha256
        ),
        accepted=accepted,
        label=(
            top_label
            if accepted
            else None
        ),
        top_label=top_label,
        top_score=top_score,
        second_label=second_label,
        second_score=second_score,
        margin=margin,
        minimum_score=(
            artifact.minimum_score
        ),
        minimum_margin=(
            artifact.minimum_margin
        ),
    )


def predict_hierarchy(
    *,
    text: str,
    bundle: InferenceBundle,
) -> HierarchyPrediction:
    register_decision = decide(
        text=text,
        artifact=bundle.register,
    )

    if not register_decision.accepted:
        return HierarchyPrediction(
            accepted=False,
            stopped_at=REGISTER_TASK,
            register=None,
            arab_region=None,
            saudi_region=None,
            register_decision=(
                register_decision
            ),
            arab_region_decision=None,
            saudi_region_decision=None,
        )

    register = (
        register_decision.label
    )

    if (
        register
        != ArabicRegister.DIALECT.value
    ):
        return HierarchyPrediction(
            accepted=True,
            stopped_at=None,
            register=register,
            arab_region=None,
            saudi_region=None,
            register_decision=(
                register_decision
            ),
            arab_region_decision=None,
            saudi_region_decision=None,
        )

    arab_region_decision = decide(
        text=text,
        artifact=bundle.arab_region,
    )

    if not arab_region_decision.accepted:
        return HierarchyPrediction(
            accepted=False,
            stopped_at=ARAB_REGION_TASK,
            register=register,
            arab_region=None,
            saudi_region=None,
            register_decision=(
                register_decision
            ),
            arab_region_decision=(
                arab_region_decision
            ),
            saudi_region_decision=None,
        )

    arab_region = (
        arab_region_decision.label
    )

    if (
        arab_region
        != ArabRegion.SAUDI.value
    ):
        return HierarchyPrediction(
            accepted=True,
            stopped_at=None,
            register=register,
            arab_region=arab_region,
            saudi_region=None,
            register_decision=(
                register_decision
            ),
            arab_region_decision=(
                arab_region_decision
            ),
            saudi_region_decision=None,
        )

    saudi_region_decision = decide(
        text=text,
        artifact=bundle.saudi_region,
    )

    return HierarchyPrediction(
        accepted=(
            saudi_region_decision
            .accepted
        ),
        stopped_at=(
            None
            if saudi_region_decision
            .accepted
            else SAUDI_REGION_TASK
        ),
        register=register,
        arab_region=arab_region,
        saudi_region=(
            saudi_region_decision.label
        ),
        register_decision=(
            register_decision
        ),
        arab_region_decision=(
            arab_region_decision
        ),
        saudi_region_decision=(
            saudi_region_decision
        ),
    )
