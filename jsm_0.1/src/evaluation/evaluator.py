from pathlib import Path

import math
import torch
from torch import nn

from src.dataset.loader import make_training_examples
from src.model.config import ModelConfig
from src.model.model import TinyLLM


@torch.no_grad()
def evaluate(
    model: TinyLLM,
    config: ModelConfig,
    dataset_path: Path,
    device: torch.device,
) -> dict:
    model.eval()

    loss_function = nn.CrossEntropyLoss(reduction="sum")

    total_loss = 0.0
    steps = 0
    targets = 0

    for x, y in make_training_examples(
        path=dataset_path,
        context_length=config.context_length,
    ):
        x = x.unsqueeze(0).to(device)
        y = y.unsqueeze(0).to(device)

        logits = model(x)

        loss = loss_function(
            logits.reshape(-1, config.vocab_size),
            y.reshape(-1),
        )

        total_loss += loss.item()
        steps += 1
        targets += y.numel()

    if steps == 0:
        return {
            "available": False,
            "loss": None,
            "perplexity": None,
            "steps": 0,
        }

    average_loss = total_loss / targets

    return {
        "available": True,
        "loss": average_loss,
        "perplexity": math.exp(min(average_loss, 700)),
        "steps": steps,
    }