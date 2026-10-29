from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    vocab_size: int = 2000
    context_length: int = 128

    d_model: int = 128
    num_heads: int = 4
    num_layers: int = 4

    dropout: float = 0.0

    def __post_init__(self):
        for name in ('vocab_size', 'context_length', 'd_model', 'num_heads', 'num_layers'):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        if self.d_model % self.num_heads:
            raise ValueError('d_model must be divisible by num_heads')
        if not 0 <= self.dropout < 1:
            raise ValueError('dropout must be between 0 and 1')
