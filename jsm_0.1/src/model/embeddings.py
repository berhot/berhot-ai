import torch
from torch import nn

from src.model.config import ModelConfig


class TokenAndPositionEmbedding(nn.Module):
    def __init__(self, config: ModelConfig):
        super().__init__()

        self.token_embedding = nn.Embedding(
            config.vocab_size,
            config.d_model,
        )

        self.position_embedding = nn.Embedding(
            config.context_length,
            config.d_model,
        )

    def forward(
        self,
        input_ids: torch.Tensor,
    ) -> torch.Tensor:

        batch_size, sequence_length = input_ids.shape

        if sequence_length > self.position_embedding.num_embeddings:
            raise ValueError(
                f"Sequence length {sequence_length} exceeds "
                f"context length "
                f"{self.position_embedding.num_embeddings}"
            )

        positions = torch.arange(
            sequence_length,
            device=input_ids.device,
        )

        token_vectors = self.token_embedding(
            input_ids
        )

        position_vectors = self.position_embedding(
            positions
        )

        return token_vectors + position_vectors