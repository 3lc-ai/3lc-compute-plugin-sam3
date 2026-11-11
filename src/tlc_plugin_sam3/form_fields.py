# Copyright 2026 3LC Inc.
# SPDX-License-Identifier: Apache-2.0
"""Maintained SAM3 form controls, shared by UI packaging and job validation."""

FIELDS = [
    {"id": "confidence", "type": "number", "min": 0.01, "max": 0.95, "step": 0.01, "default": 0.2},
    {
        "id": "modality",
        "type": "select",
        "default": "segmentation",
        "options": [{"value": "segmentation", "label": "Segmentation"}, {"value": "bbox", "label": "Bounding Boxes"}],
    },
    {
        "id": "embedding_dim",
        "type": "select",
        "default": 2,
        "options": [{"value": 2, "label": "2D UMAP"}, {"value": 3, "label": "3D UMAP"}],
    },
    {
        "id": "device",
        "type": "select",
        "default": "cuda",
        "options": [{"value": "cuda", "label": "CUDA (GPU)"}, {"value": "cpu", "label": "CPU"}],
    },
    {"id": "dataset_name", "type": "text", "default": "train"},
    {"id": "table_name", "type": "text", "default": "initial"},
]
