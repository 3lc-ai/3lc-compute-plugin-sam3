# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""Build/check the unchanged self-contained UI from maintained source assets."""

import sys
from pathlib import Path

from tlc_plugin_sdk.ui_bundle import build_fragment, form_values

from tlc_plugin_sam3.form_fields import FIELDS

package = Path(__file__).resolve().parents[1] / "src/tlc_plugin_sam3"
values = form_values(FIELDS)
values["field:confidence.display"] = format(next(f["default"] for f in FIELDS if f["id"] == "confidence"), ".2f")
build_fragment(package / "ui", package / "ui.html", check="--check" in sys.argv, values=values)
