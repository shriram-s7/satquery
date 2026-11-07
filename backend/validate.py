"""Trust Gate: input validation and typed rejections for uploaded imagery."""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union

from backend.geo import RasterInfo, guess_modality, spatial_overlap

MIN_GSD_M = 0.1
MAX_GSD_M = 100.0
MIN_OVERLAP_IOU = 0.30
PAIR_INTENTS = ("change_detection", "fusion")


class RejectionCode(Enum):
    NOT_GEOSPATIAL = "NOT_GEOSPATIAL"
    UNREADABLE = "UNREADABLE"
    WRONG_IMAGE_COUNT = "WRONG_IMAGE_COUNT"
    NO_SPATIAL_OVERLAP = "NO_SPATIAL_OVERLAP"
    CRS_MISMATCH = "CRS_MISMATCH"
    MODALITY_MISMATCH = "MODALITY_MISMATCH"
    BAND_COUNT_UNSUPPORTED = "BAND_COUNT_UNSUPPORTED"
    RESOLUTION_OUT_OF_RANGE = "RESOLUTION_OUT_OF_RANGE"


@dataclass
class ValidationResult:
    ok: bool
    code: Optional[RejectionCode]
    message: str
    remedy: str
    severity: str  # "reject" | "warn"


@dataclass
class UnreadableRaster:
    """Placeholder for a file that failed to open; callers build this from a caught exception."""
    path: str
    error: str
    display_name: Optional[str] = None


RasterLike = Union[RasterInfo, UnreadableRaster]


def _display(item: RasterLike) -> str:
    name = getattr(item, "display_name", None)
    return name or Path(item.path).name


def _centroid(info: RasterInfo):
    minlon, minlat, maxlon, maxlat = info.bounds_wgs84
    return ((minlon + maxlon) / 2, (minlat + maxlat) / 2)


def _format_latlon(lon: float, lat: float) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{abs(lat):.2f}{ns} {abs(lon):.2f}{ew}"


def validate_inputs(rasters: List[RasterLike], query: str, intent: str) -> List[ValidationResult]:
    results: List[ValidationResult] = []

    if len(rasters) == 0:
        return [ValidationResult(
            ok=False,
            code=RejectionCode.WRONG_IMAGE_COUNT,
            message="REJECTED — 0 images were provided. SatQuery needs at least 1 image "
                    "(2 for change-detection or fusion queries).",
            remedy="Upload 1 GeoTIFF/PNG image, or 2 images for change detection / fusion queries.",
            severity="reject",
        )]

    valid_geo: List[RasterInfo] = []
    for idx, item in enumerate(rasters):
        label = f"image {idx + 1}"

        if isinstance(item, UnreadableRaster):
            results.append(ValidationResult(
                ok=False,
                code=RejectionCode.UNREADABLE,
                message=f"REJECTED — {label} ('{_display(item)}') could not be opened: {item.error}",
                remedy="Re-export the file as a valid GeoTIFF/PNG and re-upload; "
                       "the file may be truncated or corrupted.",
                severity="reject",
            ))
            continue

        info = item

        if not info.has_geo:
            results.append(ValidationResult(
                ok=False,
                code=RejectionCode.NOT_GEOSPATIAL,
                message=f"REJECTED — {label} ('{_display(info)}') has no usable CRS/geotransform "
                        f"(crs={info.crs}, has_geo={info.has_geo}); it cannot be geolocated.",
                remedy="Upload a georeferenced GeoTIFF (with an embedded CRS and transform) "
                       "instead of a plain image.",
                severity="reject",
            ))
            continue

        modality = guess_modality(info)
        if modality == "unknown":
            results.append(ValidationResult(
                ok=False,
                code=RejectionCode.BAND_COUNT_UNSUPPORTED,
                message=f"REJECTED — {label} ('{_display(info)}') has {info.band_count} band(s) of "
                        f"dtype '{info.dtype}', which matches no supported modality "
                        f"(3-band uint8 optical RGB, 1-band float32 SAR, >=4-band uint16 "
                        f"multispectral, 1-band uint8/uint16 panchromatic).",
                remedy="Upload imagery in one of the supported band-count/dtype combinations.",
                severity="reject",
            ))

        if info.gsd_metres is not None:
            gx, gy = info.gsd_metres
            if not (MIN_GSD_M <= gx <= MAX_GSD_M) or not (MIN_GSD_M <= gy <= MAX_GSD_M):
                results.append(ValidationResult(
                    ok=False,
                    code=RejectionCode.RESOLUTION_OUT_OF_RANGE,
                    message=f"REJECTED — {label} ('{_display(info)}') has GSD {gx:.3f}m x {gy:.3f}m, "
                            f"outside the supported range of {MIN_GSD_M}m-{MAX_GSD_M}m.",
                    remedy=f"Provide imagery with a GSD between {MIN_GSD_M}m and {MAX_GSD_M}m, "
                           f"or resample it before upload.",
                    severity="reject",
                ))

        valid_geo.append(info)

    if intent in PAIR_INTENTS and len(rasters) == 1:
        results.append(ValidationResult(
            ok=False,
            code=RejectionCode.WRONG_IMAGE_COUNT,
            message=f"REJECTED — intent '{intent}' requires 2 images, but only 1 was provided.",
            remedy="Upload a second image (the 'after' image for change detection, "
                   "or the second modality for fusion).",
            severity="reject",
        ))

    if len(valid_geo) == 2:
        a, b = valid_geo
        iou = spatial_overlap(a, b)
        lon_a, lat_a = _centroid(a)
        lon_b, lat_b = _centroid(b)

        if iou < MIN_OVERLAP_IOU:
            results.append(ValidationResult(
                ok=False,
                code=RejectionCode.NO_SPATIAL_OVERLAP,
                message=f"REJECTED — spatial overlap {iou:.2f}. Image A centroid "
                        f"{_format_latlon(lon_a, lat_a)}, image B centroid "
                        f"{_format_latlon(lon_b, lat_b)}. These are not the same location.",
                remedy=f"Upload two images covering overlapping ground areas "
                       f"(at least {MIN_OVERLAP_IOU:.0%} IoU).",
                severity="reject",
            ))

        if a.crs != b.crs:
            results.append(ValidationResult(
                ok=True,
                code=RejectionCode.CRS_MISMATCH,
                message=f"WARNING — image A CRS is {a.crs}, image B CRS is {b.crs}. "
                        f"They will be reprojected to a common CRS before comparison.",
                remedy="No action required; SatQuery reprojects automatically. "
                       "For best accuracy, supply both images in the same CRS.",
                severity="warn",
            ))

        if intent == "fusion":
            mod_a, mod_b = guess_modality(a), guess_modality(b)
            if mod_a == mod_b:
                results.append(ValidationResult(
                    ok=False,
                    code=RejectionCode.MODALITY_MISMATCH,
                    message=f"REJECTED — fusion requires two different modalities, but both "
                            f"images were classified as '{mod_a}' (image A: {a.band_count} "
                            f"band(s) {a.dtype}; image B: {b.band_count} band(s) {b.dtype}).",
                    remedy="Upload two images of different modalities (e.g. optical + SAR) "
                           "for fusion queries.",
                    severity="reject",
                ))

    return results
