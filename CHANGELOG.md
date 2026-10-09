# Changelog

All notable changes to `3lc-compute-plugin-sam3` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

#### Data movement

- The folder alias card is hidden for table inputs, whose aliases already belong to their source project.

- The manifest declares the data SAM3 reads: `[runtime] data_inputs = ["folder", "source_table_url",
  "table_url"]`. A Hub that reads it plans that data for a run (stream it, copy it to the GPU node,
  or use a path already on the node) and refuses a folder that only exists on the person's own
  computer, also for the node routes `/preview` and `/check-source`. Older hosts ignore the key.
- A table source is checked against the Hub's "Run on:" target when it is picked and when the
  target changes (`PLUGIN_API.checkDataForRunTarget` / `onRunTargetChange`). A table a GPU node
  cannot read is flagged under the field before the run is submitted. A Hub that annotates table
  inputs itself (`hostChecksTableInputs`), or one without the API, shows no second note.
- The create step no longer applies `_alias_overrides` itself; the SDK worker applies them around
  every job.
- A preview looks for its images before it loads the model. The new `POST /check-source` node route
  runs on the worker that will read the images and answers in seconds. Before, a preview on a GPU
  node downloaded the model (minutes on a fresh node) and only then reported "No images found".
  A worker without the route (an older build on a node) skips the check.
- A folder that is not on the worker reading it is reported as "Folder not found on <machine>",
  apart from an empty folder ("No images found in … on <machine>"). An alias the worker does not
  know, or a folder it cannot list, names the machine too. The create step checks the folder
  before it starts a table or imports the model, and predict fails on a table with no rows before
  it creates a run.
- A folder source's URL alias is registered before the table's rows are written, not after.
  Registered afterwards, the first table a worker wrote kept absolute image paths.
- The persisted alias points at the durable folder (`alias_folder`), not at the folder this run
  reads. When the Hub stages the data on a GPU node and rewrites `folder` to that copy, the rows are
  written from the copy but the project's alias still names the bucket, never the node's stage
  path. The page always sends `alias_folder` (the chosen folder unless the person edited it).
- The URL alias card no longer offers to copy the folder next to the table. SAM3 never made that
  copy (it sends no `alias_copy_*` fields), so the checked offer promised something the run did not
  do. Moving data to a GPU node is the Hub's run dialog's job.
- The warm-up says whether it downloads the weights or loads them from the machine's Hugging Face
  cache, and the page logs that. It used to announce "downloading the SAM3 model" for every cold
  worker, so a worker restart on a warm machine looked like a second download.


### Added
- The Hugging Face token is a Connection. The page's token box is replaced by a **Choose…** button
  that opens the Hub's dialog (`PLUGIN_API.chooseCredential("huggingface")`). There the person picks
  one of their huggingface token Connections, allows an existing one for SAM3, or adds a token.
  The manifest declares `credentials = [{service = "huggingface", required = true}]` and
  `credential_routes = ["/preview", "/model-warmup", "/model-status"]`, so the host hands the
  Connection's value to jobs and to those routes. `/model-status` (and `/model-warmup`) report
  which token source the worker uses (`hf_token`: `connection`, `environment`, `legacy-file` or
  `none`), never the token itself.

- The model download receives the token explicitly instead of reading `HF_TOKEN` when it runs.
  The environment is shared by every job and request in a worker, and the warm-up loads on a
  thread of its own. A worker's own `HF_TOKEN` is read once, when the plugin is imported.

#### Other changes
- Lock the staged 3lc 3.5.0.dev149866 and SDK 0.5.0.20261007121635.34.1; require the staged core
  directly (`3lc>=3.5.0.dev149866,<4.0.0`, also the floor of the `3lc[pacmap,umap]` extra) and resolve
  it from the `staging` index.
- CI runs on pull requests into, and pushes to, `config-service-poc` as well as `main`.
- Require plugin SDK `>=0.5.0,<0.6.0` and lock the private POC build.
- Resolve the plugin SDK from the explicit `staging` index declared in `pyproject.toml`; developers and CI
  need only `UV_INDEX_STAGING_USERNAME` / `UV_INDEX_STAGING_PASSWORD`.
- Stamp and validate package and manifest versions together before publication.
- Manual builds publish only to private CloudRepo when explicitly requested.

- A folder source always gets its URL alias; the widget no longer offers to skip it. A table of
  absolute paths only works on the machine that wrote it, which a remote node is not.
- Runs, tables and their URL aliases are created under the project root the job carries
  (`ctx.project_root_url`), not the worker's configured root.
### Removed
- `POST /set-hf-token` and `GET /hf-token-status`. Nothing writes `hf-token.json` any more. For this
  release only, a token file saved by an earlier version is still read when no Connection is chosen
  and the worker has no `HF_TOKEN`. The page then says "using the legacy token file — choose a
  Connection", and so does a job's log.

### Fixed
- The legacy token file is found again with an SDK that resolves its config root when a store
  is built (`config_store.config_root()`; `CONFIG_ROOT` is now only an override, `None` by
  default). A worker with no home directory reads no legacy token instead of failing the job.
- The preview button no longer hangs for up to 20 minutes when the worker cannot answer
  `/model-warmup`. A reply without a warm-up state (a remote node running an older plugin build
  answers 404) or three failed polls in a row now stops the loop and says why in the log.


## [0.2.5] - 2026-09-11

