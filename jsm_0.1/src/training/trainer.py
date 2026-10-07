import math
import time
from pathlib import Path

import torch
from torch import nn

from src.dataset.loader import (
    load_token_stream,
    make_training_batches,
)
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
        weight_decay=training_config.get(
            "weight_decay",
            0.01,
        ),
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
    last_epoch = start_epoch

    batch_size = training_config.get(
        "batch_size",
        1,
    )

    warmup_steps = training_config.get(
        "warmup_steps",
        0,
    )

    gradient_clip = training_config.get(
        "gradient_clip"
    )

    max_training_minutes = training_config.get(
        "max_training_minutes"
    )

    early_stopping_patience = training_config.get(
        "early_stopping_patience"
    )

    log_every_steps = training_config.get(
        "log_every_steps"
    )

    epochs_without_improvement = 0

    token_stream = load_token_stream(
        train_path
    )

    steps_per_epoch = max(
        (len(token_stream) - 1)
        // (config.context_length * batch_size),
        1,
    )

    total_steps = epochs * steps_per_epoch

    def scheduled_learning_rate(
        step: int,
    ) -> float:
        # Linear warmup, then cosine decay to 10%.
        if step < warmup_steps:
            return (
                learning_rate
                * (step + 1)
                / warmup_steps
            )

        progress = min(
            (step - warmup_steps)
            / max(total_steps - warmup_steps, 1),
            1.0,
        )

        return learning_rate * (
            0.1
            + 0.9
            * 0.5
            * (1.0 + math.cos(math.pi * progress))
        )

    # --------------------------------------------------
    # Training
    # --------------------------------------------------

    for epoch in range(
        start_epoch + 1,
        epochs + 1,
    ):
        total_loss = 0.0
        steps_this_epoch = 0

        for x, y in make_training_batches(
            token_stream=token_stream,
            context_length=config.context_length,
            batch_size=batch_size,
        ):
            x = x.to(device)
            y = y.to(device)

            for group in optimizer.param_groups:
                group["lr"] = scheduled_learning_rate(
                    global_step
                )

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

            if gradient_clip is not None:
                nn.utils.clip_grad_norm_(
                    model.parameters(),
                    gradient_clip,
                )

            optimizer.step()

            total_loss += loss.item()

            steps_this_epoch += 1
            global_step += 1

            # Number of next-token targets processed.
            tokens_seen += y.numel()

            # A long epoch is otherwise silent until it ends.
            if (
                log_every_steps
                and steps_this_epoch % log_every_steps == 0
            ):
                print(
                    f"Epoch {epoch:03d} "
                    f"| step {steps_this_epoch:,}"
                    f"/{steps_per_epoch:,} "
                    f"| loss="
                    f"{total_loss / steps_this_epoch:.4f} "
                    f"| minutes="
                    f"{(time.perf_counter() - started_at) / 60:.1f}"
                )

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

            epochs_without_improvement = (
                0
                if is_best
                else epochs_without_improvement + 1
            )

        last_epoch = epoch

        if (
            early_stopping_patience is not None
            and epochs_without_improvement
            >= early_stopping_patience
        ):
            print(
                f"Stopping: validation loss has not "
                f"improved for "
                f"{epochs_without_improvement} epochs."
            )
            break

        if (
            max_training_minutes is not None
            and time.perf_counter() - started_at
            >= max_training_minutes * 60
        ):
            print(
                f"Stopping: reached the "
                f"{max_training_minutes}-minute limit."
            )
            break

    # --------------------------------------------------
    # Final stats
    # --------------------------------------------------

    training_seconds = (
        previous_training_seconds
        + time.perf_counter()
        - started_at
    )

    final_stats = {
        "epochs_completed": last_epoch,
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
    if last_saved_epoch != last_epoch:
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