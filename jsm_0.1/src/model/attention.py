import math

import torch
from torch import nn

from src.model.config import ModelConfig


class CausalSelfAttention(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()

        if config.d_model % config.num_heads != 0:
            raise ValueError(
                "d_model must be divisible by num_heads"
            )

        self.num_heads = config.num_heads
        self.head_dim = (
            config.d_model // config.num_heads
        )

        self.q_proj = nn.Linear(
            config.d_model,
            config.d_model,
            bias=False,
        )

        self.k_proj = nn.Linear(
            config.d_model,
            config.d_model,
            bias=False,
        )

        self.v_proj = nn.Linear(
            config.d_model,
            config.d_model,
            bias=False,
        )

        self.out_proj = nn.Linear(
            config.d_model,
            config.d_model,
            bias=False,
        )

        self.dropout = nn.Dropout(
            config.dropout
        )

    def forward(
        self,
        x: torch.Tensor,
    ) -> torch.Tensor:

        batch_size, sequence_length, d_model = x.shape

        q = self.q_proj(x)
        k = self.k_proj(x)
        v = self.v_proj(x)

        q = q.view(
            batch_size,
            sequence_length,
            self.num_heads,
            self.head_dim,
        ).transpose(1, 2)

        k = k.view(
            batch_size,
            sequence_length,
            self.num_heads,
            self.head_dim,
        ).transpose(1, 2)

        v = v.view(
            batch_size,
            sequence_length,
            self.num_heads,
            self.head_dim,
        ).transpose(1, 2)

        scores = (
            q @ k.transpose(-2, -1)
        ) / math.sqrt(self.head_dim)

        causal_mask = torch.triu(
            torch.ones(
                sequence_length,
                sequence_length,
                device=x.device,
                dtype=torch.bool,
            ),
            diagonal=1,
        )

        scores = scores.masked_fill(
            causal_mask,
            float("-inf"),
        )

        attention_weights = torch.softmax(
            scores,
            dim=-1,
        )

        attention_weights = self.dropout(
            attention_weights
        )

        output = attention_weights @ v

        output = output.transpose(
            1,
            2,
        ).contiguous()

        output = output.view(
            batch_size,
            sequence_length,
            d_model,
        )

        return self.out_proj(output)