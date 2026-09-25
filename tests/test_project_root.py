# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""Runs, tables and aliases are created under the project root the job carries (``ctx.project_root_url``)."""

from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from typing import Any

import pytest
from tlc_plugin_sdk import JobContext

import tlc_plugin_sam3
from tlc_plugin_sam3 import SAM3Plugin


class _Stop(Exception):
    """Raised by the patched ``tlc.init`` so predict stops right after creating the run."""


class _NoRootContext(JobContext):
    """A context whose worker cannot name a root (no stamped key, no ``tlc`` root)."""

    @property
    def project_root_url(self) -> str:
        return ""


def _ctx(tmp_path: Path, params: dict[str, Any], cls: type[JobContext] = JobContext) -> JobContext:
    return cls("j1", params, tmp_path, sink=lambda _event: None, cancel_event=threading.Event())


@pytest.fixture
def stubs(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Stand in for the model, the tables and tlc's writers; record what the writers were asked."""
    import tlc
    import tlc_plugin_sdk.shared.aliases as aliases
    import tlc_plugin_sdk.shared.images as images

    seen: dict[str, Any] = {}

    # ``inference`` imports torch at module level; this plugin's own venv has no GPU extra.
    inference = types.ModuleType("tlc_plugin_sam3.inference")
    vars(inference)["list_images_in_folder"] = lambda folder: ["/data/a.jpg"]
    for name in (
        "get_box_embeddings",
        "get_image_embedding",
        "get_instance_embeddings",
        "predict_single_image_with_state",
    ):
        vars(inference)[name] = lambda *args: None
    monkeypatch.setitem(sys.modules, "tlc_plugin_sam3.inference", inference)

    class FakeWriter:
        def __init__(self, **kwargs: Any) -> None:
            seen["writer"] = kwargs

        def add_batch(self, batch: dict[str, Any]) -> None:
            pass

        def finalize(self) -> Any:
            return types.SimpleNamespace(url="s3://bucket/root/proj/datasets/train/tables/initial")

    def fake_init(**kwargs: Any) -> Any:
        seen["init"] = kwargs
        raise _Stop

    monkeypatch.setattr("tlc_plugin_sam3.config_store.ensure_hf_token_env", lambda: None)
    monkeypatch.setattr(tlc, "TableWriter", FakeWriter)
    monkeypatch.setattr(tlc, "init", fake_init)

    class FakeTable(list[Any]):
        project_name = "proj"

    monkeypatch.setattr(tlc.Table, "from_url", staticmethod(lambda url: FakeTable()))
    monkeypatch.setattr(images, "read_image_size", lambda path: (10, 10))
    monkeypatch.setattr(images, "get_image_column", lambda table: "image")
    monkeypatch.setattr(aliases, "register_alias", lambda **kwargs: seen.setdefault("alias", kwargs))
    monkeypatch.setattr(tlc_plugin_sam3, "_read_labels_from_table", lambda table: ["cat"])
    monkeypatch.setattr(tlc_plugin_sam3, "_read_modality_from_table", lambda table: "bbox")
    return seen


_CREATE = {"mode": "create_table", "folder": "/data", "labels": ["cat"], "modality": "bbox", "project_name": "proj"}


def test_create_table_writes_table_and_alias_under_the_job_root(tmp_path: Path, stubs: dict[str, Any]) -> None:
    SAM3Plugin().run_job(_ctx(tmp_path, {**_CREATE, "project_root_url": "s3://bucket/root/"}))
    assert stubs["writer"]["root_url"] == "s3://bucket/root"
    assert stubs["alias"]["root_url"] == "s3://bucket/root"


def test_predict_creates_the_run_under_the_job_root(tmp_path: Path, stubs: dict[str, Any]) -> None:
    with pytest.raises(_Stop):
        SAM3Plugin().run_job(_ctx(tmp_path, {"mode": "predict", "table_url": "s3://t", "project_root_url": "s3://r"}))
    assert stubs["init"]["root_url"] == "s3://r"
    assert stubs["init"]["project_name"] == "proj"


def test_create_and_predict_share_the_job_root(tmp_path: Path, stubs: dict[str, Any]) -> None:
    with pytest.raises(_Stop):
        SAM3Plugin().run_job(_ctx(tmp_path, {**_CREATE, "mode": "create_and_predict", "project_root_url": "s3://r"}))
    assert stubs["writer"]["root_url"] == "s3://r"
    assert stubs["init"]["root_url"] == "s3://r"


def test_without_a_root_the_tlc_default_root_is_kept(tmp_path: Path, stubs: dict[str, Any]) -> None:
    with pytest.raises(_Stop):
        SAM3Plugin().run_job(_ctx(tmp_path, {**_CREATE, "mode": "create_and_predict"}, _NoRootContext))
    assert stubs["writer"]["root_url"] is None
    assert stubs["alias"]["root_url"] is None
    assert stubs["init"]["root_url"] is None
