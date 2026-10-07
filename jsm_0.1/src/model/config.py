from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    vocab_size: int = 300
    context_length: int = 128

    d_model: int = 128
    num_heads: int = 4
    num_layers: int = 4

    dropout: float = 0.0