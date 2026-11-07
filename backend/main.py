"""FastAPI app: HTTP routes for SatQuery's agentic pipeline."""
import base64
import tempfile
from io import BytesIO
from pathlib import Path
from typing import List

import numpy as np
import rasterio
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image
from rasterio.enums import Resampling

from backend.geo import guess_modality, read_raster
from backend.orchestrator import run_query
from backend.report import build_report_pdf

PREVIEW_MAX_DIM = 1024


def _stretch_to_uint8(band: np.ndarray) -> np.ndarray:
    finite = band[np.isfinite(band)]
    if finite.size == 0:
        return np.zeros(band.shape, dtype=np.uint8)
    lo, hi = np.percentile(finite, [2, 98])
    if hi <= lo:
        lo, hi = float(finite.min()), float(finite.max())
    if hi <= lo:
        return np.zeros(band.shape, dtype=np.uint8)
    stretched = np.clip((band - lo) / (hi - lo), 0, 1)
    return (stretched * 255).astype(np.uint8)


def render_preview_data_url(path: str) -> str:
    with rasterio.open(path) as ds:
        h, w = ds.height, ds.width
        scale = min(1.0, PREVIEW_MAX_DIM / max(h, w))
        out_h, out_w = max(1, round(h * scale)), max(1, round(w * scale))
        resampling = Resampling.average if scale < 1.0 else Resampling.nearest

        if ds.count >= 3 and ds.dtypes[0] == "uint8":
            arr = ds.read([1, 2, 3], out_shape=(3, out_h, out_w), resampling=resampling)
            rgb = np.transpose(arr, (1, 2, 0))
        elif ds.count >= 3:
            arr = ds.read([1, 2, 3], out_shape=(3, out_h, out_w), resampling=resampling)
            rgb = np.dstack([_stretch_to_uint8(arr[i]) for i in range(3)])
        else:
            band = ds.read(1, out_shape=(out_h, out_w), resampling=resampling)
            gray = _stretch_to_uint8(band)
            rgb = np.dstack([gray, gray, gray])

    image = Image.fromarray(rgb, mode="RGB")
    buf = BytesIO()
    image.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"

app = FastAPI(title="SatQuery AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/inspect")
async def handle_inspect(file: UploadFile = File(...)):
    with tempfile.TemporaryDirectory() as tmp_dir:
        dest = Path(tmp_dir) / file.filename
        dest.write_bytes(await file.read())

        try:
            info = read_raster(str(dest), display_name=file.filename)
            preview_data_url = render_preview_data_url(str(dest))
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"{type(e).__name__}: {e}")

    centroid = None
    if info.bounds_wgs84:
        minlon, minlat, maxlon, maxlat = info.bounds_wgs84
        centroid = {"lon": (minlon + maxlon) / 2, "lat": (minlat + maxlat) / 2}

    return {
        "filename": file.filename,
        "has_geo": info.has_geo,
        "crs": info.crs,
        "gsd_metres": info.gsd_metres,
        "band_count": info.band_count,
        "dtype": info.dtype,
        "width": info.width,
        "height": info.height,
        "modality": guess_modality(info) if info.has_geo else None,
        "bounds_wgs84": info.bounds_wgs84,
        "centroid": centroid,
        "preview_data_url": preview_data_url,
    }


@app.post("/api/query")
async def handle_query(files: List[UploadFile] = File(...), query: str = Form(...)):
    if not (1 <= len(files) <= 2):
        raise HTTPException(status_code=400, detail="SatQuery accepts 1-2 images per query.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        saved_files = []
        for upload in files:
            dest = Path(tmp_dir) / upload.filename
            dest.write_bytes(await upload.read())
            saved_files.append((str(dest), upload.filename))

        return run_query(saved_files, query)


@app.post("/api/report")
async def handle_report(payload: dict = Body(...)):
    response = payload.get("response")
    if not isinstance(response, dict):
        raise HTTPException(
            status_code=400,
            detail="Request body must include a 'response' object (the QueryResponse from /api/query).",
        )
    images = payload.get("images") or []

    pdf_bytes = build_report_pdf(response, images)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="satquery-report.pdf"'},
    )
