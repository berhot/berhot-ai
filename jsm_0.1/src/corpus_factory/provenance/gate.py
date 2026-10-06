from src.corpus_factory.provenance.result import (
    RightsDecision,
    TrainingUse,
)


def _find_rule(
    rules: dict,
    value: str,
) -> dict | None:
    target = value.strip().casefold()

    for name, rule in rules.items():
        if name.strip().casefold() == target:
            return rule

    return None


def _decision_from_rule(
    rule: dict,
    decision_source: str,
) -> RightsDecision:
    return RightsDecision(
        training_use=TrainingUse(
            rule["training_use"]
        ),
        basis=rule["basis"].strip(),
        authority=rule["authority"].strip(),
        decision_source=decision_source,
    )


def evaluate_policy(
    source_manifest: dict,
    policy: dict,
) -> RightsDecision:
    source = source_manifest.get(
        "source"
    )

    if not isinstance(source, dict):
        raise ValueError(
            "source.json has no valid source object"
        )

    source_name = source.get(
        "name"
    )

    platform = source.get(
        "platform"
    )

    if source_name is not None:
        if not isinstance(
            source_name,
            str,
        ):
            raise ValueError(
                "source.name must be a string"
            )

        rule = _find_rule(
            policy["sources"],
            source_name,
        )

        if rule is not None:
            return _decision_from_rule(
                rule,
                "source_policy",
            )

    if not isinstance(
        platform,
        str,
    ) or not platform.strip():
        raise ValueError(
            "source.platform must be a "
            "non-empty string"
        )

    rule = _find_rule(
        policy["platforms"],
        platform,
    )

    if rule is not None:
        return _decision_from_rule(
            rule,
            "platform_policy",
        )

    return _decision_from_rule(
        policy["default"],
        "default_policy",
    )