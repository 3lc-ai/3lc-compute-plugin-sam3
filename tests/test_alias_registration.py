# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""A folder source's alias is registered before the rows, from the folder read, to the durable folder."""

from __future__ import annotations

import threading
import types
from pathlib import Path
from typing import Any

import pytest
from tlc_plugin_sdk import JobContext

from tlc_plugin_sam3 import SAM3Plugin


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    """Record, in order, the alias registration and what the table writer is asked to do."""
    import tlc
    import tlc_plugin_sdk.shared.aliases as aliases
    import tlc_plugin_sdk.shared.images as images

    seen: list[tuple[str, Any]] = []

    class FakeWriter:
        def __init__(self, **kwargs: Any) -> None:
            seen.append(("writer", kwargs))

        def add_batch(self, batch: dict[str, Any]) -> None:
            seen.append(("rows", batch["image"]))

        def finalize(self) -> Any:
            seen.append(("finalize", None))
            return types.SimpleNamespace(url="s3://b/root/proj/datasets/train/tables/initial")

    def fake_register(**kwargs: Any) -> dict[str, Any]:
        seen.append(("alias", kwargs))
        return {"token": kwargs["alias_token"], "persisted": kwargs.get("remote_path") or kwargs["image_folder"]}

    def no_overrides(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("the plugin applied _alias_overrides itself; the SDK worker does that around run_job")

    monkeypatch.setattr(tlc, "TableWriter", FakeWriter)
    monkeypatch.setattr(images, "list_image_urls", lambda folder, max_count=10000: [f"{folder}/a.jpg"])
    monkeypatch.setattr(images, "read_image_size", lambda path: (10, 10))
    monkeypatch.setattr(aliases, "register_alias", fake_register)
    monkeypatch.setattr(aliases, "apply_alias_overrides", no_overrides)
    return seen


def _run(tmp_path: Path, **params: Any) -> None:
    body = {
        "mode": "create_table",
        "labels": ["cat"],
        "modality": "bbox",
        "project_name": "proj",
        "project_root_url": "s3://b/root",
        **params,
    }
    ctx = JobContext("j1", body, tmp_path, sink=lambda _event: None, cancel_event=threading.Event())
    SAM3Plugin().run_job(ctx)


def _alias(events: list[tuple[str, Any]]) -> dict[str, Any]:
    calls = [kwargs for name, kwargs in events if name == "alias"]
    assert len(calls) == 1
    return calls[0]


def test_the_alias_is_registered_before_any_row_is_written(tmp_path: Path, events: list[tuple[str, Any]]) -> None:
    _run(tmp_path, folder="s3://b/imgs")
    order = [name for name, _ in events]
    assert order.index("alias") < order.index("rows") < order.index("finalize")


def test_a_folder_read_in_place_is_the_alias(tmp_path: Path, events: list[tuple[str, Any]]) -> None:
    _run(tmp_path, folder="s3://b/imgs", alias_folder="s3://b/imgs/", alias_token="IMGS")
    alias = _alias(events)
    assert alias["image_folder"] == "s3://b/imgs"
    assert alias["remote_path"] is None
    assert alias["alias_token"] == "IMGS"
    assert alias["root_url"] == "s3://b/root"


def test_a_folder_staged_on_a_node_keeps_the_durable_folder_as_the_alias(
    tmp_path: Path, events: list[tuple[str, Any]]
) -> None:
    # The host rewrote ``folder`` to the node's copy; ``alias_folder`` is where the data lives.
    _run(tmp_path, folder="/srv/3lc/stage/imgs-1a2b", alias_folder="s3://b/imgs")
    alias = _alias(events)
    assert alias["image_folder"] == "/srv/3lc/stage/imgs-1a2b"  # the rows are written from here
    assert alias["remote_path"] == "s3://b/imgs"  # every reader of the project resolves to this


def test_without_an_alias_folder_the_folder_read_is_the_alias(tmp_path: Path, events: list[tuple[str, Any]]) -> None:
    _run(tmp_path, folder="s3://b/imgs")
    alias = _alias(events)
    assert alias["image_folder"] == "s3://b/imgs"
    assert alias["remote_path"] is None
    assert alias["alias_token"] == "PROJ"


def test_a_table_source_registers_no_alias(
    tmp_path: Path, events: list[tuple[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    import tlc
    import tlc_plugin_sdk.shared.images as images

    monkeypatch.setattr(tlc.Table, "from_url", staticmethod(lambda url: object()))
    monkeypatch.setattr(images, "get_image_column", lambda table: "image")
    monkeypatch.setattr(images, "get_image_paths", lambda table, column: ["s3://b/imgs/a.jpg"])
    _run(tmp_path, source_table_url="s3://b/root/proj/datasets/train/tables/t0")
    assert [name for name, _ in events if name == "alias"] == []


def test_alias_overrides_in_the_body_are_left_to_the_worker(tmp_path: Path, events: list[tuple[str, Any]]) -> None:
    overrides = {"enabled": True, "overrides": [{"token": "IMGS", "path": "/srv/3lc/stage/imgs"}]}
    _run(tmp_path, folder="s3://b/imgs", _alias_overrides=overrides)
    assert any(name == "finalize" for name, _ in events)
