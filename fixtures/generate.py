"""Synthesize test GeoTIFFs (and a couple of intentionally-broken files) for SatQuery fixtures."""
from pathlib import Path

import numpy as np
import rasterio
from rasterio import Affine
from rasterio.crs import CRS
from rasterio.features import rasterize
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from pyproj import Geod, Transformer
from shapely.geometry import Polygon
from shapely.affinity import scale as shapely_scale
from PIL import Image

FIXTURES_DIR = Path(__file__).parent

CHENNAI = (80.27, 13.08)
DELHI = (77.20, 28.61)
BENGALURU = (77.5946, 12.9716)

OPTICAL_SIZE = 512
OPTICAL_GSD_M = 0.65

SENTINEL_SIZE = 120
SENTINEL_GSD_M = 10.0
SENTINEL_BANDS = 12

WATER_T1 = [
    (140, 300), (210, 255), (290, 260), (330, 300),
    (345, 350), (300, 400), (220, 410), (150, 380), (120, 340),
]
BUILDINGS_T1 = [
    (40, 40, 90, 80),
    (400, 60, 460, 110),
    (60, 420, 110, 470),
    (380, 400, 440, 450),
    (200, 60, 240, 100),
]
BUILDINGS_T2_EXTRA = [
    (250, 430, 300, 470),
    (420, 220, 470, 270),
]

WATER_FAR = [
    (60, 60), (110, 50), (140, 90), (120, 130), (70, 120),
]
BUILDINGS_FAR = [
    (200, 200, 260, 250),
    (300, 300, 350, 360),
    (400, 100, 450, 150),
]


def meters_to_degrees(gsd_m, lat_deg):
    dlat = gsd_m / 111320.0
    dlon = gsd_m / (111320.0 * np.cos(np.radians(lat_deg)))
    return dlon, dlat


def geo_transform_for_center(lon, lat, gsd_m, size):
    dlon, dlat = meters_to_degrees(gsd_m, lat)
    west = lon - dlon * size / 2
    north = lat + dlat * size / 2
    return from_origin(west, north, dlon, dlat)


def build_class_raster(size, buildings, water_coords):
    classes = np.zeros((size, size), dtype=np.uint8)
    for (x0, y0, x1, y1) in buildings:
        classes[y0:y1, x0:x1] = 1
    if water_coords:
        water_poly = Polygon(water_coords)
        water_mask = rasterize(
            [(water_poly, 1)],
            out_shape=(size, size),
            fill=0,
            transform=Affine.identity(),
            dtype=np.uint8,
        )
        classes[water_mask == 1] = 2
    return classes


def scaled_water_class_raster(size, buildings, water_coords, factor):
    classes = np.zeros((size, size), dtype=np.uint8)
    for (x0, y0, x1, y1) in buildings:
        classes[y0:y1, x0:x1] = 1
    water_poly = shapely_scale(Polygon(water_coords), xfact=factor, yfact=factor, origin="centroid")
    water_mask = rasterize(
        [(water_poly, 1)],
        out_shape=(size, size),
        fill=0,
        transform=Affine.identity(),
        dtype=np.uint8,
    )
    classes[water_mask == 1] = 2
    return classes


def synth_optical(class_raster, rng):
    h, w = class_raster.shape
    field_color = np.array([60, 110, 50])
    building_color = np.array([125, 125, 120])
    water_color = np.array([40, 90, 165])
    base = np.zeros((h, w, 3), dtype=np.int16)
    base[class_raster == 0] = field_color
    base[class_raster == 1] = building_color
    base[class_raster == 2] = water_color
    noise = rng.integers(-12, 13, size=(h, w, 3))
    rgb = np.clip(base + noise, 0, 255).astype(np.uint8)
    return np.transpose(rgb, (2, 0, 1))


def synth_sar(class_raster, rng, looks=4):
    intensity = {0: 0.30, 1: 0.70, 2: 0.05}
    base = np.zeros(class_raster.shape, dtype=np.float32)
    for cls, val in intensity.items():
        base[class_raster == cls] = val
    speckle = rng.gamma(shape=looks, scale=1.0 / looks, size=class_raster.shape).astype(np.float32)
    return (base * speckle).astype(np.float32)


def synth_sentinel(rng, bands=SENTINEL_BANDS, size=SENTINEL_SIZE):
    assert size % 8 == 0
    tile = size // 8
    low_res = rng.integers(1000, 4000, size=(8, 8)).astype(np.float32)
    base = np.repeat(np.repeat(low_res, tile, axis=0), tile, axis=1)
    arr = np.zeros((bands, size, size), dtype=np.uint16)
    for b in range(bands):
        band_offset = rng.integers(-500, 500)
        band_scale = rng.uniform(0.8, 1.3)
        noise = rng.normal(0, 150, size=(size, size))
        band = base * band_scale + band_offset + noise
        arr[b] = np.clip(band, 0, 10000).astype(np.uint16)
    return arr


def write_geotiff(path, array, transform, crs, dtype):
    if array.ndim == 3:
        count, height, width = array.shape
    else:
        height, width = array.shape
        count = 1
    with rasterio.open(
        path, "w", driver="GTiff",
        height=height, width=width, count=count,
        dtype=dtype, crs=crs, transform=transform,
    ) as dst:
        if array.ndim == 3:
            dst.write(array)
        else:
            dst.write(array, 1)


