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
