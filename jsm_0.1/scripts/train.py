from paths import (
    TRAINING_DATA_DIR,
    CHECKPOINT_PATH,
    RUNS_DIR,
)

from src.model.config import ModelConfig
from src.model.model import TinyLLM
from src.training.checkpoint import load_checkpoint
from src.training.config import load_training_config
from src.training.run import create_run, finish_run
from src.training.trainer import get_device, train


TRAIN_PATH = (
    TRAINING_DATA_DIR
    / "tokenized"
    / "train.jsonl"
)

VALIDATION_PATH = (
    TRAINING_DATA_DIR
    / "tokenized"
    / "validation.jsonl"
)


if __name__ == "__main__":
    training_config = load_training_config()

    model_config = ModelConfig()

    model = TinyLLM(
        model_config
    )

    device = get_device()

    model_config_dict = {
        "vocab_size": model_config.vocab_size,
        "context_length": model_config.context_length,
        "d_model": model_config.d_model,
        "num_heads": model_config.num_heads,
        "num_layers": model_config.num_layers,
        "dropout": model_config.dropout,
    }

    # -----------------------------------------
    # Create training run
    # -----------------------------------------

    run_id, run_path = create_run(
        runs_dir=RUNS_DIR,
        device=str(device),
        checkpoint_path=CHECKPOINT_PATH,
        model_config=model_config_dict,
        training_config=training_config,
    )

    print(f"Run: {run_id}")

    # -----------------------------------------
    # Resume
    # -----------------------------------------

    resume_checkpoint = None

    if training_config.get(
        "resume",
        True,
    ):
        resume_checkpoint = load_checkpoint(
            CHECKPOINT_PATH,
            device,
        )

    # -----------------------------------------
    # Train
    # -----------------------------------------

    training_stats = train(
        model=model,
        config=model_config,
        train_path=TRAIN_PATH,
        epochs=training_config["epochs"],
        learning_rate=training_config["learning_rate"],
        checkpoint_path=CHECKPOINT_PATH,
        training_config=training_config,
        resume_checkpoint=resume_checkpoint,
        validation_path=VALIDATION_PATH,
    )

    # -----------------------------------------
    # Model stats
    # -----------------------------------------

    model_stats = {
        "total_parameters": sum(
            parameter.numel()
            for parameter in model.parameters()
        ),

        "trainable_parameters": sum(
            parameter.numel()
            for parameter in model.parameters()
            if parameter.requires_grad
        ),
    }

    # -----------------------------------------
    # Finish run
    # -----------------------------------------

    finish_run(
        run_path=run_path,
        training_stats=training_stats,
        model_stats=model_stats,
    )

    # -----------------------------------------
    # Summary
    # -----------------------------------------

    print()
    print(f"Checkpoint: {CHECKPOINT_PATH}")

    print(
        f"Epochs completed: "
        f"{training_stats['epochs_completed']}"
    )

    print(
        f"Global steps: "
        f"{training_stats['global_step']:,}"
    )

    print(
        f"Tokens seen: "
        f"{training_stats['tokens_seen']:,}"
    )

    print(
        f"Run metadata: {run_path}"
    )