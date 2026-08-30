from pathlib import Path

import pytest
import rasterio

from backend.geo import RasterInfo, read_raster
from backend.validate import RejectionCode, UnreadableRaster, validate_inputs

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _read(name):
    return read_raster(FIXTURES_DIR / name)


def _codes(results):
    return [r.code for r in results]


def test_zero_images_wrong_image_count():
    results = validate_inputs([], "what is in this image?", "single_image_analysis")
    assert len(results) == 1
    assert results[0].code == RejectionCode.WRONG_IMAGE_COUNT
    assert results[0].ok is False
    assert results[0].severity == "reject"
    assert "0 images" in results[0].message


def test_unreadable_file():
    try:
        read_raster(FIXTURES_DIR / "corrupt.tif")
        pytest.fail("expected corrupt.tif to fail to open")
    except rasterio.errors.RasterioIOError as e:
        broken = UnreadableRaster(path=str(FIXTURES_DIR / "corrupt.tif"), error=str(e))

    results = validate_inputs([broken], "what is in this image?", "single_image_analysis")
    assert RejectionCode.UNREADABLE in _codes(results)
    hit = next(r for r in results if r.code == RejectionCode.UNREADABLE)
    assert hit.ok is False
    assert hit.severity == "reject"
    assert "corrupt.tif" in hit.message


def test_not_geospatial_png():
    info = _read("not_geo.png")
    results = validate_inputs([info], "what is in this image?", "single_image_analysis")
    assert RejectionCode.NOT_GEOSPATIAL in _codes(results)
    hit = next(r for r in results if r.code == RejectionCode.NOT_GEOSPATIAL)
    assert hit.ok is False
    assert "not_geo.png" in hit.message


def test_change_detection_with_one_image_wrong_count():
    info = _read("optical_t1.tif")
    results = validate_inputs([info], "what changed?", "change_detection")
    assert RejectionCode.WRONG_IMAGE_COUNT in _codes(results)
    hit = next(r for r in results if r.code == RejectionCode.WRONG_IMAGE_COUNT)
    assert "change_detection" in hit.message


def test_fusion_with_one_image_wrong_count():
    info = _read("optical_t1.tif")
    results = validate_inputs([info], "fuse these", "fusion")
    assert RejectionCode.WRONG_IMAGE_COUNT in _codes(results)


def test_no_spatial_overlap():
    a = _read("optical_t1.tif")
    b = _read("far_away.tif")
    results = validate_inputs([a, b], "what changed between these?", "change_detection")
    assert RejectionCode.NO_SPATIAL_OVERLAP in _codes(results)
    hit = next(r for r in results if r.code == RejectionCode.NO_SPATIAL_OVERLAP)
    assert hit.ok is False
    assert hit.severity == "reject"
    assert "13.08N 80.27E" in hit.message
    assert "28.61N 77.20E" in hit.message
    assert "0.00" in hit.message


def test_crs_mismatch_is_a_warning():
    a = _read("optical_t1.tif")
    b = _read("sentinel_like.tif")
    results = validate_inputs([a, b], "fuse these", "fusion")
    assert RejectionCode.CRS_MISMATCH in _codes(results)
    hit = next(r for r in results if r.code == RejectionCode.CRS_MISMATCH)
    assert hit.ok is True
    assert hit.severity == "warn"
    assert "EPSG:4326" in hit.message
    assert "EPSG:32644" in hit.message


def test_modality_mismatch_for_fusion():
    a = _read("optical_t1.tif")
    b = _read("optical_t2.tif")
    results = validate_inputs([a, b], "fuse these", "fusion")
    assert RejectionCode.MODALITY_MISMATCH in _codes(results)
    hit = next(r for r in results if r.code == RejectionCode.MODALITY_MISMATCH)
    assert hit.ok is False
    assert hit.severity == "reject"
    assert "optical_rgb" in hit.message
    assert RejectionCode.NO_SPATIAL_OVERLAP not in _codes(results)
    assert RejectionCode.CRS_MISMATCH not in _codes(results)


def test_band_count_unsupported():
    base = dict(
        path="weird.tif", driver="GTiff", crs="EPSG:4326", width=10, height=10,
        transform=None, bounds_native=(0, 0, 1, 1), bounds_wgs84=(0, 0, 1, 1),
        gsd_metres=(1.0, 1.0), has_geo=True, nodata=None,
    )
    weird = RasterInfo(band_count=2, dtype="uint8", **base)
    results = validate_inputs([weird], "what is in this image?", "single_image_analysis")
    assert RejectionCode.BAND_COUNT_UNSUPPORTED in _codes(results)
    hit = next(r for r in results if r.code == RejectionCode.BAND_COUNT_UNSUPPORTED)
    assert "2 band(s)" in hit.message
    assert "uint8" in hit.message


def test_resolution_out_of_range():
    base = dict(
        path="too_coarse.tif", driver="GTiff", crs="EPSG:4326", width=10, height=10,
        transform=None, bounds_native=(0, 0, 1, 1), bounds_wgs84=(0, 0, 1, 1),
        gsd_metres=(1000.0, 1000.0), has_geo=True, nodata=None,
    )
    coarse = RasterInfo(band_count=3, dtype="uint8", **base)
    results = validate_inputs([coarse], "what is in this image?", "single_image_analysis")
    assert RejectionCode.RESOLUTION_OUT_OF_RANGE in _codes(results)
    hit = next(r for r in results if r.code == RejectionCode.RESOLUTION_OUT_OF_RANGE)
    assert "1000.000m" in hit.message


def test_clean_pair_has_no_issues():
    a = _read("optical_t1.tif")
    b = _read("optical_t2.tif")
    results = validate_inputs([a, b], "what changed between these?", "change_detection")
    assert results == []


def test_all_rejection_codes_are_reachable():
    covered = {
        RejectionCode.NOT_GEOSPATIAL,
        RejectionCode.UNREADABLE,
        RejectionCode.WRONG_IMAGE_COUNT,
        RejectionCode.NO_SPATIAL_OVERLAP,
        RejectionCode.CRS_MISMATCH,
        RejectionCode.MODALITY_MISMATCH,
        RejectionCode.BAND_COUNT_UNSUPPORTED,
        RejectionCode.RESOLUTION_OUT_OF_RANGE,
    }
    assert covered == set(RejectionCode)
