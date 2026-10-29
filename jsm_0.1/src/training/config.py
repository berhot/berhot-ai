import json
import math
from pathlib import Path
from paths import PROJECT_DIR
from src.model.config import ModelConfig

TRAINING_CONFIG_PATH = PROJECT_DIR / 'configs/training.json'
DEFAULTS = {'epochs': 2, 'batch_size': 32, 'gradient_accumulation_steps': 1,
    'learning_rate': 0.0003, 'warmup_steps': 200, 'weight_decay': 0.1,
    'gradient_clip': 1.0, 'seed': 42, 'precision': 'auto', 'device': 'auto',
    'checkpoint_every_steps': 100, 'eval_every_steps': 500, 'eval_batch_size': 32,
    'log_every_steps': 20, 'early_stopping_patience': None, 'max_training_minutes': None, 'max_steps': None}


def validate_training_config(config):
    for key in ('epochs', 'batch_size', 'gradient_accumulation_steps', 'checkpoint_every_steps', 'eval_every_steps', 'eval_batch_size', 'log_every_steps'):
        if type(config[key]) is not int or config[key] < 1:
            raise ValueError(f'{key} must be a positive integer')
    for key in ('seed', 'warmup_steps'):
        if type(config[key]) is not int or config[key] < 0:
            raise ValueError(f'{key} must be a nonnegative integer')
    for key in ('learning_rate', 'gradient_clip', 'weight_decay'):
        if not isinstance(config[key], (float, int)) or not math.isfinite(config[key]) or config[key] < 0 or (key != 'weight_decay' and config[key] == 0):
            raise ValueError(f'Invalid {key}')
    for key in ('early_stopping_patience', 'max_steps', 'max_training_minutes'):
        if config.get(key) is not None and (not isinstance(config[key], (int, float)) or not math.isfinite(config[key]) or config[key] <= 0):
            raise ValueError(f'{key} must be positive or null')
    ModelConfig(**config.get('model', {}))
    return config


def load_training_config(path: Path = TRAINING_CONFIG_PATH) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('Training config must be a JSON object')
    unknown = set(value) - set(DEFAULTS) - {'model'}
    if unknown:
        raise ValueError(f'Unknown training settings: {sorted(unknown)}')
    return validate_training_config({**DEFAULTS, **value})
