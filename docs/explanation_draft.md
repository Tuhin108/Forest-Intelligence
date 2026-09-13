# 2-Page Explanation — Draft

*Fill in the bracketed parts after you've actually deployed and clicked through it
yourself — anything you haven't personally verified shouldn't go in here. This draft
covers the parts that are true by construction (architecture, decisions); the
what-worked/what-didn't section is yours to write honestly, first.*

---

## What I built

Forest Intelligence: given a forest image (with an optional KML boundary), it
detects individual tree crowns, estimates the canopy area they cover, and presents
both the result and its own uncertainty in a way meant for someone who has never
used it before. I prioritized [P0 coverage: detection + count + area + honest
reliability + a zero-setup example path] over [the specific P1/P2 items you got to
— fill in which ones actually shipped: tree inspector? review flags? facts panel?
KML support? scenario explorer?].

## Architecture / workflow

Image → CRS/GSD detection (rasterio) → DeepForest (pretrained RetinaNet,
tiled inference) → pixel→physical area conversion (only when georeferenced) →
reliability scoring from confidence/overlap/shadow signals → Streamlit UI.
No database, no auth, no real-time LLM calls in the request path — the facts panel
reads a small static, source-linked JSON file. Full detail in `EXECUTION_PLAN.md`.

## Key technical decisions

- **DeepForest over training from scratch or Detectree2**: peer-reviewed, MIT-licensed,
  pip-installable, ships a real demo image with clean provenance — reinventing crown
  detection in a weekend would produce a worse model and cost the time that instead
  went into the honesty/UX layer, which is what's actually being judged.
- **Bounding-box area, not segmented-polygon area**: DeepForest predicts boxes, not
  crown shapes. Reporting box area as "canopy area" and saying so explicitly was a
  deliberate choice over implying false segmentation precision.
- **No physical units without a real CRS**: a plain photo has no ground scale to
  convert pixels to meters — the tool says so instead of guessing.
- **No carbon/biomass/species claims, ever**: crown count and canopy area alone
  don't support those claims without additional data and methodology.
- **[Your deployment choice — HF Spaces or elsewhere]**: [why].

## What worked

[Fill in after you've clicked through your own deployed demo: e.g., "the example
forest path works end to end with zero setup," "the reliability badge correctly
downgrades on a scene I deliberately picked with heavy overlap," etc. Be specific —
generic confidence reads as unverified.]

## What doesn't work / known limitations

[Write this section first, before the parts that make you look good — the form
itself says honesty about limitations is part of the evaluation. Pull from
`src/ui/components.py::LIMITATIONS` for the ones that are true by construction
(bounding-box area, no georeference → no physical units, no species/carbon/health
claims), and add anything you personally observed that isn't already listed —
e.g. specific forest types or lighting conditions where detection looked weak,
anything you didn't get to (KML support? review-accept/reject mode?), anything
you cut for time.]

## Technologies used

Python, Streamlit, DeepForest (PyTorch/RetinaNet), rasterio, shapely, pyproj,
fpdf2, [Claude / your AI coding tool] for development assistance. Full list in
`requirements.txt`.
