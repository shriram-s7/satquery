# Fixture ground truth: optical_t1.tif / optical_t2.tif

Source of truth: the literal `BUILDINGS_T1`, `BUILDINGS_T2_EXTRA`, and `WATER_T1`
constants in `fixtures/generate.py`, plus the `scaled_water_class_raster(..., factor=0.6)`
call used to build T2's water class. This file was derived by reading those constants
and re-deriving geometry with `shapely`/`backend.geo.bbox_to_geojson` — not by
re-running the generator and not by thresholding pixel colours (which would pick up
anti-aliasing/noise artefacts at edges).

All pixel bboxes are `(x0, y0, x1, y1)` in `(col, row)` order, top-left origin,
`x1`/`y1` exclusive (matches Python slicing: `classes[y0:y1, x0:x1] = 1`).
Both images are 512x512 px, 0.65 m/px, EPSG:4326, centered on `CHENNAI = (80.27, 13.08)`,
with the **same geotransform** — T1 and T2 pixel coordinates are directly comparable.

## Buildings — T1 (`BUILDINGS_T1`)

| # | pixel bbox (x0, y0, x1, y1) |
|---|------------------------------|
| 1 | (40, 40, 90, 80)     |
| 2 | (400, 60, 460, 110)  |
| 3 | (60, 420, 110, 470)  |
| 4 | (380, 400, 440, 450) |
| 5 | (200, 60, 240, 100)  |

## Buildings — T2 (`BUILDINGS_T1 + BUILDINGS_T2_EXTRA`)

| # | pixel bbox (x0, y0, x1, y1) | status |
|---|------------------------------|--------|
| 1 | (40, 40, 90, 80)     | carried over from T1 |
| 2 | (400, 60, 460, 110)  | carried over from T1 |
| 3 | (60, 420, 110, 470)  | carried over from T1 |
| 4 | (380, 400, 440, 450) | carried over from T1 |
| 5 | (200, 60, 240, 100)  | carried over from T1 |
| 6 | (250, 430, 300, 470) | **NEW** |
| 7 | (420, 220, 470, 270) | **NEW** |

No T1 building is removed, resized, or moved in T2 — `BUILDINGS_T2_EXTRA` is
additive.

## Water polygon

`WATER_T1` is a 9-vertex polygon, rasterized with `Affine.identity()` — its listed
coordinates are already pixel (x, y) coordinates, not geographic ones.

**T1** — `WATER_T1` vertices:
`(140,300) (210,255) (290,260) (330,300) (345,350) (300,400) (220,410) (150,380) (120,340)`

- pixel bbox (x0, y0, x1, y1): **(120.0, 255.0, 345.0, 410.0)**
- polygon area: **25225.0 px²**

**T2** — `WATER_T1` scaled by `xfact=0.6, yfact=0.6, origin="centroid"` (shapely
`affinity.scale`), same centroid, linear scale 0.6 → area scale 0.6² = 0.36:

- pixel bbox (x0, y0, x1, y1): **(166.4, 286.1, 301.4, 379.1)**
- polygon area: **9081.0 px²**
- area ratio T2/T1: **0.360** → **64.0% reduction** (geometric, exact from the 0.6 scale factor)

## Measured pixel counts (rasterized class array, from prior verification run)

| class | T1 | T2 | change |
|-------|------|------|--------|
| water (class 2) | 25240 | 9087 | -64% |
| built (class 1) | 12100 | 16600 | +37% (2 new buildings, 2500px + 2500px added) |

These match the geometric polygon figures above (25225→9081, ratio 0.360); the
small delta (25240 vs 25225, 9087 vs 9081) is rasterization of the polygon edge,
not a different shape. **Do not regenerate the fixtures** — current files are
correct, the 64% figure (not the originally-planned 40%) is the true value baked
into `optical_t2.tif`, and all existing tests pass against it.

## WGS84 bounding boxes for the two NEW buildings

Computed via `backend.geo.bbox_to_geojson(read_raster("fixtures/optical_t2.tif"), (row_min, col_min, row_max, col_max))`,
`(minlon, minlat, maxlon, maxlat)`:

| # | pixel bbox (x0,y0,x1,y1) | WGS84 bbox (minlon, minlat, maxlon, maxlat) |
|---|---------------------------|-----------------------------------------------|
| 6 | (250, 430, 300, 470) | (80.269964, 13.078750, 80.270264, 13.078984) |
| 7 | (420, 220, 470, 270) | (80.270983, 13.079918, 80.271283, 13.080210) |

## WGS84 bounding box for the water body (for reference)

| | pixel bbox (x0,y0,x1,y1) | WGS84 bbox (minlon, minlat, maxlon, maxlat) |
|---|---------------------------|-----------------------------------------------|
| T1 extent | (120, 255, 345, 410) | (80.269185, 13.079101, 80.270534, 13.080006) |
| T2 extent (receded) | (166, 286, 302, 380) | (80.269460, 13.079276, 80.270276, 13.079825) |

## Change summary

Between T1 and T2, two new built-up structures appear — a ~50x40 px building near
the southeast built-up cluster (#6, adjacent to the existing building at (60,420,110,470))
and a ~50x50 px building near the northeast cluster (#7, adjacent to (400,60,460,110)) —
while the water body at the scene's center contracts substantially, shrinking to
36% of its original area (a 64% reduction) around the same centroid, consistent
with a drying/reclamation event rather than a shift in location. All five original
T1 buildings are unchanged in position and size.
