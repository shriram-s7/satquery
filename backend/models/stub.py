"""PLACEHOLDER MODEL. Not a real model.

Per CLAUDE.md hard rule #1: the real vision-language model is not integrated yet.
This is the single point through which every model call must pass — never call a
real model anywhere else in this codebase. Everything below is deterministic,
canned output keyed on `task`, plus a fixed 400ms sleep to make the UI's loading
states visible during development.
"""
import time
from dataclasses import dataclass
from typing import List, Tuple

STUB_MODEL_NAME = "satquery-stub-v0 (PLACEHOLDER, not a trained model)"
STUB_LATENCY_SECONDS = 0.4

TASK_ANSWERS = {
    "vqa": "Stub answer: the scene shows a mix of built-up and vegetated land cover.",
    "captioning": "Stub caption: a satellite image patch containing buildings, roads, and vegetation.",
    "grounding": "Stub grounding: the highlighted region is the closest match for the query.",
    "change_detection": "Stub change summary: new built-up structures detected between the two time steps.",
    "fusion": "Stub fusion answer: combined optical and SAR evidence agrees on the land cover class.",
    "unknown": "Stub fallback: unable to determine a specific answer for this query type.",
}

TASK_REGIONS = {
    "vqa": [],
    "captioning": [],
    "grounding": [(40, 40, 80, 80)],
    "change_detection": [(20, 20, 60, 60), (70, 70, 100, 100)],
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


def run_model(task: str, tiles: list, query: str) -> ModelOutput:
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
