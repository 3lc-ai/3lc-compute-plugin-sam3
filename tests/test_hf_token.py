# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""Where the Hugging Face token comes from: the chosen Connection, the worker's own, the legacy file.

The token is a SECRET Connection the person chooses in the Hub. The host grants it to jobs and to
the routes the manifest lists under ``credential_routes``; the SDK binds it, and the model download
receives it explicitly. The token file the retired ``/set-hf-token`` wrote is read for one release
when nothing else is there, and never written.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest
import tomllib

from tlc_plugin_sam3 import hf_token, routes

SECRET = "hf_" + "c" * 34
LEGACY = "hf_" + "l" * 34
MANIFEST = Path(__file__).resolve().parent.parent / "src" / "tlc_plugin_sam3" / "plugin.toml"


@pytest.fixture
def config_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import tlc_plugin_sdk.shared.config_store as store

    monkeypatch.setattr(store, "CONFIG_ROOT", tmp_path)
    monkeypatch.setattr(hf_token, "_WORKER_TOKEN", "")
    return tmp_path


def _write_legacy(root: Path, token: str = LEGACY) -> None:
    (root / "sam3").mkdir(parents=True, exist_ok=True)
    (root / "sam3" / "hf-token.json").write_text(json.dumps({"hf_token": token}))


def _bound(provider: str = "huggingface", secret: str = SECRET) -> Any:
    connections = pytest.importorskip("tlc_plugin_sdk.connections")
    if not hasattr(connections, "bound_credential"):
        pytest.skip("this SDK binds no SECRET Connections")
    token = connections.SecretToken(provider=provider, secret=secret, connection_id="c-1")
    return connections.bound_credential(token)


def test_nothing_anywhere_is_none(config_root: Path) -> None:
    assert hf_token.resolve() == ("", "none")


def test_the_legacy_file_is_read_when_nothing_else_is_there(config_root: Path) -> None:
    _write_legacy(config_root)
    assert hf_token.resolve() == (LEGACY, "legacy-file")
    assert hf_token.source() == "legacy-file"


def test_a_broken_legacy_file_is_no_token(config_root: Path) -> None:
    (config_root / "sam3").mkdir()
    (config_root / "sam3" / "hf-token.json").write_text("not json")
    assert hf_token.resolve() == ("", "none")