def make_optical_pair():
    rng1 = np.random.default_rng(1)
    rng2 = np.random.default_rng(2)
    transform = geo_transform_for_center(*CHENNAI, OPTICAL_GSD_M, OPTICAL_SIZE)
    crs = CRS.from_epsg(4326)

    classes_t1 = build_class_raster(OPTICAL_SIZE, BUILDINGS_T1, WATER_T1)
    rgb_t1 = synth_optical(classes_t1, rng1)
    write_geotiff(FIXTURES_DIR / "optical_t1.tif", rgb_t1, transform, crs, "uint8")

    classes_t2 = scaled_water_class_raster(
        OPTICAL_SIZE, BUILDINGS_T1 + BUILDINGS_T2_EXTRA, WATER_T1, factor=0.6
    )
    rgb_t2 = synth_optical(classes_t2, rng2)
    write_geotiff(FIXTURES_DIR / "optical_t2.tif", rgb_t2, transform, crs, "uint8")

    return classes_t1, transform, crs


def make_sar(classes_t1, transform, crs):
    rng = np.random.default_rng(3)
    sar = synth_sar(classes_t1, rng)
    write_geotiff(FIXTURES_DIR / "sar_t1.tif", sar, transform, crs, "float32")


def make_sentinel_like():
    rng = np.random.default_rng(4)
    transformer = Transformer.from_crs(4326, 32644, always_xy=True)
    cx, cy = transformer.transform(*BENGALURU)
    west = cx - SENTINEL_GSD_M * SENTINEL_SIZE / 2
    north = cy + SENTINEL_GSD_M * SENTINEL_SIZE / 2
    transform = from_origin(west, north, SENTINEL_GSD_M, SENTINEL_GSD_M)
    crs = CRS.from_epsg(32644)
    arr = synth_sentinel(rng)
    write_geotiff(FIXTURES_DIR / "sentinel_like.tif", arr, transform, crs, "uint16")


def make_far_away():
    rng = np.random.default_rng(5)
    transform = geo_transform_for_center(*DELHI, OPTICAL_GSD_M, OPTICAL_SIZE)
    crs = CRS.from_epsg(4326)
    classes = build_class_raster(OPTICAL_SIZE, BUILDINGS_FAR, WATER_FAR)
    rgb = synth_optical(classes, rng)
    write_geotiff(FIXTURES_DIR / "far_away.tif", rgb, transform, crs, "uint8")


def make_corrupt_tif():
    rng = np.random.default_rng(6)
    arr = rng.integers(0, 255, size=(3, 10, 10), dtype=np.uint8)
    transform = from_origin(0, 0, 1, 1)
    with MemoryFile() as memfile:
        with memfile.open(
            driver="GTiff", height=10, width=10, count=3,
            dtype="uint8", crs=CRS.from_epsg(4326), transform=transform,
        ) as dst:
            dst.write(arr)
        data = memfile.read()

    header = data[:200]
    garbage = rng.integers(0, 255, size=2000, dtype=np.uint8).tobytes()
    (FIXTURES_DIR / "corrupt.tif").write_bytes(header + garbage)


def make_not_geo_png():
    rng = np.random.default_rng(7)
    arr = rng.integers(0, 255, size=(256, 256, 3), dtype=np.uint8)
    Image.fromarray(arr, mode="RGB").save(FIXTURES_DIR / "not_geo.png")


def gsd_of(ds):
    if ds.crs and ds.crs.is_geographic:
        geod = Geod(ellps="WGS84")
        t = ds.transform
        lon0, lat0 = t * (0, 0)
        lon1, lat1 = t * (1, 0)
        lon2, lat2 = t * (0, 1)
        _, _, dx = geod.inv(lon0, lat0, lon1, lat1)
        _, _, dy = geod.inv(lon0, lat0, lon2, lat2)
        return dx, dy
    return abs(ds.transform.a), abs(ds.transform.e)


def verify_geo_file(path):
    with rasterio.open(path) as ds:
        gx, gy = gsd_of(ds)
        return {
            "file": path.name,
            "crs": str(ds.crs),
            "bands": ds.count,
            "gsd": f"{gx:.2f}x{gy:.2f}m",
            "bounds": tuple(round(b, 5) for b in ds.bounds),
        }


def verify_expected_failure(path):
    try:
        with rasterio.open(path) as ds:
            if ds.crs is None:
                return True, "opened but no CRS/geotransform (not usable as geospatial data)"
            return False, "opened successfully WITH a valid CRS (unexpected)"
    except Exception as e:
        return True, f"raised on open as expected: {type(e).__name__}: {e}"


def main():
    print("Generating fixtures...")
    classes_t1, transform, crs = make_optical_pair()
    make_sar(classes_t1, transform, crs)
    make_sentinel_like()
    make_far_away()
    make_corrupt_tif()
    make_not_geo_png()
    print("Done.\n")

    geo_files = ["optical_t1.tif", "optical_t2.tif", "sar_t1.tif", "sentinel_like.tif", "far_away.tif"]
    rows = []
    for name in geo_files:
        row = verify_geo_file(FIXTURES_DIR / name)
        rows.append(row)
        print(f"OK  {name}: opened successfully")

    for name in ["corrupt.tif", "not_geo.png"]:
        ok, detail = verify_expected_failure(FIXTURES_DIR / name)
        status = "OK" if ok else "FAIL"
        print(f"{status}  {name}: {detail}")

    print("\nSummary:")
    header = f"{'file':<20}{'crs':<14}{'bands':<7}{'gsd':<14}{'bounds'}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(f"{row['file']:<20}{row['crs']:<14}{row['bands']:<7}{row['gsd']:<14}{row['bounds']}")


if __name__ == "__main__":
    main()
