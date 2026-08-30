"""GSD-adaptive preprocessing: normalize input imagery into the model's training domain
(BigEarthNet-style: 10 m/px, 120x120 px patches) before it reaches models/stub.py."""
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

from backend.geo import RasterInfo, _crs_to_epsg_string, _utm_epsg_for_lonlat

MODEL_NATIVE_GSD = 10.0
MODEL_PATCH_PX = 120
PATCH_GROUND_M = MODEL_PATCH_PX * MODEL_NATIVE_GSD


@dataclass
class NormalizationPlan:
    input_gsd: float
    scale_factor: float
    strategy: str
    tile_grid: Tuple[int, int]
    tile_count: int
    ground_coverage_km: Tuple[float, float]
    rationale: str


@dataclass
class Tile:
    array: np.ndarray
    bounds_wgs84: Tuple[float, float, float, float]
    tile_index: Tuple[int, int]
    transform: Affine
    crs: str


def plan_normalization(info: RasterInfo) -> NormalizationPlan:
    if not info.has_geo or info.gsd_metres is None or info.crs is None:
        raise ValueError(f"{info.path} has no usable GSD/CRS; cannot plan normalization")

    gsd_x, gsd_y = info.gsd_metres
    input_gsd = (gsd_x + gsd_y) / 2.0
    scale_factor = input_gsd / MODEL_NATIVE_GSD

    ground_width_km = info.width * gsd_x / 1000.0
    ground_height_km = info.height * gsd_y / 1000.0
    ground_coverage_km = (ground_width_km, ground_height_km)

    if 0.5 <= scale_factor <= 2.0:
        strategy = "passthrough"
        tile_grid = (1, 1)
        rationale = (
            f"Input GSD {input_gsd:.2f} m is within 0.5x-2x of the model's native "
            f"{MODEL_NATIVE_GSD:.0f} m resolution (scale factor {scale_factor:.2f}); "
            f"passed through as a single canonical {MODEL_PATCH_PX}x{MODEL_PATCH_PX} patch."
        )
    elif scale_factor < 0.5:
        exceeds_one_patch = (
            ground_width_km * 1000.0 > PATCH_GROUND_M or ground_height_km * 1000.0 > PATCH_GROUND_M
        )
        if exceeds_one_patch:
            strategy = "downsample_and_tile"
            cols = max(1, math.ceil(ground_width_km * 1000.0 / PATCH_GROUND_M))
            rows = max(1, math.ceil(ground_height_km * 1000.0 / PATCH_GROUND_M))
            tile_grid = (rows, cols)
            rationale = (
                f"Input GSD {input_gsd:.2f} m is much finer than the model's "
                f"{MODEL_NATIVE_GSD:.0f} m training resolution (scale factor {scale_factor:.3f}), and the "
                f"scene's {ground_width_km:.2f}x{ground_height_km:.2f} km footprint exceeds one "
                f"{PATCH_GROUND_M / 1000:.2f} km model patch, so it is downsampled and tiled into a "
                f"{rows}x{cols} grid to avoid losing ground detail."
            )
        else:
            strategy = "downsample"
            tile_grid = (1, 1)
            rationale = (
                f"Input GSD {input_gsd:.2f} m is much finer than the model's "
                f"{MODEL_NATIVE_GSD:.0f} m training resolution (scale factor {scale_factor:.3f}), but the "
                f"scene's {ground_width_km:.2f}x{ground_height_km:.2f} km footprint fits inside one "
                f"{PATCH_GROUND_M / 1000:.2f} km model patch, so it is downsampled into a single "
                f"{MODEL_PATCH_PX}x{MODEL_PATCH_PX} patch."
            )
    else:
        strategy = "upsample"
        tile_grid = (1, 1)
        rationale = (
            f"Input GSD {input_gsd:.2f} m is coarser than the model's {MODEL_NATIVE_GSD:.0f} m training "
            f"resolution (scale factor {scale_factor:.2f}), so it is upsampled via bilinear interpolation "
            f"to match the training domain."
        )

    tile_count = tile_grid[0] * tile_grid[1]

    return NormalizationPlan(
        input_gsd=input_gsd,
        scale_factor=scale_factor,
        strategy=strategy,
        tile_grid=tile_grid,
        tile_count=tile_count,
        ground_coverage_km=ground_coverage_km,
        rationale=rationale,
    )


def _target_crs(info: RasterInfo) -> CRS:
    crs = CRS.from_user_input(info.crs)
    if crs.is_geographic:
        minlon, minlat, maxlon, maxlat = info.bounds_wgs84
        center_lon = (minlon + maxlon) / 2.0
        center_lat = (minlat + maxlat) / 2.0
        return CRS.from_epsg(_utm_epsg_for_lonlat(center_lon, center_lat))
    return crs


def apply_normalization(info: RasterInfo, plan: NormalizationPlan) -> List[Tile]:
    rows, cols = plan.tile_grid
    resampling = Resampling.bilinear if plan.scale_factor >= 1.0 else Resampling.average

    src_crs = CRS.from_user_input(info.crs)
    target_crs = _target_crs(info)

    left, bottom, right, top = transform_bounds(src_crs, target_crs, *info.bounds_native)
    grid_transform = Affine(MODEL_NATIVE_GSD, 0, left, 0, -MODEL_NATIVE_GSD, top)

    total_width_px = cols * MODEL_PATCH_PX
    total_height_px = rows * MODEL_PATCH_PX
    target_crs_str = _crs_to_epsg_string(target_crs)

    tiles: List[Tile] = []
    with rasterio.open(info.path) as src:
        with WarpedVRT(
            src,
            crs=target_crs,
            transform=grid_transform,
            width=total_width_px,
            height=total_height_px,
            resampling=resampling,
        ) as vrt:
            data = vrt.read()

    for r in range(rows):
        for c in range(cols):
            row0 = r * MODEL_PATCH_PX
            col0 = c * MODEL_PATCH_PX
            patch = data[:, row0:row0 + MODEL_PATCH_PX, col0:col0 + MODEL_PATCH_PX]

            tile_transform = grid_transform @ Affine.translation(col0, row0)
            tile_left, tile_top = tile_transform @ (0, 0)
            tile_right, tile_bottom = tile_transform @ (MODEL_PATCH_PX, MODEL_PATCH_PX)
            tile_bounds_wgs84 = transform_bounds(
                target_crs, CRS.from_epsg(4326), tile_left, tile_bottom, tile_right, tile_top
            )

            tiles.append(Tile(
                array=patch,
                bounds_wgs84=tile_bounds_wgs84,
                tile_index=(r, c),
                transform=tile_transform,
                crs=target_crs_str,
            ))

    return tiles


def aggregate_tile_results(tiles: List[Tile], results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if len(tiles) != len(results):
        raise ValueError("tiles and results must have the same length, in matching order")

    classes = set()
    confidences = []
    provenance = []

    for tile, result in zip(tiles, results):
        tile_classes = list(result.get("classes", []))
        confidence = result.get("confidence")
        classes.update(tile_classes)
        if confidence is not None:
            confidences.append(confidence)
        provenance.append({
            "tile_index": tile.tile_index,
            "bounds_wgs84": tile.bounds_wgs84,
            "classes": tile_classes,
            "confidence": confidence,
        })

    mean_confidence = sum(confidences) / len(confidences) if confidences else None

    return {
        "classes": sorted(classes),
        "mean_confidence": mean_confidence,
        "tile_count": len(tiles),
        "provenance": provenance,
    }
