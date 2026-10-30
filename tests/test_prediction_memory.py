# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""Prediction releases dense per-image data while preserving the real metrics wire format."""

from __future__ import annotations

import gc
import sys
import threading
import types
import weakref
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image
from tlc_plugin_sdk import JobContext

import tlc_plugin_sam3


class _State(dict[str, Any]):
    pass


def _mask(image_index: int, instance: int) -> np.ndarray:
    mask = np.zeros((7, 11), dtype=np.uint8)
    mask[image_index : image_index + 3, instance + 2 : instance + 6] = 1
    return mask


def _predict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    counts: list[int],
    *,
    modality: str = "segmentation",
    cancel: bool = False,
) -> Any:
    import tlc
    import tlc_plugin_sdk.shared.images as images

    table = tlc.Table.from_dict(
        {"image": [f"image-{i}.png" for i in range(len(counts))]},
        project_name="memory-test",
        dataset_name="images",
        root_url=tmp_path,
    )
    retained: list[weakref.ReferenceType[Any]] = []
    call = 0
    cancel_event = threading.Event()
    runs = []
    original_init = tlc.init
    original_stack = np.stack

    def assert_released() -> None:
        gc.collect()
        assert not [ref() for ref in retained if ref() is not None], "previous image's dense data is still retained"
        retained.clear()

    def track(value: Any) -> Any:
        retained.append(weakref.ref(value))
        return value

    def read_image(*_args: Any) -> Image.Image:
        assert_released()
        return track(Image.new("RGB", (11, 7)))

    def predict(image: Image.Image, *_args: Any) -> tuple[dict[str, Any], _State]:
        nonlocal call
        idx = call
        call += 1
        n = counts[idx]
        state = track(_State(feature=track(np.arange(80, dtype=np.float32).reshape(10, 8) + idx * 100)))
        masks = [track(_mask(idx, j)) for j in range(n)]
        preds = {
            "masks": masks,
            "masks_tensor": track(np.zeros((n, 7, 11), dtype=np.float32)),
            "boxes": [[j, 1, j + 2, 4] for j in range(n)],
            "labels": [j % 2 for j in range(n)],
            "scores": [0.9 - j * 0.1 for j in range(n)],
        }
        if cancel:
            cancel_event.set()
        return preds, state

    def stack(*args: Any, **kwargs: Any) -> np.ndarray:
        return track(original_stack(*args, **kwargs))

    def reduce(embeddings: np.ndarray, dim: int) -> np.ndarray:
        assert_released()
        return embeddings[:, :dim]

    def init(**kwargs: Any) -> Any:
        run = original_init(**kwargs)
        runs.append(run)
        return run

    inference = types.ModuleType("tlc_plugin_sam3.inference")
    inference.predict_single_image_with_state = predict
    # Views of the large feature map deliberately test that only the small vectors survive.
    inference.get_image_embedding = lambda state: state["feature"][0, :4]
    inference.get_instance_embeddings = lambda state, masks: state["feature"][: len(masks), :4]
    inference.get_box_embeddings = lambda state, boxes, size: state["feature"][: len(boxes), :4]
    monkeypatch.setitem(sys.modules, "tlc_plugin_sam3.inference", inference)
    monkeypatch.setattr(np, "stack", stack)
    monkeypatch.setattr(images, "get_image_column", lambda table: "image")
    monkeypatch.setattr(images, "read_image_from_table", read_image)
    monkeypatch.setattr(tlc_plugin_sam3, "_read_labels_from_table", lambda table: ["fish", "net"])
    monkeypatch.setattr(tlc_plugin_sam3, "_read_modality_from_table", lambda table: modality)
    monkeypatch.setattr(tlc_plugin_sam3, "_reduce_embeddings", reduce)
    monkeypatch.setattr(tlc, "init", init)
    ctx = JobContext(
        "memory-test",
        {"table_url": str(table.url), "run_name": "prediction", "embedding_dim": 2},
        tmp_path,
        sink=lambda event: None,
        cancel_event=cancel_event,
    )
    tlc_plugin_sam3._run_predict(ctx, root_url=str(tmp_path))
    assert_released()
    assert call == (1 if cancel else len(counts))
    return runs[0]


@pytest.fixture(autouse=True)
def _close_run_session() -> Iterator[None]:
    import tlc

    yield
    tlc.close()


@pytest.mark.parametrize("counts", [[0, 2, 1], [0, 0]])
def test_segmentation_releases_dense_data_and_writes_roundtrip_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, counts: list[int]
) -> None:
    import tlc

    run = _predict(monkeypatch, tmp_path, counts)
    assert run.status == tlc.constants.RUN_STATUS_COMPLETED
    assert len(run.metrics_tables) == 1
    # Re-open the written table: this exercises the real declared schema and encoded-row passthrough.
    metrics = tlc.Table.from_url(run.metrics_tables[0].url)
    assert len(metrics) == len(counts)
    for i, n in enumerate(counts):
        row = metrics[i]
        seg = row["predicted_segmentations"]
        assert isinstance(seg, tlc.data_types.SegmentationMasks)
        assert (seg.image_width, seg.image_height) == (11, 7)
        if n:
            assert seg.masks.shape == (7, 11, n)
        else:
            # Core's empty RLE decoder returns an empty array; dimensions remain on the sample.
            assert seg.masks.size == 0
        for j in range(n):
            np.testing.assert_array_equal(seg.masks[:, :, j], _mask(i, j))
        if n:
            np.testing.assert_array_equal(seg.labels, [j % 2 for j in range(n)])
            np.testing.assert_allclose(seg.confidences, [0.9 - j * 0.1 for j in range(n)])
        else:
            assert seg.labels is None or len(seg.labels) == 0
            assert seg.confidences is None or len(seg.confidences) == 0
        expected_embeddings = np.asarray([[i * 100 + j * 8, i * 100 + j * 8 + 1] for j in range(n)])
        actual_embeddings = seg.per_instance_extras["instance_embedding"]
        np.testing.assert_array_equal(np.asarray(actual_embeddings).reshape(n, 2), expected_embeddings.reshape(n, 2))
        np.testing.assert_array_equal(row["image_embedding"], [i * 100, i * 100 + 1])


def test_bbox_metrics_and_separate_instance_embeddings_remain_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import tlc

    run = _predict(monkeypatch, tmp_path, [0, 2], modality="bbox")
    assert run.status == tlc.constants.RUN_STATUS_COMPLETED
    metrics = tlc.Table.from_url(run.metrics_tables[0].url)
    boxes = metrics[1]["predicted_bbs"]
    assert isinstance(boxes, tlc.data_types.BoundingBoxes2D)
    np.testing.assert_array_equal(boxes.bounding_boxes, [[0, 1, 2, 4], [1, 1, 3, 4]])
    np.testing.assert_array_equal(boxes.labels, [0, 1])
    np.testing.assert_allclose(boxes.confidences, [0.9, 0.8])
    assert metrics[0]["instance_embeddings"] == []
    np.testing.assert_array_equal(metrics[1]["instance_embeddings"], [[100, 101], [108, 109]])


def test_cancelled_prediction_releases_current_image_without_writing_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import tlc

    run = _predict(monkeypatch, tmp_path, [2, 1], cancel=True)
    assert run.status == tlc.constants.RUN_STATUS_CANCELLED
    assert not run.metrics_tables