def test_the_worker_s_own_token_wins_over_the_legacy_file(config_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_legacy(config_root)
    monkeypatch.setattr(hf_token, "_WORKER_TOKEN", "hf_operator")
    assert hf_token.resolve() == ("hf_operator", "environment")


def test_hf_token_set_later_in_the_process_is_not_the_worker_s(
    config_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The SDK sets HF_TOKEN process-wide while another job holds a Connection: never borrow it."""
    monkeypatch.setenv("HF_TOKEN", "hf_someone_elses")
    assert hf_token.resolve() == ("", "none")


def test_the_chosen_connection_wins(config_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_legacy(config_root)
    monkeypatch.setattr(hf_token, "_WORKER_TOKEN", "hf_operator")
    with _bound():
        assert hf_token.resolve() == (SECRET, "connection")
    assert hf_token.resolve() == ("hf_operator", "environment"), "only inside the job or request"


def test_a_connection_for_another_service_is_not_a_hugging_face_token(config_root: Path) -> None:
    with _bound(provider="wandb"):
        assert hf_token.resolve() == ("", "none")


def test_the_manifest_declares_the_service_and_the_routes_that_download() -> None:
    runtime = tomllib.loads(MANIFEST.read_text())["runtime"]
    assert runtime["credentials"] == [{"service": hf_token.SERVICE, "required": True}]
    assert runtime["credential_routes"] == ["/preview", "/model-warmup", "/model-status"]
    paths = {path for handler in routes.get_route_handlers() for path in handler.paths}
    assert set(runtime["credential_routes"]) <= paths, "every credential route exists"


def test_the_token_routes_are_retired() -> None:
    paths = {path for handler in routes.get_route_handlers() for path in handler.paths}
    assert "/set-hf-token" not in paths
    assert "/hf-token-status" not in paths
    import tlc_plugin_sam3.config_store as store

    assert not hasattr(store, "persist_hf_token"), "nothing writes the token file any more"


def _inference(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Import ``inference`` without the GPU stack (this plugin's own venv has no GPU extra)."""
    for name in ("numpy", "torch", "torch.nn", "torch.nn.functional", "PIL", "PIL.Image", "PIL.ImageDraw"):
        try:
            __import__(name)
        except ImportError:
            parts = name.split(".")
            for i in range(len(parts)):
                monkeypatch.setitem(
                    sys.modules,
                    ".".join(parts[: i + 1]),
                    sys.modules.get(".".join(parts[: i + 1])) or types.ModuleType(".".join(parts[: i + 1])),
                )
            if len(parts) > 1:
                setattr(sys.modules[".".join(parts[:-1])], parts[-1], sys.modules[name])
    sys.modules.pop("tlc_plugin_sam3.inference", None)
    return __import__("tlc_plugin_sam3.inference", fromlist=["*"])


def test_the_download_gets_the_token_explicitly_and_never_reads_hf_token(monkeypatch: pytest.MonkeyPatch) -> None:
    inference = _inference(monkeypatch)
    calls: list[dict[str, Any]] = []
    hub = types.ModuleType("huggingface_hub")

    def fake_download(**kwargs: Any) -> str:
        calls.append(kwargs)
        return "/cache/" + kwargs["filename"]

    vars(hub)["hf_hub_download"] = fake_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    assert inference._download_checkpoint(SECRET) == "/cache/sam3.pt"
    assert [c["token"] for c in calls] == [SECRET, SECRET]
    assert [c["filename"] for c in calls] == ["config.json", "sam3.pt"]
    calls.clear()
    inference._download_checkpoint("")
    assert [c["token"] for c in calls] == [False, False], "no token is sent rather than HF_TOKEN read"


def test_the_warmup_thread_gets_the_request_s_token(monkeypatch: pytest.MonkeyPatch) -> None:
    inference = _inference(monkeypatch)
    seen: list[Any] = []
    monkeypatch.setattr(inference, "_ensure_model", lambda device, token=None: seen.append((device, token)))
    inference._model = None
    inference._warmup_state.update(state="cold", detail="")
    inference.warmup_model("cpu", token=SECRET)
    for _ in range(200):
        if seen:
            break
        __import__("time").sleep(0.01)
    assert seen == [("cpu", SECRET)]


def test_model_status_says_where_the_token_comes_from(config_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inference = _inference(monkeypatch)
    monkeypatch.setattr(inference, "_model", None)
    handler = next(h for h in routes.get_route_handlers() if "/model-status" in h.paths)
    fn = handler.fn
    assert fn()["hf_token"] == "none"
    _write_legacy(config_root)
    assert fn()["hf_token"] == "legacy-file"
    assert LEGACY not in json.dumps(fn()), "never the token itself"


def test_a_credential_route_sees_the_bound_connection(config_root: Path) -> None:
    """End to end through the SDK's request middleware."""
    from litestar import Litestar
    from litestar.testing import TestClient
    from tlc_plugin_sdk import connections

    handlers = [h for h in routes.get_route_handlers() if "/model-status" in h.paths]
    app = Litestar(route_handlers=handlers, middleware=[connections.credential_middleware])
    token = connections.SecretToken(provider="huggingface", secret=SECRET, connection_id="c-1")
    with TestClient(app) as client:
        bound = client.get(
            "/model-status", headers={connections.BOUND_CREDENTIAL_HEADER: connections.encode_credential(token)}
        )
        assert bound.status_code == 200, bound.text
        assert bound.json()["hf_token"] == "connection"
        assert SECRET not in bound.text
        assert client.get("/model-status").json()["hf_token"] == "none"
