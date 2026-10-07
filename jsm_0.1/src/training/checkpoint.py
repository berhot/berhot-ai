import shutil
from pathlib import Path

import torch

from src.model.config import ModelConfig
from src.model.model import TinyLLM


def save_checkpoint(
    path: Path,
    model: TinyLLM,
    optimizer: torch.optim.Optimizer,
    model_config: ModelConfig,
    training_config: dict,
    training_stats: dict,
    keep_last: int = 3,
    is_best: bool = False,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    checkpoint = {
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),

        "config": {
            "vocab_size": model_config.vocab_size,
            "context_length": model_config.context_length,
            "d_model": model_config.d_model,
            "num_heads": model_config.num_heads,
            "num_layers": model_config.num_layers,
            "dropout": model_config.dropout,
        },

        "training_config": training_config,
        "training_stats": training_stats,

        "model_stats": {
            "total_parameters": sum(
                parameter.numel()
                for parameter in model.parameters()
            ),
            "trainable_parameters": sum(
                parameter.numel()
                for parameter in model.parameters()
                if parameter.requires_grad
            ),
        },
    }

    # --------------------------------------------------
    # Latest checkpoint
    # --------------------------------------------------

    temporary_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    torch.save(
        checkpoint,
        temporary_path,
    )

    temporary_path.replace(
        path
    )

    # --------------------------------------------------
    # Best checkpoint
    # --------------------------------------------------

    if is_best:
        copy_checkpoint(
            path,
            best_checkpoint_path(path),
        )

    # --------------------------------------------------
    # Historical checkpoints
    # --------------------------------------------------

    if keep_last > 0:
        epoch = training_stats["epochs_completed"]
        global_step = training_stats["global_step"]

        copy_checkpoint(
            path,
            path.parent
            / (
                f"checkpoint_epoch_{epoch:06d}"
                f"_step_{global_step:09d}.pt"
            ),
        )

    prune_history(
        path.parent,
        keep_last,
    )


def best_checkpoint_path(path: Path) -> Path:
    return path.with_name(
        "best_" + path.name
    )


def copy_checkpoint(
    source: Path,
    destination: Path,
) -> None:
    temporary_path = destination.with_suffix(
        destination.suffix + ".tmp"
    )

    shutil.copyfile(
        source,
        temporary_path,
    )

    temporary_path.replace(
        destination
    )


def prune_history(
    checkpoints_dir: Path,
    keep_last: int,
) -> None:
    """
    Keep only the newest historical checkpoints.

    Names are zero-padded, so sorting by name
    is sorting by epoch and step.
    """

    history = sorted(
        checkpoints_dir.glob(
            "checkpoint_epoch_*_step_*.pt"
        )
    )

    excess = max(
        len(history) - max(keep_last, 0),
        0,
    )

    for old_path in history[:excess]:
        old_path.unlink()


def load_checkpoint(
    path: Path,
    device: torch.device,
) -> dict | None:
    if not path.is_file():
        return None

    return torch.load(
        path,
        map_location=device,
    )