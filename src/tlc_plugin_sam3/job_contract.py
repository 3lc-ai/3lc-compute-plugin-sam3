# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""Native SAM3 jobs and MCP tools share validated inputs and source selection."""

import sys
from pathlib import Path

from tlc_plugin_sdk.job_contract import JobContract, form_field_schema, normalize_configuration, write_tools

from tlc_plugin_sam3.form_fields import FIELDS


def contract():
    fields = {
        "mode": {"type": "string", "enum": ["predict", "create_table", "create_and_predict"], "default": "predict"},
        "table_url": {"type": "string", "default": ""},
        "folder": {"type": "string", "default": ""},
        "source_table_url": {"type": "string", "default": ""},
        "labels": {"type": "array", "items": {"type": "string", "minLength": 1}, "uniqueItems": True, "default": []},
        "label_colors": {"type": "array", "items": {"type": "string"}, "default": []},
        "max_images": {"type": "integer", "minimum": 0, "default": 0},
        "project_name": {"type": "string", "default": ""},
        "run_name": {"type": "string", "default": ""},
        "alias_enabled": {"type": "boolean", "default": False},
        "alias_token": {"type": "string", "default": ""},
        "alias_folder": {"type": "string", "default": ""},
        "alias_source_folder": {"type": "string", "default": ""},
    }
    fields.update({field["id"]: form_field_schema(field) for field in FIELDS})
    for name in ("dataset_name", "table_name"):
        fields[name]["minLength"] = 1
    return JobContract(fields, body_key=None)


def requirements(mode):
    """Identical mode-specific constraints for native jobs and published tools."""
    if mode == "predict":
        return {"required": ["table_url"], "properties": {"table_url": {"pattern": r"\S"}}}
    return {
        "required": ["labels", "project_name"],
        "properties": {"labels": {"minItems": 1}, "project_name": {"pattern": r"\S"}},
        "oneOf": [
            {
                "required": ["folder"],
                "properties": {"folder": {"pattern": r"\S"}, "source_table_url": {"maxLength": 0}},
            },
            {
                "required": ["source_table_url"],
                "properties": {"source_table_url": {"pattern": r"\S"}, "folder": {"maxLength": 0}},
            },
        ],
    }


def normalize(params):
    native = contract()
    value = native.normalize({key: value for key, value in params.items() if key in native.fields})
    schema = native.native_schema()
    schema["allOf"] = [requirements(value["mode"])]
    return normalize_configuration(value, schema)


def tools():
    native = contract()
    tools = []
    for mode, title in [
        ("predict", "Predict with SAM3"),
        ("create_table", "Create a SAM3 annotation table"),
        ("create_and_predict", "Create and label a table with SAM3"),
    ]:
        tool = native.tool(
            mode,
            title,
            title + ". Uses the same native job and preparation path as the module. "
            "Select a Hugging Face Connection for gated weights. Poll job_status for the result.",
            constants={"mode": mode},
            required=("table_url",) if mode == "predict" else ("labels", "project_name"),
        )
        tool["input_schema"]["allOf"] = [requirements(mode)]
        tools.append(tool)
    return tools


if __name__ == "__main__":
    write_tools(Path(__file__).with_name("mcp-tools.json"), tools(), check="--check" in sys.argv)
