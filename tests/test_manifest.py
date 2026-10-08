# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""The manifest declares the body keys that carry the data SAM3 reads, and routes its checks to the node."""

from __future__ import annotations

import re
from pathlib import Path

import tomllib

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "tlc_plugin_sam3"
RUNTIME = tomllib.loads((PACKAGE / "plugin.toml").read_text(encoding="utf-8"))["runtime"]
UI = (PACKAGE / "ui.html").read_text(encoding="utf-8")


def test_data_inputs_are_the_keys_that_name_what_is_read() -> None:
    assert RUNTIME["data_inputs"] == ["folder", "source_table_url", "table_url"]


def test_every_declared_input_is_a_key_the_page_sends() -> None:
    for key in RUNTIME["data_inputs"]:
        assert re.search(rf"\bbody\.{key}\s*=|\{{\s*{key}\s*:", UI), key


def test_the_durable_alias_folder_is_not_an_input() -> None:
    # The host may rewrite an input for the run; the persisted alias must keep the durable location.
    assert "alias_folder" not in RUNTIME["data_inputs"]


def test_the_source_check_runs_where_the_preview_reads() -> None:
    assert {"/preview", "/check-source"} <= set(RUNTIME["node_routes"])
