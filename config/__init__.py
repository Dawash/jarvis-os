import os
import yaml
from pathlib import Path

CONFIG_DIR = Path(__file__).parent
ROOT_DIR = CONFIG_DIR.parent

def load_config() -> dict:
    config_path = CONFIG_DIR / "settings.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    _resolve_env_vars(config)
    return config

def _resolve_env_vars(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                env_var = v[2:-1]
                obj[k] = os.environ.get(env_var, "")
            else:
                _resolve_env_vars(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                env_var = v[2:-1]
                obj[i] = os.environ.get(env_var, "")
            else:
                _resolve_env_vars(v)
