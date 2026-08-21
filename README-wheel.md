# 3lc-compute-plugin-sam3

A [3LC Hub](https://docs.3lc.ai) compute-service plugin for auto-labeling images with SAM3.
Prompt with text, preview the results, create tables from them, and run predictions — all from
within the Hub.

## How it's used

You don't install this yourself. The 3LC Hub provisions the plugin into its own isolated
environment (including the GPU stack) and runs it for you; it then appears in the Hub next to the
built-in tools.

## License

Apache-2.0. See `LICENSE`. The SAM3 model weights are pulled at runtime and carry their own
license, separate from this plugin's code.

## Links

- 3LC Hub documentation: <https://docs.3lc.ai>
- Plugin SDK & author guide: <https://3lc-ai.github.io/3lc-compute-plugin-sdk/>
