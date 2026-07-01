# 3lc-plugin-sam3

The **SAM3 auto-label** plugin for the [3LC compute service](https://github.com/3lc-ai) —
auto-label images with SAM3: preview results, create tables, and run predictions with text prompts.

A standalone, venv-isolated plugin distribution, licensed **Apache-2.0**. The SAM3 model weights
are pulled at runtime and carry their own license, separate from this plugin code.

## How it's consumed

The host never installs this distribution into its own venv. It is delivered through any of the
three plugin Sources, all converging on the same out-of-process worker in a managed venv:

- **Folder Source (dev):** point the service at this repo's `src/`
  (`--plugin-dir ../3lc-plugin-sam3/src` or `TLC_COMPUTE_EXTERNAL_PLUGIN_DIRS`). Provisioning runs
  `uv sync --extra sam3` against this repo.
- **Index:** `3lc-plugin-sam3[sam3]==<ver>`.
- **GitHub:** `github:3lc-ai/3lc-plugin-sam3@v<ver>`.

The heavy stack (`torch`, `sam3`, `umap-learn`) lives behind the **`[sam3]` extra** named by
`runtime.provision_extra` in `src/tlc_plugin_sam3/plugin.toml` and is installed **only** into the
plugin's provisioned venv — never the host venv. The vendored BPE vocab
(`bpe_simple_vocab_16e6.txt.gz`) ships inside the package and is bundled into the wheel. The base
dependency is the SDK floor only.

## Dev setup

```bash
uv sync --extra sam3     # exactly what the host provisions into the plugin's venv
uvx --from 'ruff>=0.15,<0.16' ruff check .
```

To develop against a sibling `3lc-plugin-sdk` checkout, override its source **uncommitted**:

```toml
# pyproject.toml [tool.uv.sources]  (local dev only — do not commit)
3lc-plugin-sdk = { path = "../3lc-plugin-sdk", editable = true }
```

The plugin contract and author guide live in
[`3lc-plugin-sdk`](https://3lc-ai.github.io/3lc-plugin-sdk/).
