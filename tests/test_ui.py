# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""What the page sends: no copy of the data it never makes, and the source check before the model."""

from __future__ import annotations

import re
from pathlib import Path

UI = (Path(__file__).resolve().parents[1] / "src" / "tlc_plugin_sam3" / "ui.html").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = UI.index(f"function {name}(")
    end = re.compile(r"^}\n", re.MULTILINE).search(UI, start)
    assert end is not None
    return UI[start : end.end()]


def test_the_alias_card_makes_no_copy_offer() -> None:
    assert '_tlcBindAliasAutoUpdate("sam3", "sam3-project-name", "sam3-folder", "", "", { copyOffer: false })' in UI


def test_the_page_never_asks_for_a_copy() -> None:
    assert not re.search(r"body\.alias_copy|alias_copy_\w+\s*:", UI)


def test_the_preview_checks_the_source_before_warming_the_model() -> None:
    preview = _function("sam3RunPreview")
    assert '"/api/plugins/sam3/check-source"' in preview
    check = preview.index("checkSource().then(")
    assert check < preview.index("_sam3EnsureHfToken().then(pollModel)")
    # The warm-up is started from the check's answer and from nowhere else.
    assert preview.count("_sam3EnsureHfToken()") == 1


def test_the_table_source_is_checked_against_the_run_target_on_bridges_that_can() -> None:
    check = _function("sam3CheckTableAgainstRunTarget")
    assert 'typeof PLUGIN_API.checkDataForRunTarget !== "function"' in check
    assert "PLUGIN_API.hostChecksTableInputs" in check
    assert 'typeof PLUGIN_API.onRunTargetChange === "function"' in UI
    assert "PLUGIN_API.onRunTargetChange(sam3CheckTableAgainstRunTarget)" in UI


def test_a_folder_run_sends_the_picked_folder_beside_the_alias_folder() -> None:
    # The Hub may rewrite `folder`; the picked folder lets the run keep subfolders under a parent alias.
    assert "body.alias_source_folder = alias.alias_source_folder || folder;" in UI


def test_only_the_gate_enables_preview_and_create() -> None:
    # PBI 19074: the buttons are enabled only by sam3Gate, which knows why they cannot run. A preview's
    # end re-enabled Preview with no labels left, and a label added mid-preview re-enabled it.
    assert not re.search(r"\.disabled\s*=\s*(true|false)", UI)
    assert "if (sam3PreviewBlocker(sameImage)) { sam3Gate(); return; }" in _function("sam3RunPreview")
    assert "if (sam3CreateBlocker()) { sam3Gate(); return; }" in _function("sam3CreateAndPredict")


def test_recalculate_same_needs_a_preview_of_the_current_source() -> None:
    assert "_sam3SourceKey() !== _sam3LastPreviewSource" in _function("sam3PreviewBlocker")
