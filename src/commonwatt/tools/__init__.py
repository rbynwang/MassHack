"""Model tools the agents call. See contract.py for the interface the trained model implements."""

from __future__ import annotations

import importlib
import os

from commonwatt.tools.contract import EnergyModelTool

DEFAULT_TOOL = "commonwatt.tools.mock:MockModelTool"


def load_tool(spec: str | None = None) -> EnergyModelTool:
    """Load the model tool named by `spec` or $COMMONWATT_TOOL, as 'package.module:ClassName'."""
    spec = spec or os.environ.get("COMMONWATT_TOOL", DEFAULT_TOOL)
    module_name, _, cls_name = spec.partition(":")
    cls = getattr(importlib.import_module(module_name), cls_name)
    return cls()
