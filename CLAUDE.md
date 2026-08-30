# SatQuery AI — Project Rules

## What this is
Agentic vision-language system for satellite imagery. SIH 2026 PS 26167 (ISRO).
User uploads 1-2 GeoTIFF/PNG images + a natural language query. System validates
input, classifies intent, routes to the right model pathway, returns an answer with
visual overlay, geo-anchored coordinates, confidence score, and a full execution trace.

## Environment
Windows 11, PowerShell. Python 3.12 venv at .venv (already active).
Installed: rasterio 1.5.1 (GDAL 3.12.4), fastapi, uvicorn, pyproj, shapely,
numpy, Pillow, pytest, reportlab. Node v20.20.0.
- Always use `python -m pip install`, never bare `pip`.
- Use PowerShell syntax only. No `source`, no `rmdir /s`, no `&&` chaining.
- After adding a dependency, update requirements.txt via `python -m pip freeze`.

## Stack (do not substitute)
- Backend: Python 3.12, FastAPI, uvicorn, rasterio, pyproj, shapely, numpy, Pillow
- Frontend: React + Vite + TailwindCSS + react-leaflet
- No database. In-memory session state only.

## Hard rules
1. The ML model is NOT integrated yet. All model calls go through a single stub
   module `backend/models/stub.py`. Never call a real model anywhere else.
2. Everything geospatial (CRS, GSD, bounds, overlap, resampling) must be REAL
   working code using rasterio/pyproj. Never stub geospatial logic.
3. Every backend response includes a `trace` array: an ordered list of
   {step, detail, duration_ms} recording exactly what the system did.
4. Scoped edits only. When I ask for a change, touch only the files needed.
   Never refactor unrelated code.
5. No code comments unless genuinely non-obvious.
6. If you are unsure whether something is true, say so. Never invent an API,
   parameter, or behaviour you haven't verified.

## Layout
backend/
  main.py            FastAPI app + routes
  geo.py             GeoTIFF reading, CRS, GSD, bounds, overlap
  validate.py        Trust Gate — input validation and typed rejections
  gsd.py             GSD-adaptive preprocessing
  intent.py          Query intent classification
  orchestrator.py    The agent: validate -> classify -> route -> merge
  models/stub.py     Placeholder model outputs
frontend/            Vite React app
fixtures/            Synthetic test GeoTIFFs
