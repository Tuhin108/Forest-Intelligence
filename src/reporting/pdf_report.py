"""
One-page PDF summary report. Deliberately plain and text-first -- this is a
downloadable record of what the tool found, not a marketing document, and
every figure in it is pulled directly from the same ForestMetrics object the
on-screen dashboard uses (so the PDF can never say something the UI doesn't).
"""
from __future__ import annotations

import datetime
import io

from fpdf import FPDF


def _clean(text: str) -> str:
    """fpdf2's default Helvetica font is latin-1 only; swap the handful of
    unicode punctuation we use elsewhere (checkmarks, em-dash, arrows) for
    plain ASCII so report generation never throws an encoding error."""
    repl = {
        "\u2014": "-", "\u2013": "-", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2192": "->", "\u2713": "[OK]", "\u26a0": "[!]", "\u00b2": "^2", "\u2026": "...",
        "\u2260": "!=", "\u2265": ">=", "\u2264": "<=", "\u00b1": "+/-",
    }
    for k, v in repl.items():
        text = text.replace(k, v)
    # Safety net: strip anything else outside latin-1 rather than risk a crash
    # on some future limitation/reason string with an unanticipated character.
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _mc(pdf: FPDF, h: float, text: str):
    """multi_cell(width=0,...) leaves the x-cursor at the right margin instead
    of resetting it (unlike cell(...,ln=True)) -- calling this twice in a row
    without resetting x raises 'Not enough horizontal space to render a single
    character'. Always reset x to the left margin first."""
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, h, text)


def build_pdf_report(
    metrics,
    image_name: str,
    reliability_reasons: list,
    limitations: list,
    story_text: str,
    annotated_image: bytes | None = None,
) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "Forest Intelligence -- Analysis Report", ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, _clean(f"Source image: {image_name}  |  Processed: "
                          f"{datetime.date.today().isoformat()}"), ln=True)
    pdf.ln(4)
    pdf.set_text_color(0, 0, 0)

    if annotated_image:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Detection Snapshot", ln=True)
        pdf.image(io.BytesIO(annotated_image), x=15, w=180)
        pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Forest Overview", ln=True)
    pdf.set_font("Helvetica", "", 11)

    area_line = (f"{metrics.canopy_area_m2:,.0f} m^2" if metrics.has_physical_units
                 else f"{metrics.coverage_pct:.0f}% of analyzed image (pixel-based, no "
                      f"physical scale available)")
    rows = [
        ("Trees detected", f"{metrics.tree_count}"),
        ("Estimated canopy coverage", f"{metrics.coverage_pct:.0f}%"),
        ("Estimated canopy area", area_line),
        ("Reliability", metrics.reliability),
    ]
    if metrics.has_physical_units:
        rows.append(("Analyzed area", f"{metrics.analyzed_area_m2:,.0f} m^2"))
    for label, value in rows:
        pdf.cell(70, 7, _clean(label), border=0)
        pdf.cell(0, 7, _clean(str(value)), ln=True)

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Summary", ln=True)
    pdf.set_font("Helvetica", "", 11)
    _mc(pdf, 6, _clean(story_text))

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Reliability Notes", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for reason in reliability_reasons:
        _mc(pdf, 5.5, _clean(f"- {reason}"))

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Review Areas", ln=True)
    pdf.set_font("Helvetica", "", 10)
    rf = metrics.review_flags
    _mc(pdf, 5.5, _clean(
        f"- {rf.get('overlap', 0)} dense-overlap regions\n"
        f"- {rf.get('low_confidence', 0)} low-confidence detections\n"
        f"- {rf.get('shadow', 0)} shadow-affected regions"
    ))

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Known Limitations", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for lim in limitations:
        _mc(pdf, 5.5, _clean(f"- {lim}"))

    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    _mc(pdf, 5, _clean(
        "This report does not estimate species, biomass, ecological health, or "
        "carbon stock/sequestration -- these require data and methodology beyond "
        "crown detection and are not claimed here."
    ))

    out = pdf.output()
    return bytes(out)
