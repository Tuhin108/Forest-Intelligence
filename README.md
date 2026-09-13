---
title: Forest Intelligence
emoji: 🌳
colorFrom: green
colorTo: blue
sdk: streamlit
sdk_version: "1.63.0"
app_file: app.py
pinned: false
---

# 🌳 Forest Intelligence

**See the forest. Trust the count.**

Given high-resolution forest imagery (and optionally a KML boundary),
This tool detects individual tree crowns, estimates canopy area, and — the actual
point of the exercise — is explicit about how reliable each result is and what it
can't tell you.

**Live demo:** [Link](https://forest-intelligence.streamlit.app/)
**2-page explanation:** `docs/explanation.pdf` _(write after the build — see EXECUTION_PLAN.md §21)_

## What it does

1. Detects individual tree crowns in an uploaded (or example) forest image, using
   [DeepForest](https://github.com/weecology/DeepForest) — a pretrained, MIT-licensed,
   RetinaNet-based crown detector (Weinstein et al., *Methods in Ecology and Evolution*, 2020).
2. Estimates canopy area — in physical units (m²) **only** when the source image
   carries real spatial-reference metadata; otherwise it reports pixel-based figures
   and says so explicitly, rather than inventing a scale.
3. Scores an overall **reliability rating** (High/Moderate/Low) from the detections'
   own confidence, overlap, and shadow signals, and flags the specific regions that
   need a human's attention.
4. Presents all of this — plus a tree-by-tree inspector, a contextual "why does this
   matter" facts panel, CSV/PNG/PDF exports, and a "how it works" technical layer —
   in a UI meant for someone who has never seen the tool before.

## What it deliberately does *not* do

It never infers species, tree age, biomass, ecological health, biodiversity, or
carbon stock/sequestration from crown imagery alone — none of those are derivable
from a crown count and canopy area without additional data and a validated
methodology this tool doesn't have. See `src/ui/components.py::LIMITATIONS` for the
full, honest list, which is kept in sync with what the code actually does (not
aspirational copy).

## Quickstart (local)

```bash
git clone <your-repo-url> && cd flora-forest-intelligence
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only, see requirements.txt
pip install -r requirements.txt
streamlit run app.py
```

Click **Try Example Forest** — no imagery of your own required. First run downloads
the ~130 MB pretrained model from Hugging Face Hub and caches it locally.

## Deploying (recommended: Hugging Face Spaces, free CPU-basic tier)

1. Create a new Space, SDK = Streamlit.
2. Push this repo (the `---` frontmatter block at the top of this README configures
   the Space automatically).
3. First load will be slow (model download); subsequent loads are fast, with the
   usual free-tier cold-start (~30–60s) after a period of inactivity.

Streamlit Community Cloud's free tier (~1 GB RAM) is tighter for a PyTorch-based
model than HF Spaces' free CPU tier (2 vCPU / 16 GB RAM) — see `EXECUTION_PLAN.md`
§18 for the reasoning.

## Project structure

```
app.py                      # Streamlit entrypoint — screen flow lives here
src/
  detection/model.py        # DeepForest wrapper (the only place that touches the model)
  geo/raster.py              # image loading + CRS/GSD detection
  geo/kml_utils.py           # lightweight KML parsing + AOI overlap check
  geo/area.py                # canopy area, reliability scoring, review flags — pure functions,
                              # decoupled from the model so they're unit-testable (see tests/)
  facts/facts_bank.json      # curated, sourced facts (no runtime LLM calls)
  facts/selector.py          # deterministic, tag-based contextual fact selection
  reporting/csv_export.py, pdf_report.py
  ui/components.py           # image annotation, template-based narrative text, static copy
tests/test_area_calc.py      # unit tests for the area/reliability math against synthetic data
EXECUTION_PLAN.md            # full planning doc: requirements, dataset/model comparison,
                              # architecture, priorities, schedule, risk register
```

## Testing

```bash
python -m pytest tests/ -v
```

These tests validate the area/coverage/reliability/review-flag math against
hand-built synthetic detections — they don't require the model or any imagery, so
they run offline and fast, and were how this logic was verified in an environment
that couldn't reach the model's download host (see "A note on how this was built" below).

## Known limitations

See the in-app "Known limitations" expander (`src/ui/components.py::LIMITATIONS`),
which is the single source of truth shared by the UI and the PDF export. Headline
items: crown detections are bounding boxes, not segmented crown polygons, so
canopy-area figures are extents, not precise shapes; physical units require a
georeferenced source image; the pretrained model's performance on forest types very
different from its training data hasn't been independently validated here; nothing
here estimates carbon, biomass, or ecological health.

## Attribution

- **DeepForest** — Weinstein, B.G., Marconi, S., Bohlman, S., Zare, A., White, E.
  (2020). *Individual tree-crown detection in RGB imagery using semi-supervised deep
  learning neural networks.* Methods in Ecology and Evolution. MIT License.
  https://github.com/weecology/DeepForest
- **Example imagery** — NEON (National Ecological Observatory Network), Ordway-Swisher
  Biological Station site, distributed with the DeepForest package.

## A note on how this was built

Built solo, with AI coding assistance (Claude), inside a sandboxed dev environment
whose network access does not include Hugging Face Hub — the host DeepForest's
pretrained weights are distributed from. Every piece of this repo that *doesn't*
need the model (geospatial math, KML parsing, reliability scoring, review flagging,
the facts system, CSV/PNG/PDF export, the full Streamlit UI and every interactive
element in it) was built and verified end-to-end against real inputs, including the
real bundled NEON demo image. The one piece that genuinely could not be verified
in that environment — the live neural network forward pass itself — was exercised
with a mocked model output standing in for DeepForest's real return value, so the
full pipeline is proven correct *except* for that one network-gated step, which
will run for real the first time this app starts somewhere with normal internet
access. Flagging this here in the same spirit the brief asks for elsewhere: say
what you verified, and say plainly what you didn't.
