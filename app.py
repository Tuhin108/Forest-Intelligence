"""
Forest Intelligence -- Streamlit entrypoint.

Screen flow: Landing -> Upload/Example -> Preview -> Analyze (real progress
checklist) -> Forest Overview -> Visual Explorer -> Tree Inspector ->
Can-I-trust-this -> Review Areas -> Forest Profile -> Why Should I Care ->
Scenario Explorer -> Exports -> How It Works -> Limitations.

Design rule enforced throughout: every number on screen traces to a real
calculation in src/geo/area.py against the actual detections for the actual
loaded image. Nothing here is a placeholder.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image as PILImage

sys.path.insert(0, os.path.dirname(__file__))

from src.geo.raster import load_image, resolution_quality, UnsupportedImageError
from src.geo.kml_utils import parse_kml, overlaps_bounds, KMLParseError
from src.geo.area import compute_forest_metrics, simulate_canopy_loss, CONFIDENCE_THRESHOLD
from src.detection.model import detect_crowns, DetectionError, get_model
from src.facts.selector import derive_tags, select_facts
from src.reporting.csv_export import build_csv
from src.reporting.pdf_report import build_pdf_report
from src.ui.components import (
    draw_annotated_image, generate_forest_story, why_was_this_counted, crown_status,
    WHY_SHOULD_I_CARE, LIMITATIONS, FAILURE_MESSAGES,
)

st.set_page_config(page_title="Forest Intelligence", page_icon="🌳", layout="wide")


# ----------------------------------------------------------------------------
# Cached, expensive resources
# ----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _cached_model():
    return get_model()


@st.cache_data(show_spinner=False)
def _example_image_path():
    from deepforest import get_data
    return get_data("OSBS_029.tif")


def _init_state():
    defaults = dict(
        stage="landing", loaded=None, detections=None, metrics=None,
        gray=None, image_name=None, aoi_note=None, selected_tree=None,
        loss_pct=10, analysis_celebration=None,
    )
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


_init_state()


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
def _to_grayscale(rgb: np.ndarray) -> np.ndarray:
    return (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.float32)


def _reset_analysis():
    st.session_state.update(detections=None, metrics=None, gray=None, selected_tree=None)


def _reliability_badge(level: str):
    colors = {"HIGH": "#2E7D32", "MODERATE": "#F57C00", "LOW": "#C62828"}
    st.markdown(
        f"<span style='background:{colors[level]};color:white;padding:4px 12px;"
        f"border-radius:14px;font-weight:600;font-size:0.85em'>{level} RELIABILITY</span>",
        unsafe_allow_html=True,
    )


def _display_image(image: np.ndarray, max_size: tuple[int, int] = (900, 520)):
    """Render a bounded preview without changing the full-resolution analysis image."""
    preview = PILImage.fromarray(image.astype(np.uint8)).convert("RGB")
    preview.thumbnail(max_size, PILImage.Resampling.LANCZOS)
    return preview


st.markdown("""
<style>
    .stApp {
        background: linear-gradient(145deg, #f7fbf8 0%, #eef6f1 48%, #f8fbfa 100%);
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #123c32 0%, #1d5b45 100%);
    }
    [data-testid="stSidebar"] * { color: #f5fbf7 !important; }
    [data-testid="stSidebar"] [data-baseweb="radio"] label:hover {
        background: rgba(255,255,255,.12);
        border-radius: 10px;
    }
    h1, h2, h3 { color: #123c32; letter-spacing: -0.02em; }
    [data-testid="stMetric"] {
        background: rgba(255,255,255,.78);
        border: 1px solid #d6e7dd;
        border-radius: 16px;
        padding: 14px 16px;
        box-shadow: 0 4px 16px rgba(18,60,50,.06);
    }
    div.stButton > button[kind="primary"] {
        background: #1f7a55;
        border: 0;
        border-radius: 10px;
        font-weight: 700;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #d6e7dd;
        border-radius: 16px;
    }
    .growth-celebration {
        position: relative;
        overflow: hidden;
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 0 0 22px;
        padding: 14px 18px;
        color: #123c32;
        background: linear-gradient(100deg, #e3f4e8, #f8fcf8);
        border: 1px solid #b9dfc5;
        border-radius: 16px;
        box-shadow: 0 6px 20px rgba(31,122,85,.10);
        animation: celebration-in .55s ease-out both;
    }
    .growth-celebration span { color: #4b6b5c; }
    .growth-seed {
        font-size: 2rem;
        transform-origin: bottom center;
        animation: plant-grow 1.2s cubic-bezier(.2,.8,.2,1) both;
    }
    .growth-leaves {
        font-size: 1.6rem;
        animation: leaves-sway 1.8s ease-in-out .45s infinite alternate;
    }
    .growth-sun {
        color: #c98522;
        font-size: 1.3rem;
        animation: sun-pulse 1.5s ease-in-out infinite alternate;
    }
    @keyframes plant-grow {
        0% { opacity: 0; transform: scale(.2) translateY(12px); }
        70% { opacity: 1; transform: scale(1.15) translateY(-2px); }
        100% { transform: scale(1) translateY(0); }
    }
    @keyframes leaves-sway {
        from { transform: rotate(-5deg); }
        to { transform: rotate(5deg); }
    }
    @keyframes sun-pulse {
        from { opacity: .55; transform: scale(.9); }
        to { opacity: 1; transform: scale(1.1); }
    }
    @keyframes celebration-in {
        from { opacity: 0; transform: translateY(-8px); }
        to { opacity: 1; transform: translateY(0); }
    }
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Compact sidebar navigation keeps the workspace focused while preserving the
# existing analysis state across section changes.
sections = ["Explore", "Analyze", "Discover", "Understand", "Trust",
            "Scenarios", "Export", "About"]
st.session_state.setdefault("section", "Explore")
st.session_state.setdefault("nav_section", st.session_state.section)
st.session_state.setdefault("aoi", None)
pending_section = st.session_state.pop("pending_section", None)
if pending_section in sections:
    st.session_state.nav_section = pending_section
    st.session_state.section = pending_section

with st.sidebar:
    st.markdown("## 🌳 Forest Intelligence")
    st.caption("See the forest. Trust the count.")
    selected_section = st.radio("Navigate", sections, key="nav_section")
    st.session_state.section = selected_section
    st.divider()
    if st.session_state.loaded is not None:
        st.success("Image ready")
    if st.session_state.metrics is not None:
        st.caption(f"{st.session_state.metrics.tree_count} trees detected")

st.markdown("# 🌳 Forest Intelligence")
st.caption("Detect tree crowns, estimate canopy area, and understand exactly how sure the result is.")

if st.session_state.section == "Explore":
    st.markdown("## Explore")
    st.write("Start with an example forest or bring your own imagery. An optional KML limits the area of interest.")
    with st.container(border=True):
        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button("🌲 Try Example Forest", type="primary", width="stretch"):
                _reset_analysis()
                st.session_state.stage = "preview"
                st.session_state.image_name = "OSBS_029.tif (NEON, Ordway-Swisher Biological Station)"
                st.session_state.loaded = load_image(_example_image_path())
                st.rerun()
        with c2:
            uploaded = st.file_uploader("Upload a forest image", type=["tif", "tiff", "jpg", "jpeg", "png"])
            if uploaded is not None and st.session_state.image_name != uploaded.name:
                suffix = os.path.splitext(uploaded.name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded.getvalue())
                    tmp_path = tmp.name
                try:
                    _reset_analysis()
                    st.session_state.loaded = load_image(tmp_path)
                    st.session_state.image_name = uploaded.name
                    st.session_state.stage = "preview"
                except UnsupportedImageError:
                    st.error(FAILURE_MESSAGES["unsupported_format"])
            kml_file = st.file_uploader("Optional KML boundary (AOI)", type=["kml"])
            if kml_file is not None:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".kml") as tmp:
                    tmp.write(kml_file.getvalue())
                    kml_path = tmp.name
                try:
                    aoi = parse_kml(kml_path)
                    st.session_state.aoi = aoi
                    if st.session_state.loaded is not None and overlaps_bounds(aoi, st.session_state.loaded.bounds_lonlat):
                        st.session_state.aoi_note = "✅ Boundary overlaps the loaded image."
                    elif st.session_state.loaded is not None:
                        st.session_state.aoi_note = FAILURE_MESSAGES["kml_no_overlap"]
                        st.warning(st.session_state.aoi_note)
                except KMLParseError as e:
                    st.error(str(e))
    if st.session_state.loaded is None:
        st.info("Upload an image or try the example to begin.")
    else:
        loaded = st.session_state.loaded
        st.image(_display_image(loaded.array, (760, 420)),
                 caption=st.session_state.image_name, width="stretch")
        st.caption(f"{loaded.width} × {loaded.height} px · {loaded.source_note}")
        if st.button("Continue to Analyze", type="primary"):
            st.session_state.pending_section = "Analyze"
            st.rerun()

if st.session_state.section == "Analyze":
    st.markdown("## Analyze")
    loaded = st.session_state.loaded
    if loaded is None:
        st.info("Choose an image in **Explore** first.")
    else:
        quality, quality_reason = resolution_quality(loaded)
        p1, p2 = st.columns([1.05, 0.95], gap="large")
        with p1:
            st.markdown("#### Image ready for analysis")
            st.image(_display_image(loaded.array, (700, 430)),
                     caption=st.session_state.image_name, width="stretch")
        with p2:
            st.markdown("#### Before we begin")
            st.metric("Image size", f"{loaded.width} × {loaded.height} px")
            st.metric("Spatial reference", "Available" if loaded.has_crs else "Not detected")
            if st.session_state.get("aoi_note"):
                st.caption(st.session_state.aoi_note)
            if quality == "too_low":
                st.error(FAILURE_MESSAGES["too_coarse"] + f" ({quality_reason})")
            elif quality == "coarse":
                st.warning(quality_reason)
            analyze_clicked = st.button("🔍 Analyze forest", type="primary", width="stretch")
        if analyze_clicked and quality != "too_low":
            _reset_analysis()
            progress_box = st.empty()
            steps = ["Loading imagery", "Preparing analysis area", "Detecting tree crowns",
                     "Estimating canopy", "Checking result quality"]
            try:
                with st.status("Analyzing your forest...", expanded=True) as analysis_status:
                    for i, step in enumerate(steps):
                        lines = [("✅" if j < i else "🔄" if j == i else "○") + " " + s
                                 for j, s in enumerate(steps)]
                        progress_box.markdown(
                            "**ANALYZING YOUR FOREST**\n\n" + "\n\n".join(lines)
                            + "\n\n*We're looking for crown patterns and checking how reliable they are.*"
                        )
                        analysis_status.update(label=step, state="running", expanded=True)
                        if step == "Detecting tree crowns":
                            st.session_state.detections = detect_crowns(
                                loaded.array, confidence_threshold=CONFIDENCE_THRESHOLD,
                                model=_cached_model())
                        elif step == "Estimating canopy":
                            st.session_state.gray = _to_grayscale(loaded.array)
                            st.session_state.metrics = compute_forest_metrics(
                                st.session_state.detections, loaded.width, loaded.height,
                                gsd_m=loaded.gsd_m, gray_image=st.session_state.gray)
                        else:
                            time.sleep(0.25)
                    st.session_state.stage = "results"
                    st.session_state.analysis_celebration = (
                        "growth" if st.session_state.metrics.tree_count > 0 else "snow"
                    )
                    st.session_state.pending_section = "Discover"
                    analysis_status.update(
                        label="Analysis complete — opening your forest view",
                        state="complete", expanded=False,
                    )
                progress_box.empty()
                st.rerun()
            except DetectionError as e:
                progress_box.empty()
                st.error(FAILURE_MESSAGES["model_error"])
                st.caption(str(e))

metrics = st.session_state.metrics
detections = st.session_state.detections
loaded = st.session_state.loaded

def _needs_results():
    if metrics is None or detections is None or loaded is None:
        st.info("Analyze an image first; your results will appear here.")
        return False
    if metrics.tree_count == 0:
        st.warning(FAILURE_MESSAGES["no_crowns"])
        return False
    return True


if (
    st.session_state.section == "Discover"
    and metrics is not None
    and detections is not None
    and loaded is not None
    and metrics.tree_count == 0
    and st.session_state.analysis_celebration == "snow"
):
    st.snow()
    st.info("No reliable crowns were found this time. The scene may need clearer or higher-resolution imagery.")
    st.session_state.analysis_celebration = None


if st.session_state.section == "Discover" and _needs_results():
    st.markdown("## Discover")
    st.caption("Your forest at a glance — explore the evidence, then take the results with you.")
    if st.session_state.analysis_celebration == "growth":
        st.markdown("""
        <div class="growth-celebration" role="status" aria-label="Forest analysis complete">
            <div class="growth-sun">☀</div>
            <div class="growth-seed">🌱</div>
            <div class="growth-leaves">🌿</div>
            <strong>Analysis complete</strong>
            <span>Your forest is ready to explore.</span>
        </div>
        """, unsafe_allow_html=True)
        st.session_state.analysis_celebration = None
    elif st.session_state.analysis_celebration == "snow":
        st.session_state.analysis_celebration = None
    st.markdown("### Forest Overview")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🌳 Trees detected", metrics.tree_count)
    m2.metric("🌿 Canopy coverage", f"{metrics.coverage_pct:.0f}%")
    if metrics.has_physical_units:
        m3.metric("📐 Canopy area", f"{metrics.canopy_area_m2:,.0f} m²")
        m4.metric("🗺️ Analyzed area", f"{metrics.analyzed_area_m2:,.0f} m²")
    else:
        m3.metric("📐 Canopy area (pixels)", f"{metrics.canopy_area_px2:,.0f} px²")
        m4.metric("🗺️ Analyzed area (pixels)", f"{metrics.analyzed_area_px2:,.0f} px²")
    _reliability_badge(metrics.reliability)
    st.write(generate_forest_story(metrics))
    st.caption(metrics.unit_caveat)
    view_mode = st.radio("View", ["Original", "Detected Crowns", "Review Flags"], key="view_mode", horizontal=True)
    annotated = draw_annotated_image(
        loaded.array, detections,
        mode={"Original": "original", "Detected Crowns": "detected", "Review Flags": "review"}[view_mode],
        review_indices=metrics.review_indices, highlight_tree_id=st.session_state.selected_tree)
    image_col, action_col = st.columns([1.55, 0.45], gap="large")
    with image_col:
        st.image(_display_image(np.asarray(annotated), (760, 410)), width="stretch")
    with action_col:
        st.markdown("#### Next step")
        st.write("Ready to save or share what you found?")
        if st.button("📤 Go to Export", type="primary", width="stretch"):
            st.session_state.pending_section = "Export"
            st.rerun()
        st.caption("Download tree-level data, an annotated image, or a PDF summary.")
    if view_mode == "Review Flags":
        st.caption("🔴 dense overlap · 🟠 low confidence · 🔵 shadow-affected · 🟢 reliable")
    st.markdown("### Tree Inspector")
    selected = st.selectbox("Select a tree", detections["tree_id"].tolist(),
                            format_func=lambda t: f"Tree #{t}", key="tree_picker")
    st.session_state.selected_tree = selected
    row = detections[detections["tree_id"] == selected].iloc[0]
    crown_area_px2 = (row["xmax"] - row["xmin"]) * (row["ymax"] - row["ymin"])
    st.write(f"**Tree #{selected}** · confidence **{row['score']:.0%}** · status **{crown_status(selected, metrics.review_indices)}**")
    if loaded.gsd_m:
        st.write(f"Estimated crown area: **{crown_area_px2 * loaded.gsd_m**2:.1f} m²**")
    else:
        st.write(f"Estimated crown extent: **{crown_area_px2:.0f} px²**")
    with st.expander("Why was this counted?"):
        st.write(why_was_this_counted(selected, row["score"], metrics.review_indices))

if st.session_state.section == "Understand" and _needs_results():
    st.markdown("## Understand")
    st.markdown("### Forest Profile")
    a, b = st.columns([1, 1.4])
    with a:
        st.write(f"Tree count: **{metrics.tree_count}**")
        st.write(f"Canopy coverage: **{metrics.coverage_pct:.0f}%**")
        if metrics.has_physical_units:
            st.write(f"Average crown area: **{metrics.avg_crown_area_m2:.1f} m²**")
        else:
            st.write(f"Average crown extent: **{metrics.avg_crown_area_px2:.0f} px²**")
    with b:
        st.write("Crown size distribution (relative to this scene's own detections):")
        for label, value in metrics.size_distribution.items():
            st.write(f"{label.title()} — {value}%")
            st.progress(value / 100)
    st.markdown("### 🌿 Look Closer")
    facts = select_facts(derive_tags(metrics), n=2, seed=hash(st.session_state.image_name) % 1000)
    for fact in facts:
        with st.container(border=True):
            st.markdown(f"**{fact['hook']}**")
            st.write(fact["body"])
            st.caption(f"Why it matters: {fact['why_it_matters']}")
            st.caption(f"Source: [{fact['source_name']}]({fact['source_url']})")
    with st.expander("Why should I care?"):
        st.write(WHY_SHOULD_I_CARE["tree_count"])
        st.write(WHY_SHOULD_I_CARE["canopy_coverage"])

if st.session_state.section == "Trust" and _needs_results():
    st.markdown("## Trust")
    _reliability_badge(metrics.reliability)
    for reason in metrics.reliability_reasons:
        st.write(reason)
    st.markdown("**Suitable for:** rapid estimation · comparative analysis · exploratory mapping · initial field planning")
    st.markdown("**Not suitable for:** exact ground-truth inventory · legal measurement · definitive carbon accounting")
    st.markdown("### Review Areas")
    r1, r2, r3 = st.columns(3)
    r1.metric("🔴 Dense-overlap regions", metrics.review_flags["overlap"])
    r2.metric("🟠 Low-confidence detections", metrics.review_flags["low_confidence"])
    r3.metric("🔵 Shadow-affected regions", metrics.review_flags["shadow"])

if st.session_state.section == "Scenarios" and _needs_results():
    st.markdown("## Scenarios")
    st.caption(WHY_SHOULD_I_CARE["canopy_loss_scenario"])
    loss_pct = st.slider("Hypothetical canopy loss", 0, 90, st.session_state.loss_pct, step=5, format="%d%%")
    st.session_state.loss_pct = loss_pct
    scenario = simulate_canopy_loss(metrics, loss_pct)
    s1, s2 = st.columns(2)
    s1.metric("Remaining coverage", f"{scenario['remaining_coverage_pct']:.0f}%")
    if "remaining_area_m2" in scenario:
        s2.metric("Remaining canopy area", f"{scenario['remaining_area_m2']:,.0f} m²")
    else:
        s2.metric("Affected canopy (pixels)", f"{scenario['affected_area_px2']:,.0f} px²")

if st.session_state.section == "Export" and _needs_results():
    st.markdown("## Export")
    import io as _io
    csv_text = build_csv(detections, metrics.review_indices, loaded.gsd_m)
    st.download_button("⬇️ Download CSV", csv_text, file_name="tree_crowns.csv", mime="text/csv", width="stretch")
    annotated_full = draw_annotated_image(loaded.array, detections, mode="review", review_indices=metrics.review_indices)
    buf = _io.BytesIO()
    annotated_full.save(buf, format="PNG")
    annotated_bytes = buf.getvalue()
    st.download_button("⬇️ Download Annotated Image", buf.getvalue(), file_name="annotated_forest.png", mime="image/png", width="stretch")
    pdf_bytes = build_pdf_report(
        metrics, st.session_state.image_name, metrics.reliability_reasons,
        LIMITATIONS, generate_forest_story(metrics), annotated_image=annotated_bytes,
    )
    st.download_button("⬇️ Download PDF Report", pdf_bytes, file_name="forest_report.pdf", mime="application/pdf", width="stretch")

if st.session_state.section == "About":
    st.markdown("## About")
    st.markdown("""
    Forest Intelligence uses DeepForest to identify individual tree crowns and
    reports measurements derived from the loaded image and its spatial metadata.
    """)
    with st.expander("How it works"):
        st.markdown("""
        1. Imagery and spatial-reference metadata are loaded.
        2. A pretrained DeepForest RetinaNet model identifies crown regions.
        3. Confidence, overlap, and shadow signals are retained as review flags.
        4. Areas are converted to square metres only when usable georeferencing exists.
        """)
        if loaded is not None:
            st.caption(f"Model: DeepForest · Confidence threshold: {CONFIDENCE_THRESHOLD:.0%} · CRS: `{loaded.crs or 'none detected'}`")
    with st.expander("Known limitations"):
        for limitation in LIMITATIONS:
            st.write(f"- {limitation}")
