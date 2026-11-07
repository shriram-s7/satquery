"""PDF export for a QueryResponse, using reportlab.

Consumes the same JSON shape POST /api/query returns, plus the per-image
metadata (including preview thumbnails) POST /api/inspect already returned to
the frontend for each uploaded file — that metadata isn't part of QueryResponse
itself, so the caller supplies it alongside the response.
"""
import base64
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from PIL import Image as PILImage, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = colors.HexColor("#0e1626")
CYAN = colors.HexColor("#0e7490")
MUTED = colors.HexColor("#5b6b7d")
GRID = colors.HexColor("#cbd5e1")
STRIPE = colors.HexColor("#f1f5f9")

_STYLES = getSampleStyleSheet()
TITLE_STYLE = ParagraphStyle("SQTitle", parent=_STYLES["Title"], textColor=NAVY, fontSize=20, spaceAfter=2)
HEADING_STYLE = ParagraphStyle("SQHeading2", parent=_STYLES["Heading2"], textColor=NAVY, spaceBefore=14, spaceAfter=6)
BODY_STYLE = ParagraphStyle("SQBody", parent=_STYLES["BodyText"], fontSize=10, leading=14)
MONO_STYLE = ParagraphStyle("SQMono", parent=_STYLES["Code"], fontName="Courier", fontSize=8, leading=11, textColor=MUTED)
CELL_STYLE = ParagraphStyle("SQCell", fontSize=7.5, leading=10, textColor=colors.HexColor("#111827"))


def _esc(value: Any) -> str:
    return escape(str(value if value is not None else ""))


def _cell(value: Any) -> Paragraph:
    return Paragraph(_esc(value), CELL_STYLE)


def _basename(path: str) -> str:
    return (path or "").replace("\\", "/").rsplit("/", 1)[-1]


def _table_style(header_bg=NAVY) -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, STRIPE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


def _project(lon: float, lat: float, bounds: List[float]) -> tuple:
    west, south, east, north = bounds
    x = (lon - west) / (east - west) if east != west else 0.5
    y = (north - lat) / (north - south) if north != south else 0.5
    return x, y


def _regions_for_image(overlay_regions: List[Dict[str, Any]], filename: str) -> List[Dict[str, Any]]:
    if not filename:
        return []
    return [r for r in overlay_regions if (r.get("source_image") or "").endswith(filename)]


def _render_overlay_png(image_meta: Dict[str, Any], regions: List[Dict[str, Any]]) -> Optional[bytes]:
    data_url = image_meta.get("preview_data_url")
    if not data_url or "," not in data_url:
        return None

    _, b64 = data_url.split(",", 1)
    base = PILImage.open(BytesIO(base64.b64decode(b64))).convert("RGB")
    draw = ImageDraw.Draw(base, "RGBA")
    bounds = image_meta.get("bounds_wgs84")
    w, h = base.size

    if bounds:
        for idx, region in enumerate(regions):
            ring = region.get("bbox_wgs84") or []
            if not ring:
                continue
            lons = [p[0] for p in ring]
            lats = [p[1] for p in ring]
            x0, y0 = _project(min(lons), max(lats), bounds)
            x1, y1 = _project(max(lons), min(lats), bounds)
            rect = (x0 * w, y0 * h, x1 * w, y1 * h)
            draw.rectangle(rect, outline=(34, 211, 238, 255), width=3)

            label = f"#{idx + 1} - {region.get('confidence', 0):.2f}"
            label_h = 14
            label_top = max(0, rect[1] - label_h)
            draw.rectangle((rect[0], label_top, rect[0] + 7 * len(label) + 6, label_top + label_h),
                            fill=(4, 7, 13, 220))
            draw.text((rect[0] + 3, label_top + 2), label, fill=(34, 211, 238, 255))

    buf = BytesIO()
    base.save(buf, format="PNG")
    return buf.getvalue()


def _flowable_image(png_bytes: bytes, max_width_mm: float = 150.0) -> RLImage:
    rl_img = RLImage(BytesIO(png_bytes))
    max_w = max_width_mm * mm
    ratio = rl_img.imageHeight / float(rl_img.imageWidth)
    rl_img.drawWidth = max_w
    rl_img.drawHeight = max_w * ratio
    return rl_img


EVIDENCE_COL_WIDTH_MM = 80.0
EVIDENCE_COL_GUTTER_MM = 6.0


