# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""SAM3 saved job configs — schema + store factory.

The JSON-on-disk CRUD lives in the shared
:class:`tlc_plugin_sdk.shared.config_store.PluginConfigStore`; this
module only declares the plugin's config schema and a store factory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tlc_plugin_sdk.shared.config_store import PluginConfigStore


@dataclass
class SAM3Config:
    """A saved SAM3 auto-labeling configuration."""

    id: str = ""
    name: str = ""
    source_type: str = "folder"  # folder | table
    folder: str = ""
    table_url: str = ""
    labels: list[dict[str, str]] = field(default_factory=list)  # [{name, color}]
    modality: str = "segmentation"
    confidence: float = 0.2
    project_name: str = ""
    dataset_name: str = "train"
    table_name: str = "initial"
    embedding_dim: int = 2
    device: str = "cuda"
    created: str = ""
    last_run: str | None = None


# Pre-standardization location, migrated into ~/.3lc-plugin-configs/sam3/ on
# first store construction. Remove once the cutover is complete.
_LEGACY_DIR = Path.home() / ".3lc-sam3" / "configs"


def config_store() -> PluginConfigStore[SAM3Config]:
    """Return a store for SAM3 saved configs (cheap; not cached)."""
    return PluginConfigStore(SAM3Config, "sam3", legacy_dir=_LEGACY_DIR)


# The HF token used to live only in the worker's process env (os.environ), so it
# evaporated on every worker restart — and never reached remote GPU workers at all.
# Persisted in the plugin config dir it survives restarts AND rides the host's
# config seeding onto fresh nodes.
_HF_TOKEN_FILE = "hf-token.json"


def persist_hf_token(token: str) -> None:
    """Save the HF token in the plugin's config dir."""
    import json

    from tlc_plugin_sdk.shared.config_store import CONFIG_ROOT

    root = CONFIG_ROOT / "sam3"
    root.mkdir(parents=True, exist_ok=True)
    (root / _HF_TOKEN_FILE).write_text(json.dumps({"hf_token": token}))


def ensure_hf_token_env() -> None:
    """Populate ``HF_TOKEN`` from the persisted file when the process env lacks it."""
    import json
    import os

    if os.environ.get("HF_TOKEN"):
        return
    from tlc_plugin_sdk.shared.config_store import CONFIG_ROOT

    path = CONFIG_ROOT / "sam3" / _HF_TOKEN_FILE
    try:
        token = str(json.loads(path.read_text()).get("hf_token", "") or "")
    except Exception:
        return
    if token:
        os.environ["HF_TOKEN"] = token