### Fixed
- `plugin.toml` version now matches the package version. 0.2.4's release commit bumped
  `pyproject.toml` but not the manifest, which failed the release workflow's version-parity
  gate before publish — 0.2.4 never reached PyPI.

## [0.2.4] - 2026-09-10

### Added
- `POST /model-warmup` starts the multi-GB model load on a background thread and returns at
  once; `GET /model-status` reports `cold | warming | ready | failed`. The page warms the model
  through short polls before the first preview instead of one long request that a browser
  timeout or a proxy idle window could kill. A load that fails (a gated model the token cannot
  read) is reported on the next poll; only a fresh user action retries it.
- The HF token is persisted in the plugin's config directory and loaded into the process
  environment on demand, so it survives worker restarts instead of living only in the
  worker's environment.
- The manifest declares `node_routes = ["/preview", "/model-warmup", "/model-status"]`, the
  routes bound to the loaded model. A host without remote-node support ignores the key.
- The Table URL field has the host's table picker (Browse), like the other plugins.
- The sidebar and the page hero carry Meta's mark.

### Changed
- Requires plugin SDK `>=0.4.0,<0.5.0` (was `>=0.3.1,<0.4.0`).

### Fixed
- The `sam3` extra declares the imports Meta's `sam3` wheel uses without declaring them
  (`psutil`, `opencv-python-headless`, `scipy`, `matplotlib`, and `decord` on Linux), so a
  freshly provisioned venv no longer fails at request time with `No module named 'psutil'`.

## [0.2.3] - 2026-09-07

### Changed
- Requires `3lc>=3.3.0` (was `>=3.0.0`), so the plugin venv resolves the current 3lc release.

## [0.2.2] - 2026-08-27

### Changed
- Requires plugin SDK `3lc-compute-plugin-sdk>=0.3.1,<0.4.0`, pinned without the `[shared]`
  extra: since SDK 0.3.1 the `3lc` data plane is a base dependency of the SDK, and the extra is a
  deprecated no-op.
- The prediction run URL is reported as the job's **result** (`ctx.result`), so the Queue &
  Progress card's Open link points at it; it is no longer a `run` entry in the job's metric
  cards. A `create_table` job reports the created table as its result, and a
  `create_and_predict` job reports the table until the run exists.
- Validation failures (unknown mode, no images in the source, no labels in the table schema)
  are reported with a clean, user-facing message on the failed job card instead of an
  exception-type prefix.
- The job page is now a launcher over the generic Queue: the fragment drives jobs through the
  SDK's `PluginJobs` client and reads completion (`run_url`) and failure (`error`) from the
  generic job record. On mount it re-attaches to a queued/running SAM3 job from the host's job
  list, showing a compact running state (progress, "Open Queue") instead of the empty launch
  form, so navigating away and back mid-job no longer loses the job.

### Fixed
- Live log lines and per-image progress from a running job reach the plugin page again. The
  fragment had opened its own socket on the root namespace while the host relays the plugin's
  events on `/sam3`; it now subscribes on the plugin namespace through `PluginJobs`.

## [0.2.1] - 2026-08-21

### Changed
- Packaging: added a PyPI project README (`README-wheel.md`) and tightened the distribution
  description. No functional or contract change.

## [0.2.0] - 2026-08-18

### Added
- The image-folder field uses the SDK's shared data-source picker: browse the compute node's
  filesystem (confined to operator-configured roots) instead of typing a path blind. The SDK's
  `/browse` route is mounted alongside the plugin's own routes (#4).

### Changed
- **Distribution moved to PyPI**: tagged releases publish `3lc-compute-plugin-sam3` to public
  PyPI via Trusted Publishing; the CloudRepo index (pypi.3lc.ai) is no longer needed to install
  the plugin. Manual prerelease builds keep publishing to CloudRepo for a grace period (#4).
- The plugin SDK pin is `>=0.2.2,<0.3.0`, resolved from public PyPI (the SDK's home since
  0.2.2) — no custom indexes remain besides the CUDA torch index (#4). Earlier steps on the
  way: the pin was widened to `>=0.2.0,<0.3.0` (#2), and `3lc` moved to public PyPI with the
  3.2 rust release (#3).
- The folder field no longer ships a hardcoded dev-machine default path (#4).

### Fixed
- A `~`-prefixed folder path is expanded at every ingress (image listing, preview, table
  creation) instead of failing opaquely when the plugin can't find the literal path (#4).

## [0.1.3] - 2026-07-03

### Fixed
- The plugin manifest version and the distribution version are bumped together, so the version
  the plugin card reports matches the installed distribution.

## [0.1.2] - 2026-07-03

### Fixed
- The CUDA torch index is applied on Windows as well as Linux, so GPU-enabled installs work on
  Windows hosts.

### Changed
- The plugin SDK dependency is resolved from the public package index under its final name
  `3lc-compute-plugin-sdk` (was a git pin).

## [0.1.1] - 2026-07-01

### Added
- PaCMAP dependency, and UMAP routed through the `3lc[pacmap,umap]` extras, so embedding
  visualizations work out of the box.

## [0.1.0] - 2026-07-01

First release, extracted from the `3lc-compute-plugins` umbrella into its own repository.

### Added
- The SAM3 auto-label plugin for the 3LC compute service: generate segmentation annotations for
  image tables using SAM3, written back as 3LC table revisions. GPU-classed and venv-isolated;
  distributed as `3lc-compute-plugin-sam3`.
