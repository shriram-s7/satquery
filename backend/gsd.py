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
    valid_region_px: Tuple[int, int, int, int]  # (row_min, col_min, row_max, col_max), local tile coords


def _resampling_for(scale_factor: float) -> Resampling:
    return Resampling.bilinear if scale_factor >= 1.0 else Resampling.average


def _single_patch_valid_note(ground_width_km: float, ground_height_km: float, resampling: Resampling) -> str:
    valid_w = min(MODEL_PATCH_PX, math.ceil(ground_width_km * 1000.0 / MODEL_NATIVE_GSD))
    valid_h = min(MODEL_PATCH_PX, math.ceil(ground_height_km * 1000.0 / MODEL_NATIVE_GSD))

    resample_note = f"Resampled to {MODEL_NATIVE_GSD:.1f} m/px ({valid_w}x{valid_h} px, Resampling.{resampling.name})"

    if valid_w < MODEL_PATCH_PX or valid_h < MODEL_PATCH_PX:
        pct = 100.0 * (valid_w * valid_h) / (MODEL_PATCH_PX * MODEL_PATCH_PX)
        padding_note = (
            f", padded to the {MODEL_PATCH_PX}x{MODEL_PATCH_PX} model patch size. "
            f"Valid region: {valid_w}x{valid_h} px ({pct:.1f}% of patch)."
        )
    else:
        padding_note = f", exactly filling the {MODEL_PATCH_PX}x{MODEL_PATCH_PX} model patch (no padding)."

    return f"{resample_note}{padding_note} Effective output GSD: {MODEL_NATIVE_GSD:.1f} m/px."


def plan_normalization(info: RasterInfo) -> NormalizationPlan:
    if not info.has_geo or info.gsd_metres is None or info.crs is None:
        raise ValueError(f"{info.path} has no usable GSD/CRS; cannot plan normalization")

    gsd_x, gsd_y = info.gsd_metres
    input_gsd = (gsd_x + gsd_y) / 2.0
    scale_factor = input_gsd / MODEL_NATIVE_GSD

    ground_width_km = info.width * gsd_x / 1000.0
    ground_height_km = info.height * gsd_y / 1000.0
    ground_coverage_km = (ground_width_km, ground_height_km)
    footprint_note = f"Input GSD {input_gsd:.2f} m/px, scene footprint {ground_width_km * 1000:.1f} x {ground_height_km * 1000:.1f} m."

    if 0.5 <= scale_factor <= 2.0:
        strategy = "passthrough"
        tile_grid = (1, 1)
        resampling = _resampling_for(scale_factor)
        rationale = f"{footprint_note} {_single_patch_valid_note(ground_width_km, ground_height_km, resampling)}"
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
                f"{footprint_note} It exceeds one {PATCH_GROUND_M / 1000:.2f} km model patch, so it is "
                f"resampled to {MODEL_NATIVE_GSD:.1f} m/px (Resampling.average) and tiled into a {rows}x{cols} "
                f"grid of {MODEL_PATCH_PX}x{MODEL_PATCH_PX} patches; edge tiles are padded where the scene "
                f"doesn't fill the full patch. Effective output GSD: {MODEL_NATIVE_GSD:.1f} m/px."
            )
        else:
            strategy = "downsample"
            tile_grid = (1, 1)
            rationale = f"{footprint_note} {_single_patch_valid_note(ground_width_km, ground_height_km, Resampling.average)}"
    else:
        strategy = "upsample"
        tile_grid = (1, 1)
        rationale = f"{footprint_note} {_single_patch_valid_note(ground_width_km, ground_height_km, Resampling.bilinear)}"

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


def _tile_valid_region_px(row0: int, col0: int, src_height_px: float, src_width_px: float) -> Tuple[int, int, int, int]:
    row_min = 0
    col_min = 0
    row_max = min(MODEL_PATCH_PX, max(0, math.ceil(src_height_px - row0)))
    col_max = min(MODEL_PATCH_PX, max(0, math.ceil(src_width_px - col0)))
    return (row_min, col_min, row_max, col_max)


def apply_normalization(info: RasterInfo, plan: NormalizationPlan) -> List[Tile]:
    rows, cols = plan.tile_grid
    resampling = Resampling.bilinear if plan.scale_factor >= 1.0 else Resampling.average

    src_crs = CRS.from_user_input(info.crs)
    target_crs = _target_crs(info)

    left, bottom, right, top = transform_bounds(src_crs, target_crs, *info.bounds_native)
    grid_transform = Affine(MODEL_NATIVE_GSD, 0, left, 0, -MODEL_NATIVE_GSD, top)

    # The grid is anchored at the source's own reprojected top-left corner, so the
    # source's real (non-padded) data always spans grid pixels [0, src_height_px) x
    # [0, src_width_px) at MODEL_NATIVE_GSD — used below to mark padding per tile.
    src_height_px = (top - bottom) / MODEL_NATIVE_GSD
    src_width_px = (right - left) / MODEL_NATIVE_GSD

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
                valid_region_px=_tile_valid_region_px(row0, col0, src_height_px, src_width_px),
            ))

    return tiles


def pair_tiles(tiles_a: List[Tile], tiles_b: List[Tile]) -> List[Tuple[Tile, Tile]]:
    grid_a = {tile.tile_index for tile in tiles_a}
    grid_b = {tile.tile_index for tile in tiles_b}
    if grid_a != grid_b:
        raise ValueError(
            f"Cannot pair tiles: tile grids differ between the two images "
            f"({sorted(grid_a)} vs {sorted(grid_b)})."
        )

    by_index_b = {tile.tile_index: tile for tile in tiles_b}
    return [(tile_a, by_index_b[tile_a.tile_index]) for tile_a in sorted(tiles_a, key=lambda t: t.tile_index)]


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
