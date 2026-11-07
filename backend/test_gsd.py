from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine
from rasterio.crs import CRS

from backend.geo import read_raster
from backend.gsd import (
    MODEL_NATIVE_GSD,
    MODEL_PATCH_PX,
    aggregate_tile_results,
    apply_normalization,
    pair_tiles,
    plan_normalization,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture(scope="module")
def optical_t1():
    return read_raster(FIXTURES_DIR / "optical_t1.tif")


@pytest.fixture(scope="module")
def optical_t2():
    return read_raster(FIXTURES_DIR / "optical_t2.tif")


@pytest.fixture(scope="module")
def sentinel_like():
    return read_raster(FIXTURES_DIR / "sentinel_like.tif")


def test_plan_normalization_sentinel_like_passthrough(sentinel_like):
    plan = plan_normalization(sentinel_like)
    print(f"\nsentinel_like.tif plan: {plan}")

    assert plan.strategy == "passthrough"
    assert plan.scale_factor == pytest.approx(1.0, rel=0.05)
    assert plan.tile_grid == (1, 1)
    assert plan.tile_count == 1


def test_plan_normalization_optical_t1_downsample(optical_t1):
    plan = plan_normalization(optical_t1)
    print(f"\noptical_t1.tif plan: {plan}")

    assert plan.scale_factor < 0.5
    assert plan.ground_coverage_km[0] * 1000 < MODEL_PATCH_PX * MODEL_NATIVE_GSD
    assert plan.strategy == "downsample"
    assert plan.tile_grid == (1, 1)
    assert plan.tile_count == 1


def test_plan_normalization_large_finescene_downsamples_and_tiles(tmp_path):
    size = 2000
    gsd = 0.65
    transform = Affine(gsd, 0, 700000.0, 0, -gsd, 1400000.0)
    crs = CRS.from_epsg(32644)
    path = tmp_path / "large_fine_scene.tif"
    with rasterio.open(
        path, "w", driver="GTiff",
        height=size, width=size, count=3,
        dtype="uint8", crs=crs, transform=transform,
    ) as dst:
        dst.write(np.zeros((3, size, size), dtype=np.uint8))

    info = read_raster(path)
    plan = plan_normalization(info)
    print(f"\nlarge_fine_scene.tif plan: {plan}")

    assert plan.scale_factor < 0.5
    assert plan.strategy == "downsample_and_tile"
    assert plan.tile_grid[0] > 1 and plan.tile_grid[1] > 1
    assert plan.tile_count == plan.tile_grid[0] * plan.tile_grid[1]

    tiles = apply_normalization(info, plan)
    assert len(tiles) == plan.tile_count
    for tile in tiles:
        assert tile.array.shape[-2:] == (MODEL_PATCH_PX, MODEL_PATCH_PX)
        minlon, minlat, maxlon, maxlat = tile.bounds_wgs84
        assert minlon < maxlon and minlat < maxlat


def test_apply_normalization_sentinel_like_single_tile(sentinel_like):
    plan = plan_normalization(sentinel_like)
    tiles = apply_normalization(sentinel_like, plan)

    assert len(tiles) == 1
    tile = tiles[0]
    assert tile.tile_index == (0, 0)
    assert tile.array.shape == (sentinel_like.band_count, MODEL_PATCH_PX, MODEL_PATCH_PX)

    minlon, minlat, maxlon, maxlat = tile.bounds_wgs84
    src_minlon, src_minlat, src_maxlon, src_maxlat = sentinel_like.bounds_wgs84
    assert minlon == pytest.approx(src_minlon, abs=1e-3)
    assert maxlat == pytest.approx(src_maxlat, abs=1e-3)


def test_apply_normalization_optical_t1_single_padded_tile(optical_t1):
    plan = plan_normalization(optical_t1)
    tiles = apply_normalization(optical_t1, plan)

    assert len(tiles) == 1
    tile = tiles[0]
    assert tile.array.shape == (optical_t1.band_count, MODEL_PATCH_PX, MODEL_PATCH_PX)

    non_nodata_px = np.count_nonzero(tile.array[0])
    assert 0 < non_nodata_px < tile.array[0].size

    row_min, col_min, row_max, col_max = tile.valid_region_px
    assert row_min == 0 and col_min == 0
    assert 0 < row_max < MODEL_PATCH_PX
    assert 0 < col_max < MODEL_PATCH_PX


def test_apply_normalization_effective_gsd_matches_model_native(optical_t1, sentinel_like):
    for info in (optical_t1, sentinel_like):
        plan = plan_normalization(info)
        for tile in apply_normalization(info, plan):
            px_w = abs(tile.transform.a)
            px_h = abs(tile.transform.e)
            assert px_w == pytest.approx(MODEL_NATIVE_GSD, rel=0.01)
            assert px_h == pytest.approx(MODEL_NATIVE_GSD, rel=0.01)


def test_apply_normalization_sentinel_like_no_padding():
    info = read_raster(FIXTURES_DIR / "sentinel_like.tif")
    plan = plan_normalization(info)
    tile = apply_normalization(info, plan)[0]

    assert tile.valid_region_px == (0, 0, MODEL_PATCH_PX, MODEL_PATCH_PX)


def test_aggregate_tile_results_merges_classes_and_confidence(sentinel_like):
    plan = plan_normalization(sentinel_like)
    tiles = apply_normalization(sentinel_like, plan)

    fake_results = [
        {"classes": ["water", "urban"], "confidence": 0.9},
    ]
    merged = aggregate_tile_results(tiles, fake_results)

    assert merged["classes"] == ["urban", "water"]
    assert merged["mean_confidence"] == pytest.approx(0.9)
    assert merged["tile_count"] == 1
    assert merged["provenance"][0]["tile_index"] == (0, 0)
    assert merged["provenance"][0]["classes"] == ["water", "urban"]


def test_aggregate_tile_results_multi_tile_union_and_mean():
    class FakeTile:
        def __init__(self, idx):
            self.tile_index = idx
            self.bounds_wgs84 = (0, 0, 1, 1)

    tiles = [FakeTile((0, 0)), FakeTile((0, 1))]
    results = [
        {"classes": ["water"], "confidence": 0.8},
        {"classes": ["urban", "water"], "confidence": 0.6},
    ]
    merged = aggregate_tile_results(tiles, results)

    assert merged["classes"] == ["urban", "water"]
    assert merged["mean_confidence"] == pytest.approx(0.7)
    assert merged["tile_count"] == 2


def test_aggregate_tile_results_length_mismatch_raises():
    with pytest.raises(ValueError):
        aggregate_tile_results([1, 2], [{"classes": []}])


class _FakeTile:
    def __init__(self, idx):
        self.tile_index = idx


def test_pair_tiles_matches_by_row_col_regardless_of_order():
    tiles_a = [_FakeTile((0, 0)), _FakeTile((0, 1))]
    tiles_b = [_FakeTile((0, 1)), _FakeTile((0, 0))]

    pairs = pair_tiles(tiles_a, tiles_b)

    assert len(pairs) == 2
    assert [p[0].tile_index for p in pairs] == [(0, 0), (0, 1)]
    assert [p[1].tile_index for p in pairs] == [(0, 0), (0, 1)]
    for tile_a, tile_b in pairs:
        assert tile_a.tile_index == tile_b.tile_index


def test_pair_tiles_mismatched_grids_raises():
    tiles_a = [_FakeTile((0, 0)), _FakeTile((0, 1))]
    tiles_b = [_FakeTile((0, 0))]

    with pytest.raises(ValueError):
        pair_tiles(tiles_a, tiles_b)


def test_pair_tiles_real_single_tile_images(optical_t1, optical_t2):
    tiles_a = apply_normalization(optical_t1, plan_normalization(optical_t1))
    tiles_b = apply_normalization(optical_t2, plan_normalization(optical_t2))

    pairs = pair_tiles(tiles_a, tiles_b)

    assert len(pairs) == 1
    tile_a, tile_b = pairs[0]
    assert tile_a.tile_index == (0, 0)
    assert tile_b.tile_index == (0, 0)
