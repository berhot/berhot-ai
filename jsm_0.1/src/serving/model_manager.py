import re
import threading
from collections import OrderedDict
from pathlib import Path

import torch

from src.model.config import ModelConfig
from src.model.model import TinyLLM
from src.tokenization.tokenizer import Tokenizer


class UnknownModelError(Exception):
    """The requested model id is not a discovered checkpoint."""


class ModelLoadError(Exception):
    """A discovered checkpoint or its tokenizer cannot be used."""


HISTORY_CHECKPOINT_PATTERN = re.compile(
    r"checkpoint_epoch_(\d+)_step_(\d+)"
)


def display_name(stem: str) -> str:
    """
    Human-friendly name for a checkpoint file stem.

    tiny_model -> Tiny Model
    checkpoint_epoch_000021_step_000000063
        -> Checkpoint Epoch 21 · Step 63
    jsm_10m -> JSM 10M
    """

    match = HISTORY_CHECKPOINT_PATTERN.fullmatch(stem)

    if match is not None:
        return (
            f"Checkpoint Epoch {int(match.group(1))}"
            f" · Step {int(match.group(2))}"
        )

    words = [
        word.upper()
        if word.lower() == "jsm"
        or any(character.isdigit() for character in word)
        else word.capitalize()
        for word in re.split(r"[_\-\s]+", stem)
        if word
    ]

    return " ".join(words) or stem


