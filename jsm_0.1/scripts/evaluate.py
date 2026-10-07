import torch

from paths import (
    CHECKPOINT_PATH,
    TRAINING_DATA_DIR,
)
from src.evaluation.evaluator import evaluate
from src.model.config import ModelConfig
from src.model.model import TinyLLM
from src.training.trainer import get_device


if __name__ == "__main__":
    device = get_device()

    checkpoint = torch.load(
        CHECKPOINT_PATH,
        map_location=device,
    )

    config = ModelConfig(
        **checkpoint["config"]
    )

    model = TinyLLM(config)

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    model.to(device)

    TOKENIZED_DIR = (
        TRAINING_DATA_DIR
        / "tokenized"
    )

    for split in (
        "train",
        "validation",
        "test",
    ):
        result = evaluate(
            model=model,
            config=config,
            dataset_path=TOKENIZED_DIR / f"{split}.jsonl",
            device=device,
        )

        if not result["available"]:
            print(
                f"{split}: no evaluation examples"
            )
            continue

        print(
            f"{split}: "
            f"loss={result['loss']:.4f}, "
            f"perplexity={result['perplexity']:.4f}, "
            f"steps={result['steps']}"
        )