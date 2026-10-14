# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""Find the images a SAM3 preview or job reads, before anything expensive happens.

A folder or table that the worker cannot read must fail in seconds, on the worker that would read
it, with a message that names that worker. Without this a preview first downloads the model
(minutes on a fresh machine) and only then reports "No images found", and a run on a GPU node
reports the same words for a folder that only exists on the person's own computer.

Nothing here imports torch: the checks run in the create step and in the cheap ``/check-source``
route, neither of which needs the model.
"""

from __future__ import annotations

import os
import random
import socket
from typing import Any

from tlc_plugin_sdk.shared.url_utils import normalize_url


class SourceError(ValueError):
    """The image source cannot be read here; the message is for the person."""


def worker_name() -> str:
    """Name the machine this worker runs on, for messages about where data was looked for."""
    try:
        return socket.gethostname() or "this worker"
    except OSError:
        return "this worker"


def _local_folder(folder: str) -> str | None:
    """The local directory *folder* names, or ``None`` when it is a URL (or an alias to one)."""
    path = folder
    if "<" in path:
        import tlc

        path = str(tlc.Url(path).expand_aliases(allow_unexpanded=True))
    if path.startswith("file://"):
        path = path[len("file://") :]
    if "://" in path:
        return None
    return os.path.expanduser(path)


def images_in_folder(folder: str, max_count: int = 10000) -> list[str]:
    """List the images under *folder*, or say why there are none on this worker.

    Args:
        folder: Folder path or URL, as the run body carries it (``~`` and aliases allowed).
        max_count: Maximum number of paths to return.

    Returns:
        The sorted, non-empty list of image paths/URLs.

    Raises:
        SourceError: When no folder is given, the folder is not on this worker, it cannot be
            listed (an unknown alias, missing credentials), or it holds no images.

    """
    from tlc_plugin_sdk.shared.images import list_image_urls

    folder = normalize_url(str(folder or "").strip())
    if not folder:
        msg = "No image folder given"
        raise SourceError(msg)
    where = worker_name()
    try:
        images = list_image_urls(folder, max_count)
    except ValueError as exc:  # an alias this worker does not know
        msg = f"Cannot read {folder} on {where}: {exc}"
        raise SourceError(msg) from exc
    except OSError as exc:  # the folder exists but cannot be listed (credentials, region, permissions)
        msg = f"Cannot list {folder} on {where}: {exc}"
        raise SourceError(msg) from exc
    if images:
        return images
    # The SDK lists a missing folder as empty; the two need different answers.
    local = _local_folder(folder)
    if local is not None and not os.path.isdir(local):
        msg = f"Folder not found on {where}: {folder}"
        raise SourceError(msg)
    msg = f"No images found in {folder} on {where}"
    raise SourceError(msg)


def check_source(data: dict[str, Any]) -> dict[str, Any]:
    """Check that a preview's folder or table has images here, without loading the model.

    Args:
        data: The preview body: ``folder`` or ``table_url``.

    Returns:
        ``{"ok": True, "count": n, "image_path": <a random image>}``, or ``{"error": message}``.

    """
    folder = str(data.get("folder", "") or "").strip()
    table_url = str(data.get("table_url", "") or "").strip()
    try:
        if table_url:
            return {"ok": True, **_pick_from_table(table_url)}
        if folder:
            images = images_in_folder(folder)
            return {"ok": True, "count": len(images), "image_path": random.choice(images)}
    except SourceError as exc:
        return {"error": str(exc)}
    return {"error": "Either folder or table_url is required"}


def _pick_from_table(table_url: str) -> dict[str, Any]:
    """Count a table's rows and pick one image, absolutized so it round-trips into a preview."""
    where = worker_name()
    try:
        import tlc
        from tlc_plugin_sdk.shared.images import get_image_column, resolve_image_url

        table = tlc.Table.from_url(normalize_url(table_url))
        count = len(table)
        if count == 0:
            msg = f"Table {table_url} has no rows"
            raise SourceError(msg)
        column = get_image_column(table)
        row = table.table_rows[random.randint(0, count - 1)]
        image_path = resolve_image_url(str(row[column]), table.url).to_str()
    except SourceError:
        raise
    except Exception as exc:
        msg = f"Cannot read table {table_url} on {where}: {exc}"
        raise SourceError(msg) from exc
    return {"count": count, "image_path": image_path}
