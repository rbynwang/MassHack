"""homesim: synthetic single-family home dataset grounded in HouseZero weather and PV.

Synthetic data. Only weather and PV inputs are measured (HouseZero).
"""

from pathlib import Path

import yaml

__version__ = "0.1.0"

DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")


def load_config(path: Path | None = None) -> dict:
    """Load the YAML config (defaults to the packaged config.yaml)."""
    with open(path or DEFAULT_CONFIG_PATH) as fh:
        return yaml.safe_load(fh)
