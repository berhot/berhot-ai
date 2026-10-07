import time
from pathlib import Path

import torch
from torch import nn

from src.dataset.loader import make_training_examples
from src.evaluation.evaluator import evaluate
from src.model.config import ModelConfig
from src.model.model import TinyLLM
from src.training.checkpoint import save_checkpoint


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")

    if torch.backends.mps.is_available():
        return torch.device("mps")

    return torch.device("cpu")


def train(
    model: TinyLLM,
    config: ModelConfig,
    train_path: Path,
    epochs: int,
    learning_rate: float,
    checkpoint_path: Path,
    training_config: dict,
    resume_checkpoint: dict | None = None,
    validation_path: Path | None = None,
) -> dict:

    device = get_device()

    model.to(device)
    model.train()

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=learning_rate,
    )

    loss_function = nn.CrossEntropyLoss()

    start_epoch = 0
    global_step = 0
    tokens_seen = 0
    previous_training_seconds = 0.0
    final_loss = None
    validation_loss = None
    best_validation_loss = None

    # --------------------------------------------------
    # Resume from checkpoint
    # --------------------------------------------------

    if resume_checkpoint is not None:
        model.load_state_dict(
            resume_checkpoint["model_state_dict"]
        )

        optimizer_state = resume_checkpoint.get(
            "optimizer_state_dict"
        )

        if optimizer_state is not None:
            optimizer.load_state_dict(
                optimizer_state
            )

        previous_stats = resume_checkpoint.get(
            "training_stats",
            {},
        )

        start_epoch = previous_stats.get(
            "epochs_completed",
            0,
        )

        global_step = previous_stats.get(
            "global_step",
            0,
        )

        tokens_seen = previous_stats.get(
            "tokens_seen",
            0,
        )

        previous_training_seconds = previous_stats.get(
            "training_seconds",
            0.0,
        )

        final_loss = previous_stats.get(
            "final_loss"
        )

        validation_loss = previous_stats.get(
            "validation_loss"
        )

        best_validation_loss = previous_stats.get(
            "best_validation_loss"
        )

        print(
            f"Resuming from epoch {start_epoch}, "
            f"step {global_step:,}, "
            f"tokens_seen {tokens_seen:,}"
        )

    print(f"Device: {device}")

    # Nothing left to train
    if start_epoch >= epochs:
        print(
            f"Training already completed "
            f"{start_epoch}/{epochs} epochs."
        )

        return {
            "epochs_completed": start_epoch,
            "global_step": global_step,
            "tokens_seen": tokens_seen,
            "training_seconds": previous_training_seconds,
            "final_loss": final_loss,
            "validation_loss": validation_loss,
            "best_validation_loss": best_validation_loss,
            "learning_rate": learning_rate,
        }

    started_at = time.perf_counter()

    checkpoint_every_epochs = training_config.get(
        "checkpoint_every_epochs",
        1,
    )

    keep_last_checkpoints = training_config.get(
        "keep_last_checkpoints",
        3,
    )

    last_saved_epoch = start_epoch

    # --------------------------------------------------
    # Training
    # --------------------------------------------------

    for epoch in range(
        start_epoch + 1,
        epochs + 1,
    ):
        total_loss = 0.0
        steps_this_epoch = 0

        for x, y in make_training_examples(
            path=train_path,
            context_length=config.context_length,
        ):
            x = x.unsqueeze(0).to(device)
            y = y.unsqueeze(0).to(device)

            optimizer.zero_grad()

            logits = model(x)

            loss = loss_function(
                logits.reshape(
                    -1,
                    config.vocab_size,
                ),
                y.reshape(-1),
            )

            loss.backward()

            optimizer.step()

            total_loss += loss.item()

            steps_this_epoch += 1
            global_step += 1

            # Number of next-token targets processed.
            tokens_seen += y.numel()

        if steps_this_epoch == 0:
            raise ValueError(
                "No training examples were produced"
            )

        final_loss = (
            total_loss
            / steps_this_epoch
        )

        print(
            f"Epoch {epoch:03d} "
            f"| loss={final_loss:.4f} "
            f"| steps={global_step:,} "
            f"| tokens_seen={tokens_seen:,}"
        )

        # --------------------------------------------------
        # Checkpoint
        # --------------------------------------------------

        if (
            checkpoint_every_epochs > 0
            and epoch % checkpoint_every_epochs == 0
        ):
            # --------------------------------------------------
            # Validation decides the best checkpoint
            # --------------------------------------------------

            is_best = False

            if (
                validation_path is not None
                and validation_path.is_file()
            ):
                result = evaluate(
                    model=model,
                    config=config,
                    dataset_path=validation_path,
                    device=device,
                )

                model.train()

                if result["available"]:
                    validation_loss = result["loss"]

                    is_best = (
                        best_validation_loss is None
                        or validation_loss
                        < best_validation_loss
                    )

                    if is_best:
                        best_validation_loss = (
                            validation_loss
                        )

                    print(
                        f"Epoch {epoch:03d} "
                        f"| validation_loss="
                        f"{validation_loss:.4f}"
                        f"{' (best)' if is_best else ''}"
                    )

            save_checkpoint(
                path=checkpoint_path,
                model=model,
                optimizer=optimizer,
                model_config=config,
                training_config=training_config,
                training_stats={
                    "epochs_completed": epoch,
                    "global_step": global_step,
                    "tokens_seen": tokens_seen,
                    "training_seconds": (
                        previous_training_seconds
                        + time.perf_counter()
                        - started_at
                    ),
                    "final_loss": final_loss,
                    "validation_loss": validation_loss,
                    "best_validation_loss": best_validation_loss,
                    "learning_rate": learning_rate,
                },
                keep_last=keep_last_checkpoints,
                is_best=is_best,
            )

            last_saved_epoch = epoch

    # --------------------------------------------------
    # Final stats
    # --------------------------------------------------

    training_seconds = (
        previous_training_seconds
        + time.perf_counter()
        - started_at
    )

    final_stats = {
        "epochs_completed": epochs,
        "global_step": global_step,
        "tokens_seen": tokens_seen,
        "training_seconds": training_seconds,
        "final_loss": final_loss,
        "validation_loss": validation_loss,
        "best_validation_loss": best_validation_loss,
        "learning_rate": learning_rate,
    }

    # Save the final state if the last epoch
    # was not already checkpointed.
    if last_saved_epoch != epochs:
        save_checkpoint(
            path=checkpoint_path,
            model=model,
            optimizer=optimizer,
            model_config=config,
            training_config=training_config,
            training_stats=final_stats,
            keep_last=keep_last_checkpoints,
        )

    return final_stats