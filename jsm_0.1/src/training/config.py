import json

from paths import PROJECT_DIR


TRAINING_CONFIG_PATH = (
    PROJECT_DIR
    / "configs"
    / "training.json"
)


def load_training_config() -> dict:
    if not TRAINING_CONFIG_PATH.is_file():
        raise FileNotFoundError(
            f"Training config not found: "
            f"{TRAINING_CONFIG_PATH}"
        )

    with TRAINING_CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        config = json.load(file)

    if not isinstance(config, dict):
        raise ValueError(
            "training.json must contain a JSON object"
        )

    return config