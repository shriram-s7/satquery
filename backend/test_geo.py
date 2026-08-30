from pathlib import Path

import pytest
import rasterio

from backend.geo import (
    bbox_to_geojson,
    guess_modality,
    pixel_to_lonlat,
    read_raster,
    spatial_overlap,
    to_wgs84_bounds,
    RasterInfo,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

GEO_FILES = {
    "optical_t1.tif": {"bands": 3, "dtype": "uint8", "gsd": 0.65, "modality": "optical_rgb"},
    "optical_t2.tif": {"bands": 3, "dtype": "uint8", "gsd": 0.65, "modality": "optical_rgb"},
    "sar_t1.tif": {"bands": 1, "dtype": "float32", "gsd": 0.65, "modality": "sar"},
    "sentinel_like.tif": {"bands": 12, "dtype": "uint16", "gsd": 10.0, "modality": "multispectral"},
    "far_away.tif": {"bands": 3, "dtype": "uint8", "gsd": 0.65, "modality": "optical_rgb"},
}


@pytest.fixture(scope="module")
def infos():
    return {name: read_raster(FIXTURES_DIR / name) for name in GEO_FILES}


@pytest.mark.parametrize("name", GEO_FILES.keys())
def test_read_raster_valid_files(infos, name):
    info = infos[name]
    expected = GEO_FILES[name]

    assert info.has_geo is True
    assert info.crs is not None
    assert info.band_count == expected["bands"]
    assert info.dtype == expected["dtype"]
    assert info.width > 0 and info.height > 0
    assert info.bounds_wgs84 is not None
    minlon, minlat, maxlon, maxlat = info.bounds_wgs84
    assert -180 <= minlon < maxlon <= 180
    assert -90 <= minlat < maxlat <= 90

    assert info.gsd_metres is not None
    gsd_x, gsd_y = info.gsd_metres
    assert gsd_x == pytest.approx(expected["gsd"], rel=0.05)
    assert gsd_y == pytest.approx(expected["gsd"], rel=0.05)


def test_read_raster_corrupt_raises():
    with pytest.raises(rasterio.errors.RasterioIOError):
        read_raster(FIXTURES_DIR / "corrupt.tif")


def test_read_raster_not_geo_png():
    info = read_raster(FIXTURES_DIR / "not_geo.png")
    assert info.has_geo is False
    assert info.crs is None
    assert info.bounds_wgs84 is None
    assert info.gsd_metres is None
    assert info.band_count == 3
    assert info.dtype == "uint8"


@pytest.mark.parametrize("name", GEO_FILES.keys())
def test_to_wgs84_bounds_matches_read_raster(infos, name):
    info = infos[name]
    recomputed = to_wgs84_bounds(info.bounds_native, info.crs)
    for a, b in zip(recomputed, info.bounds_wgs84):
        assert a == pytest.approx(b, abs=1e-9)


def test_to_wgs84_bounds_requires_crs():
    with pytest.raises(ValueError):
        to_wgs84_bounds((0, 0, 1, 1), None)


def test_spatial_overlap_identical_footprint(infos):
    iou = spatial_overlap(infos["optical_t1.tif"], infos["optical_t2.tif"])
    assert iou == pytest.approx(1.0, abs=1e-6)


def test_spatial_overlap_disjoint_far_away(infos):
    iou = spatial_overlap(infos["optical_t1.tif"], infos["far_away.tif"])
    assert iou == 0.0


def test_spatial_overlap_disjoint_different_crs(infos):
    iou = spatial_overlap(infos["optical_t1.tif"], infos["sentinel_like.tif"])
    assert iou == 0.0


def test_spatial_overlap_missing_bounds():
    png_info = read_raster(FIXTURES_DIR / "not_geo.png")
    tif_info = read_raster(FIXTURES_DIR / "optical_t1.tif")
    assert spatial_overlap(png_info, tif_info) == 0.0


@pytest.mark.parametrize("name", GEO_FILES.keys())
def test_pixel_to_lonlat_within_bounds(infos, name):
    info = infos[name]
    minlon, minlat, maxlon, maxlat = info.bounds_wgs84

    lon, lat = pixel_to_lonlat(info, row=0, col=0)
    assert minlon - 1e-6 <= lon <= maxlon + 1e-6
    assert minlat - 1e-6 <= lat <= maxlat + 1e-6

    lon_c, lat_c = pixel_to_lonlat(info, row=info.height // 2, col=info.width // 2)
    assert minlon - 1e-6 <= lon_c <= maxlon + 1e-6
    assert minlat - 1e-6 <= lat_c <= maxlat + 1e-6


def test_pixel_to_lonlat_requires_crs():
    info = read_raster(FIXTURES_DIR / "not_geo.png")
    with pytest.raises(ValueError):
        pixel_to_lonlat(info, 0, 0)


@pytest.mark.parametrize("name", GEO_FILES.keys())
def test_bbox_to_geojson_full_extent(infos, name):
    info = infos[name]
    feature = bbox_to_geojson(info, (0, 0, info.height, info.width))

    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Polygon"
    ring = feature["geometry"]["coordinates"][0]
    assert len(ring) == 5
    assert ring[0] == ring[-1]

    lons = [pt[0] for pt in ring]
    lats = [pt[1] for pt in ring]
    minlon, minlat, maxlon, maxlat = info.bounds_wgs84
    assert min(lons) == pytest.approx(minlon, abs=1e-6)
    assert max(lons) == pytest.approx(maxlon, abs=1e-6)
    assert min(lats) == pytest.approx(minlat, abs=1e-6)
    assert max(lats) == pytest.approx(maxlat, abs=1e-6)


@pytest.mark.parametrize("name,expected", [(n, v["modality"]) for n, v in GEO_FILES.items()])
def test_guess_modality_from_fixtures(infos, name, expected):
    assert guess_modality(infos[name]) == expected


def test_guess_modality_panchromatic_and_unknown():
    base = dict(
        path="x", driver="GTiff", crs="EPSG:4326", width=10, height=10,
        transform=None, bounds_native=(0, 0, 1, 1), bounds_wgs84=(0, 0, 1, 1),
        gsd_metres=(1.0, 1.0), has_geo=True, nodata=None,
    )
    pan = RasterInfo(band_count=1, dtype="uint16", **base)
    assert guess_modality(pan) == "panchromatic"

    unknown = RasterInfo(band_count=2, dtype="uint8", **base)
    assert guess_modality(unknown) == "unknown"