def _evidence_table(images: List[Dict[str, Any]], overlay_regions: List[Dict[str, Any]]) -> Optional[Table]:
    cells = []
    for img in images:
        regions = _regions_for_image(overlay_regions, img.get("filename", ""))
        png_bytes = _render_overlay_png(img, regions)
        if not png_bytes:
            continue
        cells.append([
            Paragraph(_esc(img.get("filename", "")), MONO_STYLE),
            _flowable_image(png_bytes, max_width_mm=EVIDENCE_COL_WIDTH_MM),
        ])

    if not cells:
        return None

    rows = [cells[i:i + 2] for i in range(0, len(cells), 2)]
    for row in rows:
        if len(row) == 1:
            row.append([])

    col_width = (EVIDENCE_COL_WIDTH_MM + EVIDENCE_COL_GUTTER_MM) * mm
    table = Table(rows, colWidths=[col_width, col_width], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), EVIDENCE_COL_GUTTER_MM * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def build_report_pdf(response: Dict[str, Any], images: Optional[List[Dict[str, Any]]] = None) -> bytes:
    images = images or []
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=20 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    story = []

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    story.append(Paragraph("SatQuery AI &mdash; Analysis Report", TITLE_STYLE))
    story.append(Paragraph(_esc(f"Generated {generated_at}"), MONO_STYLE))
    story.append(Spacer(1, 10))

    if images:
        story.append(Paragraph("Input imagery", HEADING_STYLE))
        rows = [["File", "CRS", "GSD (m/px)", "Bands", "Size", "Modality", "Centroid (WGS84)"]]
        for img in images:
            gsd = img.get("gsd_metres")
            gsd_label = f"{gsd[0]:.2f} x {gsd[1]:.2f}" if gsd else "n/a"
            centroid = img.get("centroid")
            centroid_label = f"{centroid['lat']:.4f}, {centroid['lon']:.4f}" if centroid else "n/a"
            rows.append([
                _cell(img.get("filename", "n/a")),
                _cell(img.get("crs") or "n/a"),
                _cell(gsd_label),
                _cell(f"{img.get('band_count', 'n/a')} x {img.get('dtype', '')}"),
                _cell(f"{img.get('width', '?')} x {img.get('height', '?')}"),
                _cell(img.get("modality") or "n/a"),
                _cell(centroid_label),
            ])
        table = Table(rows, hAlign="LEFT", repeatRows=1)
        table.setStyle(_table_style())
        story.append(table)

    intent = response.get("intent") or {}
    validations = response.get("validations") or []

    if response.get("rejected"):
        story.append(Paragraph("Rejected by the Trust Gate", HEADING_STYLE))
        for v in validations:
            if v.get("severity") != "reject":
                continue
            story.append(Paragraph(f"<b>{_esc(v.get('code'))}</b>", BODY_STYLE))
            story.append(Paragraph(_esc(v.get("message", "")), BODY_STYLE))
            story.append(Paragraph(f"<i>Remedy:</i> {_esc(v.get('remedy', ''))}", BODY_STYLE))
            story.append(Spacer(1, 6))
    else:
        story.append(Paragraph("Answer", HEADING_STYLE))
        story.append(Paragraph(
            f"Intent: <b>{_esc(intent.get('intent', 'n/a'))}</b> "
            f"({_esc(intent.get('method', 'n/a'))}, "
            f"confidence {intent.get('confidence', 0) * 100:.0f}%)",
            BODY_STYLE,
        ))
        story.append(Spacer(1, 4))
        story.append(Paragraph(_esc(response.get("answer_text", "")), BODY_STYLE))
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Overall confidence: <b>{response.get('confidence', 0) * 100:.0f}%</b>", BODY_STYLE))

        overlay_regions = response.get("overlay_regions") or []

        if images:
            evidence_table = _evidence_table(images, overlay_regions)
            if evidence_table:
                story.append(Paragraph("Evidence", HEADING_STYLE))
                story.append(evidence_table)
                story.append(Spacer(1, 4))

        if overlay_regions:
            story.append(Paragraph("Detected regions", HEADING_STYLE))
            rows = [["#", "Source", "Tile", "Confidence", "WGS84 bbox (min lon, min lat, max lon, max lat)"]]
            for idx, region in enumerate(overlay_regions):
                ring = region.get("bbox_wgs84") or []
                if ring:
                    lons = [p[0] for p in ring]
                    lats = [p[1] for p in ring]
                    bbox_label = f"{min(lons):.5f}, {min(lats):.5f}, {max(lons):.5f}, {max(lats):.5f}"
                else:
                    bbox_label = "n/a"
                rows.append([
                    str(idx + 1),
                    _cell(_basename(region.get("source_image", ""))),
                    str(tuple(region.get("tile_index", []))),
                    f"{region.get('confidence', 0):.2f}",
                    _cell(bbox_label),
                ])
            table = Table(rows, hAlign="LEFT", repeatRows=1,
                           colWidths=[10 * mm, 45 * mm, 18 * mm, 22 * mm, 79 * mm])
            table.setStyle(_table_style())
            story.append(table)

    normalization_plan = response.get("normalization_plan") or []
    if normalization_plan:
        story.append(Paragraph("GSD normalization", HEADING_STYLE))
        for plan in normalization_plan:
            story.append(Paragraph(
                f"<b>{_esc(_basename(plan.get('path', '')))}</b> &mdash; {_esc(plan.get('rationale', ''))}",
                BODY_STYLE,
            ))
            story.append(Spacer(1, 4))

    trace = response.get("trace") or []
    if trace:
        story.append(Paragraph("Execution trace", HEADING_STYLE))
        rows = [["Step", "Detail", "Duration (ms)"]]
        for entry in trace:
            rows.append([
                _cell(entry.get("step", "")),
                _cell(entry.get("detail", "")),
                f"{entry.get('duration_ms', 0):.2f}",
            ])
        table = Table(rows, hAlign="LEFT", repeatRows=1, colWidths=[30 * mm, 110 * mm, 24 * mm])
        table.setStyle(_table_style())
        story.append(table)

    doc.build(story)
    return buf.getvalue()
