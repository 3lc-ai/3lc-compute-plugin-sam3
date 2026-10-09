# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""Where SAM3's Hugging Face token comes from, for one job or one request.

SAM 3's weights are gated on Hugging Face, so the model download needs a token. In order:

1. **The Connection the person chose in the Hub** (``PLUGIN_API.chooseCredential("huggingface")``
   in the fragment). The host obtains its value for this plugin and the SDK binds it: around
   ``run_job`` for a job, and around the handler for a call to one of the manifest's
   ``credential_routes``. :func:`tlc_plugin_sdk.connections.current_credential` then returns it in
   that job's or request's context.
2. **``HF_TOKEN`` in the worker's environment when it started** (an operator's own).
3. **The legacy token file**, for one release only: ``hf-token.json`` in the plugin's config dir,
   which the retired ``/set-hf-token`` route used to write. Read when neither of the above is
   there; never written any more. The fragment says "using the legacy token file — choose a
   Connection".

Else there is none, and the gated download fails with Hugging Face's own 401.

The token is handed to the download explicitly (``token=``), never read back from ``HF_TOKEN`` at
download time: the environment is shared by every job and request in the worker, so a token placed
there would reach another person's call, and the warm-up loads the model on a thread that outlives
the request that started it. The SDK binds a Connection's value only in the job's or request's
context, never in ``os.environ``. The worker's own variable is read once, when this module is
imported with the plugin.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

SERVICE = "huggingface"
"""The credential service this plugin's manifest declares (``[runtime] credentials``)."""

LEGACY_TOKEN_FILE = "hf-token.json"

TokenSource = Literal["connection", "legacy-file", "environment", "none"]

# Captured at plugin import, before any job or request can bind a Connection's value into it.
_WORKER_TOKEN = os.environ.get("HF_TOKEN", "").strip()


def _bound_token() -> str:
    """The value of the Connection bound to the current job or request, or ``""``."""
    try:
        from tlc_plugin_sdk.connections import current_credential
    except ImportError:  # an SDK without Connections
        return ""
    # A job: the SDK binds the run's granted value around run_job (SDK 0.5 secret leg).
    # A credential_routes request: bound by the SDK's request middleware, which reads the host's
    # X-TLC-Bound-Credential header.
    credential = current_credential()
    if getattr(credential, "provider", "") != SERVICE:
        return ""
    secret = getattr(credential, "secret", "")
    return secret if isinstance(secret, str) else ""


def legacy_token_path() -> Path:
    """Where the retired ``/set-hf-token`` route saved the token."""
    from tlc_plugin_sdk.shared.config_store import config_root

    return config_root() / "sam3" / LEGACY_TOKEN_FILE


def _legacy_token() -> str:
    from tlc_plugin_sdk.shared.config_store import ConfigRootUnavailable

    try:
        data = json.loads(legacy_token_path().read_text())
    except (OSError, ValueError, ConfigRootUnavailable):
        return ""
    token = data.get("hf_token", "") if isinstance(data, dict) else ""
    return token.strip() if isinstance(token, str) else ""


def resolve() -> tuple[str, TokenSource]:
    """The token for the current job or request, and where it came from.

    Returns:
        ``(token, source)``; ``token`` is ``""`` when ``source`` is ``"none"``.
    """
    token = _bound_token()
    if token:
        return token, "connection"
    if _WORKER_TOKEN:
        return _WORKER_TOKEN, "environment"
    token = _legacy_token()
    if token:
        return token, "legacy-file"
    return "", "none"


def source() -> TokenSource:
    """Where the current job's or request's token comes from (never the token itself)."""
    return resolve()[1]
