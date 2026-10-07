import sys

import torch

from paths import (
    CHECKPOINT_PATH,
    TOKENIZER_PATH,
)
from src.inference.generator import generate
from src.model.config import ModelConfig
from src.model.model import TinyLLM
from src.tokenization.tokenizer import Tokenizer
from src.training.trainer import get_device


if __name__ == "__main__":
    prompt = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "علي حسن"
    )

    device = get_device()

    tokenizer = Tokenizer.load(
        TOKENIZER_PATH
    )

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

    output = generate(
        model=model,
        tokenizer=tokenizer,
        prompt=prompt,
        max_new_tokens=50,
        temperature=0.0,
    )

    print(f"Device: {device}")
    print()
    print(output)