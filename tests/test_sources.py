# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""A missing or empty image source fails fast, names the worker, and never loads the model."""

from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from typing import Any

import pytest
from tlc_plugin_sdk import JobContext, JobFailed

from tlc_plugin_sam3 import SAM3Plugin, sources


@pytest.fixture(autouse=True)
def _host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sources, "worker_name", lambda: "gpu-node-1")


@pytest.fixture
def no_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace ``inference`` (it imports torch) with a module whose every use fails the test."""

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("the model was used before the image source was checked")

    inference = types.ModuleType("tlc_plugin_sam3.inference")
    for name in (
        "get_box_embeddings",
        "get_image_embedding",
        "get_instance_embeddings",
        "predict_single_image",
        "predict_single_image_with_state",
        "render_preview",
        "warmup_model",
    ):
        vars(inference)[name] = _boom
    monkeypatch.setitem(sys.modules, "tlc_plugin_sam3.inference", inference)


def test_a_folder_that_is_not_on_this_worker_says_so(tmp_path: Path) -> None:
    missing = tmp_path / "bra"
    with pytest.raises(sources.SourceError, match=r"^Folder not found on gpu-node-1: .*bra$"):
        sources.images_in_folder(str(missing))


def test_an_empty_folder_is_reported_as_empty_with_the_worker(tmp_path: Path) -> None:
    with pytest.raises(sources.SourceError, match=r"^No images found in .* on gpu-node-1$"):
        sources.images_in_folder(str(tmp_path))


def test_a_folder_with_images_lists_them(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"")
    (tmp_path / "notes.txt").write_text("not an image")
    assert [Path(p).name for p in sources.images_in_folder(str(tmp_path))] == ["a.jpg"]


def test_an_unknown_alias_names_the_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    import tlc_plugin_sdk.shared.images as images

    def _unknown(folder: str, max_count: int = 10000) -> list[str]:
        msg = "could not expand alias <HUBBALLOONS>"
        raise ValueError(msg)

    monkeypatch.setattr(images, "list_image_urls", _unknown)
    with pytest.raises(sources.SourceError, match=r"Cannot read <HUBBALLOONS>/x on gpu-node-1: .*HUBBALLOONS"):
        sources.images_in_folder("<HUBBALLOONS>/x")


def test_a_bucket_prefix_with_nothing_under_it_is_not_called_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import tlc_plugin_sdk.shared.images as images

    monkeypatch.setattr(images, "list_image_urls", lambda folder, max_count=10000: [])
    with pytest.raises(sources.SourceError, match=r"^No images found in s3://b/imgs on gpu-node-1$"):
        sources.images_in_folder("s3://b/imgs")


def test_check_source_answers_with_an_image_or_the_reason(tmp_path: Path) -> None:
    assert sources.check_source({"folder": str(tmp_path / "nope")}) == {
        "error": f"Folder not found on gpu-node-1: {tmp_path / 'nope'}"
    }
    (tmp_path / "a.png").write_bytes(b"")
    result = sources.check_source({"folder": str(tmp_path)})
    assert result["ok"] is True
    assert result["count"] == 1
    assert result["image_path"].endswith("a.png")
    assert "error" in sources.check_source({})


def test_the_preview_reports_a_missing_folder_without_the_model(tmp_path: Path, no_model: None) -> None:
    from tlc_plugin_sam3.routes import _run_preview

    result = _run_preview({"folder": str(tmp_path / "bra"), "labels": ["cat"]})
    assert result == {"error": f"Folder not found on gpu-node-1: {tmp_path / 'bra'}"}


def test_the_job_fails_on_a_missing_folder_before_any_table_or_model(
    tmp_path: Path, no_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tlc

    def _no_writer(**_kwargs: Any) -> Any:
        pytest.fail("a table was started for a folder that is not there")

    monkeypatch.setattr(tlc, "TableWriter", _no_writer)
    params = {
        "mode": "create_and_predict",
        "folder": str(tmp_path / "bra"),
        "labels": ["cat"],
        "modality": "bbox",
        "project_name": "proj",
    }
    ctx = JobContext("j1", params, tmp_path, sink=lambda _event: None, cancel_event=threading.Event())
    with pytest.raises(JobFailed, match="Folder not found on gpu-node-1"):
        SAM3Plugin().run_job(ctx)


def test_predict_on_an_empty_table_fails_before_the_run_and_the_model(
    tmp_path: Path, no_model: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tlc

    class EmptyTable(list[Any]):
        project_name = "proj"

    def _no_run(**_kwargs: Any) -> Any:
        pytest.fail("a run was created for an empty table")

    monkeypatch.setattr(tlc.Table, "from_url", staticmethod(lambda url: EmptyTable()))
    monkeypatch.setattr(tlc, "init", _no_run)
    import tlc_plugin_sdk.shared.images as images

    monkeypatch.setattr(images, "get_image_column", lambda table: "image")
    ctx = JobContext(
        "j1", {"mode": "predict", "table_url": "s3://t"}, tmp_path, sink=lambda _e: None, cancel_event=threading.Event()
    )
    with pytest.raises(JobFailed, match="has no rows"):
        SAM3Plugin().run_job(ctx)
