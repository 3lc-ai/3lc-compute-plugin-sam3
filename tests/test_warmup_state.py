# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""The warmup state machine — what the page polls while a multi-GB model loads."""

from __future__ import annotations

import sys
import types
from typing import Any


def _stub_missing(*names: str) -> None:
    """Stand in for the GPU stack when it is not installed.

    The state machine under test never touches torch — but ``inference`` imports it at module
    level, and this plugin's own venv has no GPU extra, so without this the test could only run
    on a node.
    """
    for name in names:
        try:
            __import__(name)
        except ImportError:
            parts = name.split(".")
            for i in range(len(parts)):
                path = ".".join(parts[: i + 1])
                sys.modules.setdefault(path, types.ModuleType(path))
            parent = sys.modules[".".join(parts[:-1])] if len(parts) > 1 else None
            if parent is not None:
                setattr(parent, parts[-1], sys.modules[name])


def _inference(monkeypatch: Any, loader: Any) -> Any:
    """Import ``inference`` with its heavy model load replaced by *loader*."""
    _stub_missing("numpy", "torch", "torch.nn", "torch.nn.functional", "PIL", "PIL.Image", "PIL.ImageDraw")
    for name in list(sys.modules):
        if name.startswith("tlc_plugin_sam3.inference"):
            del sys.modules[name]
    module = __import__("tlc_plugin_sam3.inference", fromlist=["*"])
    monkeypatch.setattr(module, "_ensure_model", loader)
    module._model = None
    module._warmup_state.update(state="idle", detail="")
    return module


def test_a_permanent_failure_is_reported_not_retried_behind_the_poll(monkeypatch: Any) -> None:
    """A gated model the token cannot read fails the same way every time. The page polls every five
    seconds; if each poll starts a fresh attempt, the caller only ever sees "warming" and waits out
    the timeout — which is exactly what happened on a GPU node whose HF token had not reached it."""
    calls: list[str] = []

    def loader(device: str) -> None:
        calls.append(device)
        msg = "401 Client Error: access to facebook/sam3 is restricted"
        raise RuntimeError(msg)

    inference = _inference(monkeypatch, loader)

    first = inference.warmup_model("cuda")
    # A load that fails instantly may already have failed by the time the call returns; a real one
    # is still "warming". Either is fine — what matters is what the polls after it see.
    assert first["state"] in {"warming", "failed"}
    for _ in range(200):  # the load thread runs to its failure
        if inference._warmup_state["state"] != "warming":
            break
        __import__("time").sleep(0.01)
    assert inference._warmup_state["state"] == "failed"
    assert "401" in inference._warmup_state["detail"]

    # A poll looks; it does not start the failing load again.
    polled = inference.warmup_model("cuda", retry=False)
    assert polled["state"] == "failed" and "401" in polled["detail"]
    assert len(calls) == 1

    # A fresh user action does retry — otherwise fixing the token would need a worker restart.
    inference.warmup_model("cuda", retry=True)
    for _ in range(200):
        if inference._warmup_state["state"] != "warming":
            break
        __import__("time").sleep(0.01)
    assert len(calls) == 2
