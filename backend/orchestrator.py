"""The agent: validate -> classify -> route -> merge."""
import dataclasses
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from backend.geo import RasterInfo, bbox_to_geojson, read_raster
from backend.gsd import (
    MODEL_NATIVE_GSD,
    MODEL_PATCH_PX,
    Tile,
    aggregate_tile_results,
    apply_normalization,
    plan_normalization,
)
from backend.intent import IntentResult, classify_intent
from backend.models.stub import run_model
from backend.validate import UnreadableRaster, ValidationResult, validate_inputs


@dataclass
class QueryResponse:
    answer_text: str
    geojson: Dict[str, Any]
    overlay_regions: List[Dict[str, Any]]
    confidence: float
    intent: IntentResult
    normalization_plan: List[Dict[str, Any]]
    validations: List[ValidationResult]
    trace: List[Dict[str, Any]] = field(default_factory=list)
    rejected: bool = False


def _trace(step: str, detail: str, start: float) -> Dict[str, Any]:
    return {"step": step, "detail": detail, "duration_ms": round((time.perf_counter() - start) * 1000, 2)}


def _tile_raster_info(tile: Tile) -> RasterInfo:
    return RasterInfo(
        path="<tile>",
        driver="tile",
        crs=tile.crs,
        width=MODEL_PATCH_PX,
        height=MODEL_PATCH_PX,
        band_count=tile.array.shape[0],
        dtype=str(tile.array.dtype),
        transform=tile.transform,
        bounds_native=tile.bounds_wgs84,
        bounds_wgs84=tile.bounds_wgs84,
        gsd_metres=(MODEL_NATIVE_GSD, MODEL_NATIVE_GSD),
        has_geo=True,
        nodata=None,
    )


def run_query(files: List[str], query: str) -> QueryResponse:
    trace: List[Dict[str, Any]] = []

    t0 = time.perf_counter()
    rasters = []
    for path in files:
        try:
            rasters.append(read_raster(path))
        except Exception as e:
            rasters.append(UnreadableRaster(path=str(path), error=f"{type(e).__name__}: {e}"))
    ok_count = sum(1 for r in rasters if isinstance(r, RasterInfo))
    bad_count = len(rasters) - ok_count
    trace.append(_trace(
        "read_rasters", f"Read {len(files)} file(s): {ok_count} ok, {bad_count} unreadable.", t0,
    ))

    t0 = time.perf_counter()
    intent_result = classify_intent(query, image_count=len(files))
    trace.append(_trace(
        "classify_intent",
        f"intent={intent_result.intent} confidence={intent_result.confidence} "
        f"method={intent_result.method} signals={intent_result.matched_signals}",
        t0,
    ))

    t0 = time.perf_counter()
    validations = validate_inputs(rasters, query, intent_result.intent)
    trace.append(_trace(
        "validate",
        f"{len(validations)} validation result(s): "
        f"{[v.code.value if v.code else None for v in validations]}",
        t0,
    ))

    if any(v.severity == "reject" for v in validations):
        return QueryResponse(
            answer_text="Query rejected by the Trust Gate; see validations for details.",
            geojson={"type": "FeatureCollection", "features": []},
            overlay_regions=[],
            confidence=0.0,
            intent=intent_result,
            normalization_plan=[],
            validations=validations,
            trace=trace,
            rejected=True,
        )

    valid_infos: List[RasterInfo] = [r for r in rasters if isinstance(r, RasterInfo)]

    t0 = time.perf_counter()
    normalization_plans: List[Dict[str, Any]] = []
    all_tiles: List[tuple] = []
    for info in valid_infos:
        plan = plan_normalization(info)
        tiles = apply_normalization(info, plan)
        normalization_plans.append({"path": info.path, **dataclasses.asdict(plan)})
        for tile in tiles:
            all_tiles.append((info, tile))
    trace.append(_trace(
        "gsd_normalize",
        f"Normalized {len(valid_infos)} image(s) into {len(all_tiles)} total tile(s).",
        t0,
    ))

    # TODO(real-model): once a real model is wired in, tiles from paired images
    # (change_detection / fusion) should be matched by tile_index and passed to the
    # model together. The stub ignores tile content, so each tile is scored
    # independently for now.
    t0 = time.perf_counter()
    tile_outputs = []
    for info, tile in all_tiles:
        output = run_model(task=intent_result.intent, tiles=[tile], query=query)
        tile_outputs.append((info, tile, output))
    trace.append(_trace(
        "run_model",
        f"Ran stub model on {len(tile_outputs)} tile(s), task={intent_result.intent}.",
        t0,
    ))

    t0 = time.perf_counter()
    tiles_only = [tile for _, tile, _ in tile_outputs]
    result_dicts = [{"classes": [], "confidence": output.confidence} for _, _, output in tile_outputs]
    aggregated = aggregate_tile_results(tiles_only, result_dicts)
    trace.append(_trace(
        "aggregate",
        f"Aggregated {aggregated['tile_count']} tile(s); mean_confidence={aggregated['mean_confidence']}.",
        t0,
    ))

    t0 = time.perf_counter()
    features: List[Dict[str, Any]] = []
    overlay_regions: List[Dict[str, Any]] = []
    for info, tile, output in tile_outputs:
        tile_info = _tile_raster_info(tile)
        for bbox in output.regions:
            fc_feature = bbox_to_geojson(tile_info, bbox)
            fc_feature["properties"] = {
                "tile_index": list(tile.tile_index),
                "source_image": info.path,
                "confidence": output.confidence,
                "task": intent_result.intent,
            }
            features.append(fc_feature)
            overlay_regions.append({
                "tile_index": list(tile.tile_index),
                "source_image": info.path,
                "bbox_px": list(bbox),
                "bbox_wgs84": fc_feature["geometry"]["coordinates"][0],
                "confidence": output.confidence,
            })
    geojson = {"type": "FeatureCollection", "features": features}
    trace.append(_trace("regions_to_geojson", f"Converted {len(features)} region(s) to GeoJSON.", t0))

    t0 = time.perf_counter()
    mean_tile_confidence = aggregated["mean_confidence"]
    if mean_tile_confidence is not None:
        overall_confidence = round((intent_result.confidence + mean_tile_confidence) / 2.0, 3)
    else:
        overall_confidence = intent_result.confidence
    trace.append(_trace(
        "compute_confidence",
        f"overall_confidence={overall_confidence} "
        f"(intent={intent_result.confidence}, mean_tile={mean_tile_confidence}).",
        t0,
    ))

    if len(tile_outputs) == 1:
        answer_text = tile_outputs[0][2].answer_text
    elif tile_outputs:
        answer_text = " | ".join(
            f"[{info.path} tile{tile.tile_index}] {output.answer_text}"
            for info, tile, output in tile_outputs
        )
    else:
        answer_text = "No tiles were produced for this query."

    return QueryResponse(
        answer_text=answer_text,
        geojson=geojson,
        overlay_regions=overlay_regions,
        confidence=overall_confidence,
        intent=intent_result,
        normalization_plan=normalization_plans,
        validations=validations,
        trace=trace,
        rejected=False,
    )
