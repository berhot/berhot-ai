import json

from pathlib import Path

from paths import PROJECT_DIR

from src.corpus_factory.provenance.result import (
    TrainingUse,
)


PROVENANCE_CONFIG_PATH = (
    PROJECT_DIR
    / "configs"
    / "provenance.json"
)


def validate_rule(
    name: str,
    rule: dict,
) -> None:
    if not isinstance(rule, dict):
        raise ValueError(
            f"Provenance rule must be an object: {name}"
        )

    allowed_keys = {
        "training_use",
        "basis",
        "authority",
    }

    unknown = set(rule) - allowed_keys

    if unknown:
        raise ValueError(
            f"Unknown provenance rule keys for "
            f"{name}: {sorted(unknown)}"
        )

    try:
        TrainingUse(
            rule.get("training_use")
        )

    except ValueError as error:
        raise ValueError(
            f"Invalid training_use for provenance "
            f"rule: {name}"
        ) from error

    for key in (
        "basis",
        "authority",
    ):
        value = rule.get(key)

        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                f"Provenance rule {name}: "
                f"{key} must be a non-empty string"
            )


def validate_rule_map(
    name: str,
    rules: dict,
) -> None:
    if not isinstance(rules, dict):
        raise ValueError(
            f"Provenance {name} must be an object"
        )

    normalized = set()

    for rule_name, rule in rules.items():
        if (
            not isinstance(rule_name, str)
            or not rule_name.strip()
        ):
            raise ValueError(
                f"Invalid provenance {name} name"
            )

        key = rule_name.strip().casefold()

        if key in normalized:
            raise ValueError(
                f"Duplicate provenance {name} rule: "
                f"{rule_name}"
            )

        normalized.add(key)

        validate_rule(
            f"{name}.{rule_name}",
            rule,
        )


def validate_provenance_config(
    config: dict,
) -> dict:
    if not isinstance(config, dict):
        raise ValueError(
            "Provenance config must be a JSON object"
        )

    allowed_keys = {
        "schema_version",
        "default",
        "sources",
        "platforms",
    }

    unknown = set(config) - allowed_keys

    if unknown:
        raise ValueError(
            f"Unknown provenance config keys: "
            f"{sorted(unknown)}"
        )

    if config.get(
        "schema_version"
    ) != "1.0.0":
        raise ValueError(
            "Unsupported provenance config schema"
        )

    default = config.get("default")

    validate_rule(
        "default",
        default,
    )

    validate_rule_map(
        "sources",
        config.get(
            "sources",
            {},
        ),
    )

    validate_rule_map(
        "platforms",
        config.get(
            "platforms",
            {},
        ),
    )

    return config


def load_provenance_config(
    path: Path = PROVENANCE_CONFIG_PATH,
) -> dict:
    try:
        config = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as error:
        raise ValueError(
            f"Cannot load provenance config "
            f"{path}: {error}"
        ) from error

    return validate_provenance_config(
        config
    )