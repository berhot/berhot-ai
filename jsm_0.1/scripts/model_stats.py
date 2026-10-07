import json

import torch

from paths import (
    CHECKPOINT_PATH,
    TOKENIZER_PATH,
    TRAINING_DATA_DIR,
)
from src.dataset.loader import load_token_sequences
from src.model.config import ModelConfig
from src.model.model import TinyLLM
from src.tokenization.tokenizer import Tokenizer


TRAIN_PATH = (
    TRAINING_DATA_DIR
    / "tokenized"
    / "train.jsonl"
)


def count_parameters(model):
    total = sum(
        parameter.numel()
        for parameter in model.parameters()
    )

    trainable = sum(
        parameter.numel()
        for parameter in model.parameters()
        if parameter.requires_grad
    )

    return total, trainable


def count_dataset_tokens(path):
    documents = 0
    stored_tokens = 0
    prediction_tokens = 0
    steps = 0

    context_length = 128

    for token_ids in load_token_sequences(path):
        documents += 1
        stored_tokens += len(token_ids)

        if len(token_ids) < 2:
            continue

        prediction_tokens += len(token_ids) - 1

        for start in range(
            0,
            len(token_ids) - 1,
            context_length,
        ):
            chunk = token_ids[
                start:start + context_length + 1
            ]

            if len(chunk) >= 2:
                steps += 1

    return {
        "documents": documents,
        "stored_tokens": stored_tokens,
        "prediction_tokens_per_epoch": prediction_tokens,
        "steps_per_epoch": steps,
    }


if __name__ == "__main__":
    checkpoint = torch.load(
        CHECKPOINT_PATH,
        map_location="cpu",
    )

    config = ModelConfig(
        **checkpoint["config"]
    )

    model = TinyLLM(config)

    total_params, trainable_params = (
        count_parameters(model)
    )

    tokenizer = Tokenizer.load(
        TOKENIZER_PATH
    )

    dataset = count_dataset_tokens(
        TRAIN_PATH
    )

    model_bytes = sum(
        parameter.numel()
        * parameter.element_size()
        for parameter in model.parameters()
    )

    print("JSM MODEL STATS")
    print("--------------------------")

    print(f"Parameters:       {total_params:,}")
    print(f"Trainable params: {trainable_params:,}")
    print(
        f"Model FP32 size:  "
        f"{model_bytes / 1024 / 1024:.2f} MB"
    )

    print()
    print(f"Vocabulary:       {tokenizer.vocab_size:,}")
    print(f"Context length:   {config.context_length}")
    print(f"d_model:          {config.d_model}")
    print(f"Attention heads:  {config.num_heads}")
    print(f"Layers:           {config.num_layers}")

    print()
    print(
        f"Train documents:  "
        f"{dataset['documents']:,}"
    )
    print(
        f"Dataset tokens:   "
        f"{dataset['stored_tokens']:,}"
    )
    print(
        f"Prediction tokens/epoch: "
        f"{dataset['prediction_tokens_per_epoch']:,}"
    )
    print(
        f"Steps/epoch:      "
        f"{dataset['steps_per_epoch']:,}"
    )