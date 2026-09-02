# Changelog

All notable changes to `3lc-compute-plugin-sam3` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Manifest declares `node_routes = ["/preview", "/model-warmup", "/model-status"]`: only the
  model-bound routes follow an armed GPU node. Saved configs and the HF token now always live
  on the controller, so they are the same no matter which node is armed (they used to be
  written to whichever worker was armed, and disappeared with the node).

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
