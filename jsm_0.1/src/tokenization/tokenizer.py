import json
from pathlib import Path

from src.tokenization.bpe import (
    BPEModel,
    BOS_ID,
    EOS_ID,
    PAD_ID,
    FIRST_MERGE_ID,
    merge_pair,
)


class Tokenizer:
    def __init__(
        self,
        model: BPEModel,
    ):
        self.model = model

        self._token_bytes = {
            token_id: bytes([token_id])
            for token_id in range(256)
        }

        for index, pair in enumerate(
            self.model.merges
        ):
            token_id = FIRST_MERGE_ID + index

            self._token_bytes[token_id] = (
                self._token_bytes[pair[0]]
                + self._token_bytes[pair[1]]
            )

    @property
    def vocab_size(self) -> int:
        return self.model.vocab_size

    @property
    def bos_id(self) -> int:
        return BOS_ID

    @property
    def eos_id(self) -> int:
        return EOS_ID

    @property
    def pad_id(self) -> int:
        return PAD_ID

    def encode(
        self,
        text: str,
        add_bos: bool = False,
        add_eos: bool = False,
    ) -> list[int]:

        tokens = list(
            text.encode("utf-8")
        )

        for index, pair in enumerate(
            self.model.merges
        ):
            new_token_id = (
                FIRST_MERGE_ID + index
            )

            tokens = merge_pair(
                tokens=tokens,
                pair=pair,
                new_token_id=new_token_id,
            )

        if add_bos:
            tokens.insert(
                0,
                BOS_ID,
            )

        if add_eos:
            tokens.append(
                EOS_ID
            )

        return tokens

    def token_to_bytes(
        self,
        token_id: int,
    ) -> bytes:

        if token_id in {
            BOS_ID,
            EOS_ID,
            PAD_ID,
        }:
            return b""

        if token_id not in self._token_bytes:
            raise ValueError(
                f"Unknown token id: {token_id}"
            )

        return self._token_bytes[token_id]

    def tokens_to_bytes(
        self,
        token_ids: list[int],
    ) -> bytes:

        parts = []

        for token_id in token_ids:
            if token_id in {
                BOS_ID,
                EOS_ID,
                PAD_ID,
            }:
                continue

            parts.append(
                self.token_to_bytes(
                    token_id
                )
            )

        return b"".join(parts)

    def decode(
        self,
        token_ids: list[int],
        skip_special_tokens: bool = True,
        errors: str = "strict",
    ) -> str:

        data_parts = []

        for token_id in token_ids:
            if token_id in {
                BOS_ID,
                EOS_ID,
                PAD_ID,
            }:
                if skip_special_tokens:
                    continue

                raise ValueError(
                    "Cannot decode special token as text"
                )

            data_parts.append(
                self.token_to_bytes(
                    token_id
                )
            )

        return b"".join(
            data_parts
        ).decode(
            "utf-8",
            errors=errors,
        )

    def save(
        self,
        path: Path,
    ) -> None:

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = {
            "type": "byte_level_bpe",
            "version": "1.0.0",

            "base_vocab_size": 256,

            "special_tokens": {
                "bos": {
                    "token": "<BOS>",
                    "id": BOS_ID,
                },
                "eos": {
                    "token": "<EOS>",
                    "id": EOS_ID,
                },
                "pad": {
                    "token": "<PAD>",
                    "id": PAD_ID,
                },
            },

            "first_merge_id": FIRST_MERGE_ID,
            "vocab_size": self.vocab_size,

            "merges": [
                [left, right]
                for left, right
                in self.model.merges
            ],
        }

        path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(
        cls,
        path: Path,
    ) -> "Tokenizer":

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        merges = tuple(
            (left, right)
            for left, right
            in data["merges"]
        )

        return cls(
            BPEModel(
                merges=merges
            )
        )