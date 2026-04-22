import yaml
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_CONFIG_PATH = _ROOT / "config" / "config.yaml"

def load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)

def paths(cfg: dict) -> dict:
    root = _ROOT
    return {k: root / v for k, v in cfg["paths"].items()}
