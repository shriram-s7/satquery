"""Real geospatial primitives for SatQuery: CRS, GSD, bounds, overlap, pixel<->lonlat."""
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import rasterio
from affine import Affine
from pyproj import CRS as PyprojCRS
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.warp import transform_bounds
from shapely.geometry import box


@dataclass
class RasterInfo:
    path: str
    driver: str
    crs: Optional[str]
    width: int
    height: int
    band_count: int
    dtype: str
    transform: Affine
    bounds_native: Tuple[float, float, float, float]
    bounds_wgs84: Optional[Tuple[float, float, float, float]]
    gsd_metres: Optional[Tuple[float, float]]
    has_geo: bool
    nodata: Optional[float]


def _crs_to_epsg_string(crs: CRS) -> str:
    epsg = crs.to_epsg()
    return f"EPSG:{epsg}" if epsg is not None else crs.to_string()


def _utm_epsg_for_lonlat(lon: float, lat: float) -> int:
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def _compute_gsd_metres(crs: CRS, transform: Affine, width: int, height: int) -> Tuple[float, float]:
    if crs.is_geographic:
        left, bottom, right, top = rasterio.transform.array_bounds(height, width, transform)
        center_lon = (left + right) / 2
        center_lat = (bottom + top) / 2
        utm_crs = CRS.from_epsg(_utm_epsg_for_lonlat(center_lon, center_lat))
        transformer = Transformer.from_crs(crs, utm_crs, always_xy=True)
        x0, y0 = transformer.transform(*(transform @ (0, 0)))
        x1, y1 = transformer.transform(*(transform @ (1, 0)))
        x2, y2 = transformer.transform(*(transform @ (0, 1)))
        gsd_x = math.hypot(x1 - x0, y1 - y0)
        gsd_y = math.hypot(x2 - x0, y2 - y0)
        return (gsd_x, gsd_y)

    unit_factor = 1.0
    axis_info = PyprojCRS.from_wkt(crs.to_wkt()).axis_info
    if axis_info:
        conv = axis_info[0].unit_conversion_factor
        if conv:
            unit_factor = conv
    return (abs(transform.a) * unit_factor, abs(transform.e) * unit_factor)


def read_raster(path) -> RasterInfo:
    path_str = str(path)
    with rasterio.open(path_str) as ds:
        crs = ds.crs
        transform = ds.transform
        has_geo = crs is not None and transform is not None and transform != Affine.identity()

        crs_str = _crs_to_epsg_string(crs) if crs is not None else None
        bounds_native = tuple(ds.bounds)

        bounds_wgs84 = None
        gsd_metres = None
        if has_geo:
            bounds_wgs84 = to_wgs84_bounds(bounds_native, crs)
            gsd_metres = _compute_gsd_metres(crs, transform, ds.width, ds.height)

        return RasterInfo(
            path=path_str,
            driver=ds.driver,
            crs=crs_str,
            width=ds.width,
            height=ds.height,
            band_count=ds.count,
            dtype=ds.dtypes[0] if ds.dtypes else "",
            transform=transform,
            bounds_native=bounds_native,
            bounds_wgs84=bounds_wgs84,
            gsd_metres=gsd_metres,
            has_geo=has_geo,
            nodata=ds.nodata,
        )


def to_wgs84_bounds(bounds, src_crs) -> Tuple[float, float, float, float]:
    if src_crs is None:
        raise ValueError("src_crs is required to reproject bounds to WGS84")
    crs = src_crs if isinstance(src_crs, CRS) else CRS.from_user_input(src_crs)
    left, bottom, right, top = bounds
    minlon, minlat, maxlon, maxlat = transform_bounds(crs, CRS.from_epsg(4326), left, bottom, right, top)
    return (minlon, minlat, maxlon, maxlat)


def spatial_overlap(a: RasterInfo, b: RasterInfo) -> float:
    if not a.bounds_wgs84 or not b.bounds_wgs84:
        return 0.0
    box_a = box(*a.bounds_wgs84)
    box_b = box(*b.bounds_wgs84)
    if not box_a.intersects(box_b):
        return 0.0
    inter_area = box_a.intersection(box_b).area
    union_area = box_a.union(box_b).area
    if union_area == 0:
        return 0.0
    return inter_area / union_area


def _crs_of(info: RasterInfo) -> CRS:
    if info.crs is None:
        raise ValueError(f"{info.path} has no CRS")
    return CRS.from_user_input(info.crs)


def pixel_to_lonlat(info: RasterInfo, row: int, col: int) -> Tuple[float, float]:
    crs = _crs_of(info)
    x, y = info.transform @ (col + 0.5, row + 0.5)
    if crs.to_epsg() == 4326:
        return (x, y)
    transformer = Transformer.from_crs(crs, CRS.from_epsg(4326), always_xy=True)
    lon, lat = transformer.transform(x, y)
    return (lon, lat)


def bbox_to_geojson(info: RasterInfo, bbox_pixels: Tuple[int, int, int, int]) -> Dict[str, Any]:
    row_min, col_min, row_max, col_max = bbox_pixels
    crs = _crs_of(info)
    transformer = None
    if crs.to_epsg() != 4326:
        transformer = Transformer.from_crs(crs, CRS.from_epsg(4326), always_xy=True)

    corners_px = [
        (col_min, row_min),
        (col_max, row_min),
        (col_max, row_max),
        (col_min, row_max),
        (col_min, row_min),
    ]
    ring = []
    for col, row in corners_px:
        x, y = info.transform @ (col, row)
        if transformer is not None:
            x, y = transformer.transform(x, y)
        ring.append([x, y])

    return {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [ring],
        },
    }


def guess_modality(info: RasterInfo) -> str:
    bands = info.band_count
    dtype = info.dtype

    if bands == 3 and dtype == "uint8":
        return "optical_rgb"
    if bands == 1 and dtype == "float32":
        return "sar"
    if bands >= 4 and dtype == "uint16":
        return "multispectral"
    if bands == 1 and dtype in ("uint8", "uint16"):
        return "panchromatic"
    return "unknown"
