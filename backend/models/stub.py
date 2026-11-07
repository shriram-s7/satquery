"""PLACEHOLDER MODEL. Not a real model.

Per CLAUDE.md hard rule #1: the real vision-language model is not integrated yet.
This is the single point through which every model call must pass — never call a
real model anywhere else in this codebase. Everything below is deterministic,
canned output keyed on `task`, plus a fixed 400ms sleep to make the UI's loading
states visible during development.

This module performs NO real inference — it never looks at pixel content. The
change_detection regions below are static coordinates copied from
fixtures/GROUND_TRUTH.md (the two new buildings and the receded water body in
optical_t1.tif/optical_t2.tif), scaled from that file's native-image pixel space
into the model's 10 m/px tile-pixel space so the demo overlay lands on the real
synthetic features instead of on arbitrary boxes. This only works for those two
specific fixtures; a real model would derive regions from the tiles it receives.
"""
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

STUB_MODEL_NAME = "satquery-stub-v0 (PLACEHOLDER, not a trained model)"
STUB_LATENCY_SECONDS = 0.4
PAIR_TASKS = ("change_detection", "fusion")

TASK_ANSWERS = {
    "vqa": "Stub answer: the scene shows a mix of built-up and vegetated land cover.",
    "captioning": "Stub caption: a satellite image patch containing buildings, roads, and vegetation.",
    "grounding": "Stub grounding: the highlighted region is the closest match for the query.",
    "change_detection": (
        "Stub change summary: 2 new built-up structures appeared, and the water body "
        "near the scene center contracted to about 36% of its T1 extent (a ~64% reduction)."
    ),
    "fusion": "Stub fusion answer: combined optical and SAR evidence agrees on the land cover class.",
    "unknown": "Stub fallback: unable to determine a specific answer for this query type.",
}

# change_detection boxes: pixel bboxes for the 2 new buildings and the receded water
# body from fixtures/GROUND_TRUTH.md, converted from that file's native-image pixel
# space (0.65 m/px) into the model's tile-pixel space (10 m/px) via a fixed scale
# factor (0.65/10). Valid only for optical_t1.tif/optical_t2.tif.
TASK_REGIONS = {
    "vqa": [],
    "captioning": [],
    "grounding": [(40, 40, 80, 80)],
    "change_detection": [(28, 16, 31, 20), (14, 27, 18, 31), (19, 11, 25, 20)],
    "fusion": [(30, 30, 90, 90)],
    "unknown": [],
}

TASK_CONFIDENCE = {
    "vqa": 0.62,
    "captioning": 0.68,
    "grounding": 0.71,
    "change_detection": 0.77,
    "fusion": 0.66,
    "unknown": 0.20,
}


@dataclass
class ModelOutput:
    answer_text: str
    regions: List[Tuple[int, int, int, int]]
    confidence: float
    model_name: str
    latency_ms: float


def run_model(
    task: str,
    query: str,
    tiles: Optional[list] = None,
    tile_pairs: Optional[List[Tuple[object, object]]] = None,
) -> ModelOutput:
    if task in PAIR_TASKS:
        if not tile_pairs:
            raise ValueError(f"run_model requires tile_pairs for task '{task}'")
    elif not tiles:
        raise ValueError(f"run_model requires tiles for task '{task}'")

    start = time.perf_counter()
    time.sleep(STUB_LATENCY_SECONDS)

    answer_text = TASK_ANSWERS.get(task, TASK_ANSWERS["unknown"])
    regions = list(TASK_REGIONS.get(task, TASK_REGIONS["unknown"]))
    confidence = TASK_CONFIDENCE.get(task, TASK_CONFIDENCE["unknown"])

    query = (query or "").strip()
    if query:
        answer_text = f'{answer_text} (query: "{query}")'

    latency_ms = (time.perf_counter() - start) * 1000.0

    return ModelOutput(
        answer_text=answer_text,
        regions=regions,
        confidence=confidence,
        model_name=STUB_MODEL_NAME,
        latency_ms=round(latency_ms, 2),
    )
