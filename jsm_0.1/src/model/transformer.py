import torch
from torch import nn

from src.model.attention import CausalSelfAttention
from src.model.config import ModelConfig


class FeedForward(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()

        hidden_size = 4 * config.d_model

        self.net = nn.Sequential(
            nn.Linear(
                config.d_model,
                hidden_size,
            ),
            nn.GELU(),
            nn.Linear(
                hidden_size,
                config.d_model,
            ),
            nn.Dropout(
                config.dropout
            ),
        )

    def forward(
        self,
        x: torch.Tensor,
    ) -> torch.Tensor:
        return self.net(x)


class TransformerBlock(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()

        self.norm1 = nn.LayerNorm(
            config.d_model
        )

        self.attention = CausalSelfAttention(
            config
        )

        self.norm2 = nn.LayerNorm(
            config.d_model
        )

        self.feed_forward = FeedForward(
            config
        )

    def forward(
        self,
        x: torch.Tensor,
    ) -> torch.Tensor:

        x = x + self.attention(
            self.norm1(x)
        )

        x = x + self.feed_forward(
            self.norm2(x)
        )

        return x