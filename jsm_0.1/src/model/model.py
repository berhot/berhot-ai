import torch
from torch import nn

from src.model.config import ModelConfig
from src.model.embeddings import TokenAndPositionEmbedding
from src.model.transformer import TransformerBlock


class TinyLLM(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()

        self.config = config

        self.embeddings = TokenAndPositionEmbedding(
            config
        )

        self.blocks = nn.ModuleList(
            [
                TransformerBlock(config)
                for _ in range(config.num_layers)
            ]
        )

        self.final_norm = nn.LayerNorm(
            config.d_model
        )

        self.lm_head = nn.Linear(
            config.d_model,
            config.vocab_size,
            bias=False,
        )

    def forward(
        self,
        input_ids: torch.Tensor,
    ) -> torch.Tensor:

        x = self.embeddings(
            input_ids
        )

        for block in self.blocks:
            x = block(x)

        x = self.final_norm(x)

        logits = self.lm_head(x)

        return logits