class ModelManager:
    """
    Single owner of model discovery, metadata, loading and caching.

    Today models are .pt files directly under one checkpoint
    directory. A later registry / publish system only has to
    replace the discovery part of this class.
    """

    def __init__(
        self,
        checkpoints_dir: Path,
        tokenizer_path: Path,
        default_model_id: str,
        device: torch.device,
        max_loaded_models: int = 4,
    ) -> None:
        self.checkpoints_dir = checkpoints_dir
        self.tokenizer_path = tokenizer_path
        self.default_model_id = default_model_id
        self.device = device
        self.max_loaded_models = max_loaded_models

        self._lock = threading.RLock()

        # model id -> (file signature, metadata or None if unusable)
        self._metadata_cache: dict[
            str, tuple[tuple, dict | None]
        ] = {}

        # model id -> (file signature, loaded model)
        self._loaded: OrderedDict[
            str, tuple[tuple, TinyLLM]
        ] = OrderedDict()

        self._tokenizer: Tokenizer | None = None

    # --------------------------------------------------
    # Discovery
    # --------------------------------------------------

    def _discover(self) -> dict[str, Path]:
        """
        Model id -> path, for checkpoints directly under
        the checkpoint directory.

        Every lookup of a client-supplied id goes through
        this mapping, so an id can never name another path.
        """

        if not self.checkpoints_dir.is_dir():
            return {}

        return {
            path.name: path
            for path in self.checkpoints_dir.glob("*.pt")
            if path.is_file()
            and not path.is_symlink()
        }

    @staticmethod
    def _signature(path: Path) -> tuple:
        stat = path.stat()

        return (
            stat.st_mtime_ns,
            stat.st_size,
        )

    def _read_checkpoint(self, path: Path) -> dict:
        try:
            checkpoint = torch.load(
                path,
                map_location="cpu",
                weights_only=True,
            )

        except Exception as error:
            raise ModelLoadError(
                f"Cannot read checkpoint {path.name}: "
                f"{error}"
            ) from error

        if (
            not isinstance(checkpoint, dict)
            or not isinstance(
                checkpoint.get("config"), dict
            )
            or not isinstance(
                checkpoint.get("model_state_dict"), dict
            )
        ):
            raise ModelLoadError(
                f"{path.name} is not a JSM checkpoint"
            )

        try:
            ModelConfig(**checkpoint["config"])

        except TypeError as error:
            raise ModelLoadError(
                f"{path.name} has an incompatible "
                f"model config: {error}"
            ) from error

        return checkpoint

    # --------------------------------------------------
    # Metadata
    # --------------------------------------------------

    def _metadata(
        self,
        model_id: str,
        path: Path,
    ) -> dict | None:
        signature = self._signature(path)

        cached = self._metadata_cache.get(model_id)

        if cached is not None and cached[0] == signature:
            return cached[1]

        try:
            checkpoint = self._read_checkpoint(path)

        except ModelLoadError:
            metadata = None

        else:
            config = checkpoint["config"]

            # Older checkpoints may miss any of these.
            training_stats = (
                checkpoint.get("training_stats") or {}
            )
            model_stats = (
                checkpoint.get("model_stats") or {}
            )

            metadata = {
                "id": model_id,
                "name": path.stem,
                "display_name": display_name(path.stem),
                # "checkpoint" = a per-epoch training snapshot,
                # "model" = something meant to be used.
                "kind": (
                    "checkpoint"
                    if HISTORY_CHECKPOINT_PATTERN.fullmatch(
                        path.stem
                    )
                    else "model"
                ),
                "parameters": model_stats.get(
                    "total_parameters"
                ),
                "trainable_parameters": model_stats.get(
                    "trainable_parameters"
                ),
                "epochs": training_stats.get(
                    "epochs_completed"
                ),
                "global_step": training_stats.get(
                    "global_step"
                ),
                "tokens_seen": training_stats.get(
                    "tokens_seen"
                ),
                "vocab_size": config.get("vocab_size"),
                "context_length": config.get(
                    "context_length"
                ),
            }

        self._metadata_cache[model_id] = (
            signature,
            metadata,
        )

        return metadata

    def _mark_unusable(
        self,
        model_id: str,
        signature: tuple,
    ) -> None:
        self._metadata_cache[model_id] = (
            signature,
            None,
        )

    def list_models(
        self,
        include_checkpoints: bool = False,
    ) -> list[dict]:
        """
        Usable models, latest first.

        Corrupt or incompatible checkpoints are skipped.
        Per-epoch training snapshots are left out unless
        asked for: they are history, not models to offer.
        """

        with self._lock:
            discovered = self._discover()

            for stale_id in (
                set(self._metadata_cache) - set(discovered)
            ):
                del self._metadata_cache[stale_id]

            # Newest file first.
            ordered = sorted(
                discovered.items(),
                key=lambda item: item[1].stat().st_mtime_ns,
                reverse=True,
            )

            models = [
                metadata
                for model_id, path in ordered
                if (
                    metadata := self._metadata(
                        model_id, path
                    )
                )
                is not None
                and (
                    include_checkpoints
                    or metadata["kind"] == "model"
                )
            ]

            if not models:
                return []

            ids = [model["id"] for model in models]

            latest_id = (
                self.default_model_id
                if self.default_model_id in ids
                else ids[0]
            )

            models = [
                {
                    **model,
                    "latest": model["id"] == latest_id,
                }
                for model in models
            ]

            models.sort(
                key=lambda model: not model["latest"]
            )

            return models

    def latest_model_id(self) -> str | None:
        models = self.list_models()

        return models[0]["id"] if models else None

    # --------------------------------------------------
    # Loading
    # --------------------------------------------------

    def tokenizer_for(self, model_id: str) -> Tokenizer:
        """
        Every checkpoint currently shares one tokenizer.

        Callers ask per model, so model-specific tokenizers
        can be added here later without touching them.
        """

        with self._lock:
            if self._tokenizer is None:
                if not self.tokenizer_path.is_file():
                    raise ModelLoadError(
                        f"Tokenizer not found: "
                        f"{self.tokenizer_path}"
                    )

                try:
                    self._tokenizer = Tokenizer.load(
                        self.tokenizer_path
                    )

                except Exception as error:
                    raise ModelLoadError(
                        f"Cannot load tokenizer: {error}"
                    ) from error

            return self._tokenizer

    def load(self, model_id: str) -> TinyLLM:
        """
        Return the loaded model, reading it from disk only
        when it is not cached or its file has changed.
        """

        with self._lock:
            path = self._discover().get(model_id)

            if path is None:
                raise UnknownModelError(model_id)

            signature = self._signature(path)

            cached = self._loaded.get(model_id)

            if cached is not None and cached[0] == signature:
                self._loaded.move_to_end(model_id)

                return cached[1]

            tokenizer = self.tokenizer_for(model_id)

            try:
                checkpoint = self._read_checkpoint(path)

                config = ModelConfig(
                    **checkpoint["config"]
                )

                if config.vocab_size != tokenizer.vocab_size:
                    raise ModelLoadError(
                        f"{model_id} expects vocab size "
                        f"{config.vocab_size}, tokenizer has "
                        f"{tokenizer.vocab_size}"
                    )

                model = TinyLLM(config)

                try:
                    model.load_state_dict(
                        checkpoint["model_state_dict"]
                    )

                except RuntimeError as error:
                    raise ModelLoadError(
                        f"{model_id} does not match the "
                        f"current model architecture: {error}"
                    ) from error

            except ModelLoadError:
                self._mark_unusable(model_id, signature)
                raise

            model.to(self.device)
            model.eval()

            self._loaded[model_id] = (signature, model)
            self._loaded.move_to_end(model_id)

            while len(self._loaded) > self.max_loaded_models:
                self._loaded.popitem(last=False)

            return model
