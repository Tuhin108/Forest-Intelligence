# Forest Intelligence — Execution Plan
### Flora Carbon AI hiring hackathon — "Build this weekend. Win a paid tech internship."

---

## 1. Problem Understanding

Strip away the branding and the brief is a three-part technical ask, judged on honesty as much as accuracy:

1. Given high-resolution forest imagery (and optionally KML files), **detect and count individual tree crowns**.
2. **Estimate the canopy area** those crowns cover.
3. **Present the results so a stranger can use them without you in the room.**

The Google Form and LinkedIn post are consistent with each other, so there's no conflict to resolve — just one brief stated twice, once formally and once in a founder's voice. The founder's voice is the more revealing document: *"a rough tool that admits what it can't do is more valuable than a polished one that invents numbers"* and *"in carbon markets, that isn't modesty — it's the job."* That sentence is the actual rubric. This is a company whose product is carbon accounting; a tool that quietly overclaims is worse than useless to them, it's a liability. Every design decision below is filtered through that lens.

## 2. Requirements Extracted From the Two Source Files

**Mandatory (stated explicitly):**
- Input: high-resolution forest imagery, optionally with KML file(s).
- Output: individual tree-crown detection + count, canopy area estimate, results presented usably.
- Solo work only — one confirmed checkbox, one name on it.
- Any tech stack / model / AI coding tool, "vibe coding welcome" — no stack mandate.
- Deliverables: a **live demo URL** (publicly reachable, no login) and a **repository URL**.
- A **maximum 2-page PDF** explaining approach, architecture/workflow, key decisions, what worked, what didn't, known limitations. *"Honesty about limitations is part of the evaluation"* is bolded on the form itself.
- Form questions ("What did you build?", "What doesn't work?", "Did you use AI coding tools?") that you'll answer in 3–5 sentences each — draft these after the build, not before.
- Deadline: **Monday, 14 September 2026, 11:59 PM IST** — checked against today's date (Sat 12 Sept 2026): Sun 13th, Mon 14th, so the form's day-and-date pairing is internally consistent. That gives you roughly two and a half days from now.
- Judging axes, verbatim: *does it run*, *can a stranger use it without you*, *are you honest about limitations*.
- Shortlisted → in-person demo at the Kolkata office, which **is** the interview.

**Optional / not required, but clearly rewarded by the judging axes:**
- Anything that makes a stranger succeed unaided (example mode, clear UI, no setup).
- Anything that makes limitations legible rather than buried in the README.

**Explicitly NOT required:** authentication, multi-user support, a specific model or stack, species/biomass/carbon-credit output, mobile support, a particular cloud provider.

**What I'm adding as differentiators (my proposal, not the brief):** the uncertainty-as-first-class-feature UI, the review/flagging system, the contextual fact layer, the scenario explorer. None of these are asked for. All of them exist to make the *same* required output (count + area + usable presentation) more convincing and more honest. If time runs short, every one of these is cut before the P0 list is touched.

**Needs your judgment, not mine:** whether to use your own drone/satellite imagery (the brief says "source your own imagery") or lean on the bundled example — see §9. Whether you're comfortable using a third-party model's pretrained weights vs. training your own (see §12 — I recommend pretrained, but it's your call to make explicitly in the 2-pager).

## 3. Product Vision

Not "an ML model that draws circles around trees." A tool that lets a non-technical person point a satellite/drone image at it and walk away understanding three things: *what's there, how sure we are, and why it matters* — with a technical layer underneath for anyone who wants to check the work. The tagline that best captures this without overselling: **"See the forest. Trust the count."**

## 4. Personas

- **Primary — the non-technical reviewer or field user.** Cares about forests, has no ML background, wants a number and a map, not a confusion matrix. Success = they understand the result in under 2 minutes with zero help.
- **Secondary — the technical judge.** Wants to see the model choice, the area methodology, the CRS handling, the code. Success = every number in the UI is traceable to a line of code they can find in under a minute.

## 5. UX Principles

1. Imagery is the hero. Metrics support it, never compete with it.
2. No number appears without a way to ask "how sure are you?" next to it.
3. Every ML/geospatial term has a plain-English layer in front of it; the jargon is opt-in, never mandatory.
4. Nothing the model can't actually determine (species, biomass, carbon tonnage, ecological health) is stated as fact, ever, anywhere in the UI, exports, or facts panel.
5. The demo must survive a stranger clicking around with no briefing. If a click can 404 or throw a stack trace, it's a bug, not an edge case.

## 6. User Journey / Screen-by-Screen Spec

**Landing.** One sentence of copy, one primary button ("Try Example Forest"), one secondary path (upload your own image ± KML). No jargon, no login.

**Upload / Example.** File picker for image (GeoTIFF/JPG/PNG); optional KML. Immediate validation with the friendly errors from §17 — never a raw traceback.

**Preview.** Show the loaded image before committing to analysis, plus any detected metadata (resolution, whether it's georeferenced, KML overlap if provided).

**Analyze → Processing.** A real checklist (loading → tiling → detecting → estimating → quality-checking), not a spinner. Each step reflects something the code actually just did.

**Forest Overview (results header).** Tree count, canopy coverage %, canopy area (units depend on whether the image is georeferenced — see §16), analyzed area, a **reliability badge** (High / Moderate / Low), and one sentence of plain-English interpretation generated from the actual numbers, never invented.

**Visual Explorer.** Toggle between Original / Detected Crowns / Review Flags over the same image. This is the single most important widget in the app — it's the thing that makes a skeptical judge believe the count.

**Tree Inspector.** Pick a tree (table + highlight-on-image, since true click-a-pixel-on-an-image interaction is a P2 stretch in Streamlit); see its estimated crown extent, confidence, status, and a one-line "why was this counted" explanation.

**Can I Trust This? panel.** The uncertainty methodology in plain English — see §17.

**Review Areas.** Counts of dense-overlap / low-confidence / shadow-affected detections, each a real number computed from the actual output, not a placeholder.

**Forest Profile.** Count, coverage, average crown extent, a size-distribution split (small/medium/large by tertile of the *actual* detected-crown-area distribution, not fixed arbitrary cutoffs — so the split is meaningful whether the scene has small saplings or huge canopy trees).

**Why Should I Care / Facts.** Short, sourced, occasionally funny cards, contextually selected from a small pre-written bank based on tags the analysis actually produced (see §22–26). No live LLM call in the request path.

**Scenario Explorer.** A slider simulating hypothetical canopy loss, labeled explicitly as geometry, not ecology or carbon.

**Exports.** CSV (tree_id, pixel/geo centroid, crown_area, confidence, status), annotated image PNG, 1-page PDF summary.

**How It Works / Limitations.** Plain-English 8-step pipeline description up top, technical detail (model name, thresholds, CRS handling, tiling config) behind an expander, and a limitations list that says only things the implementation can actually back up.

## 7. Feature List & Priority

**P0 — must exist for this to be a valid submission at all:**
Image upload + bundled example; tree-crown detection; count; canopy-area estimate with honest units; before/after visual; reliability badge with plain-English rationale; limitations section; friendly failure handling; public demo URL with zero setup; public repo; 2-page PDF.

**P1 — the differentiators, cut in this order if time runs out:**
Individual tree inspector → Review/flagged-regions → "Can I trust this?" deep-dive → CSV/PDF export → contextual facts panel → forest-profile size distribution.

**P2 — nice to have, only after every P1 item works end-to-end:**
KML-based AOI clipping and map view; scenario explorer; lightweight accept/reject review-mode UI.

**P3 — first thing cut, don't start these until P0+P1 are demo-solid:**
Crown polygon refinement via SAM, multi-scene gallery beyond the one hero example, mobile polish.

## 8. Dataset Strategy

The brief says "source your own imagery," which puts the decision on you, but the demo still needs a **reliable hero scene that works with zero setup and zero network dependency on demo day** — a judge's laptop or wifi hiccup shouldn't be able to break the interview.

## 9. Dataset Candidates & Comparison

| Candidate | Resolution | Crown separability | License / access | Verdict |
|---|---|---|---|---|
| **DeepForest's bundled NEON demo scene** (`OSBS_029.tif`, Ordway-Swisher Biological Station) | 0.1 m RGB airborne | Individual crowns clearly visible | MIT, ships inside the `deepforest` pip package — no download needed at all | **Hero scene.** Zero network dependency, published provenance (Weinstein et al. 2019/2020), exactly the imagery the pretrained model was trained on, so results are defensible rather than out-of-domain. |
| NEON Airborne Observation Platform archive (data.neonscience.org) | 0.1–0.25 m RGB, dozens of US sites | Good, varies by canopy type | Public, NSF-funded network; confirm current redistribution terms before bundling extra scenes in the repo — safer to *link* to the source than to re-host | **Secondary scenes** for a robustness demo (denser vs. sparser canopy), fetched live rather than committed to the repo. |
| Your own drone/phone aerial photo of a real forest | Depends on capture | Depends on altitude/angle | Yours outright | **Do this if you have access to a drone or a rooftop/hill vantage this weekend** — nothing beats "and here's a photo I took myself" in an interview. Falls back gracefully to the NEON scene if it doesn't pan out. |
| NAIP (US, ~0.6–1 m) | Borderline for crown separation | Weak on small/close crowns | Public domain | Not recommended as hero imagery — resolution is at the edge of what individual-crown detection needs. |
| Sentinel-2 / most public satellite | 10 m | None — a whole grove is one pixel | Public | Explicitly **not suitable** for individual-crown work; worth one sentence in the limitations section explaining *why* satellite ≠ this use case, since "satellite imagery" is literally the word used in the brief and a judge may ask about it. |

**Recommendation:** ship the bundled NEON scene as the guaranteed-to-work example, add your own captured image as a second scene if you can get one this weekend, and treat live-fetched NEON scenes as an optional P2 "robustness" addition — not a P0 dependency.

## 10. Model Candidates & Comparison

| Candidate | Output type | Setup cost | Maturity | License |
|---|---|---|---|---|
| **DeepForest** (Weinstein et al., U. Florida/Weecology) | Bounding boxes + confidence, RetinaNet backbone (PyTorch) | `pip install deepforest`, weights auto-download from Hugging Face Hub on first run | Actively maintained (v2.1 as of this writing), pretrained on 30M+ semi-supervised + 10k hand-labeled crowns across 22+6 forests, ships a bundled demo raster | MIT |
| Detectree2 (Ball et al. 2023, U. Cambridge) | Instance-segmentation polygons, Mask R-CNN via Detectron2 | Detectron2 is a heavier, fussier install (not pure pip, CUDA-sensitive), tuned for tropical forest structure | Solid research pedigree, smaller/slower-moving community | MIT |
| Train a custom model from scratch | Whatever you design | High — needs labeled data you don't have this weekend | N/A | N/A |
| Foundation-model-assisted (SAM prompted by boxes) | Refines boxes into polygons | Adds a second heavy dependency and inference pass | Promising, not necessary for a v1 | Varies |

**Recommendation: DeepForest.** It installs cleanly, has an actual research paper and citation behind the pretrained weights (not a black box), ships a demo image so the "try example" path has zero external dependency, and its RetinaNet output (boxes + confidence) is honestly simpler to reason about and explain to a non-technical judge than a segmentation mask would be — which matters when the rubric explicitly rewards not overclaiming precision you don't have.

**Important honesty point to carry into the UI and the 2-pager:** DeepForest predicts **bounding boxes**, not crown-shaped polygons. "Canopy area" computed from a box is the *extent* of the crown, not its true segmented shape — a box around an irregular crown always slightly overstates area. Say this explicitly in the limitations section rather than letting "canopy area: 18,420 m²" imply pixel-perfect segmentation. Training from scratch, or layering SAM on top of the boxes for true polygons, are both legitimate v2 ideas — name them as future work rather than attempting them under deadline pressure.

## 11. Canopy Area Methodology

- If the raster carries geospatial reference info (a GeoTIFF with CRS/transform, verified via `rasterio`), convert each bounding box's pixel area to physical units using the ground sample distance (GSD) derived from the affine transform. Report **crown extent in m²**, sum for total canopy area, divide by analyzed-area to get coverage %.
- If the raster has **no** CRS (a plain JPG/PNG, e.g. a phone photo), do **not** report square meters — there is no ground-truth scale to convert pixels to. Report pixel-based figures (crown extent in px², % of analyzed image covered) and say exactly why physical units aren't available. This is the single most important "don't invent numbers" rule in the whole app, so it's implemented as a hard branch in the code, not a UI afterthought.
- Round to a precision the methodology can actually defend — whole m² or one decimal, never 6 significant figures.
- Never derive carbon tonnage, biomass, species, or ecological health from crown count/area alone. If the topic comes up (facts panel, "why should I care," export), the copy explicitly states that these require independent methodology and data this tool doesn't have.

## 12. Uncertainty & Reliability Methodology

Reliability is computed from things actually observable in the output, not asserted:
- Detection confidence distribution (fraction of detections above/below the model's confidence threshold).
- Overlap rate (fraction of boxes with IoU above a threshold against a neighbor — a proxy for dense/ambiguous canopy).
- A brightness-based shadow heuristic (mean pixel brightness inside a crown crop below a threshold flags "shadow-affected") — cheap, explainable, and honestly labeled as a heuristic rather than true shadow detection.

These three signals combine into HIGH / MODERATE / LOW with the specific reasons shown (✓/⚠ list), plus an explicit "suitable for / not suitable for" block, matching the brief's demand for legible limitations.

## 13. Review / Flagging Methodology

Three flag categories, each backed by a real computed condition: dense-overlap regions (high mutual IoU), low-confidence detections (below threshold), shadow-affected regions (brightness heuristic). Counts shown are always the actual counts from the current image, never placeholders.

## 14. Fact System Architecture

```
Curated fact bank (facts_bank.json, hand-written & source-linked)
        ↓
Deterministic tag-based selector (reads analysis output: overlap_high?
shadow_high? coverage_high? uncertainty_high? → picks matching facts)
        ↓
Streamlit UI card ("Look Closer")
```

No LLM call happens in the request path — the fact bank is static JSON committed to the repo. This is a deliberate simplification from the original "LLM-curated batch pipeline" concept in the brief document you gave me: for a weekend build, hand-writing ~12 well-sourced, honestly-scoped facts is more reliable and more auditable than standing up an LLM curation/validation pipeline that could itself invent a number under time pressure. If you want the fuller batch-generation architecture (LLM writes → validation layer → dated JSON → app reads cache) as a v2 improvement, it's a clean drop-in replacement for `facts_bank.json` — same consumer-side interface, so nothing else in the app needs to change.

## 15. Full Technical Architecture

```
Image / KML in
   → geo.raster: load + detect CRS/GSD, or flag "no georeference"
   → geo.kml_utils: parse KML, clip AOI if provided
   → detection.model: DeepForest, tiled inference, confidence threshold
   → geo.area: pixel→physical area conversion (branch on CRS presence),
               reliability scoring, review-flag computation
   → facts.selector: tag-based lookup against static bank
   → ui: Streamlit renders dashboard, visual explorer, inspector, exports
```

Deliberately excluded: databases, auth, microservices, real-time LLM calls in the request path, GPU requirement (CPU inference is fine at this image scale and this is what makes free-tier hosting reliable).

## 16. Repository Structure

```
flora-forest-intelligence/
├── app.py                    # Streamlit entrypoint
├── requirements.txt
├── README.md                 # incl. HF Spaces deploy metadata
├── src/
│   ├── detection/model.py    # DeepForest wrapper, tiling, thresholds
│   ├── geo/raster.py         # CRS/GSD detection, image loading
│   ├── geo/kml_utils.py      # KML parsing, AOI clipping
│   ├── geo/area.py           # area calc, reliability, review flags
│   ├── facts/facts_bank.json + selector.py
│   ├── reporting/csv_export.py, pdf_report.py
│   └── ui/components.py
├── tests/test_area_calc.py   # unit tests against synthetic detections
└── docs/                     # 2-page explanation source
```

## 17. Failure Handling (verbatim copy used in the app)

No image → *"Please upload a forest image."* Unsupported format → *"This image format isn't supported."* No georeference → *"We can detect crowns, but physical area estimates aren't available without spatial reference information — here are the pixel-based numbers instead."* Too coarse → *"This image looks too low-resolution for reliable individual crown detection."* Zero detections → *"No reliable crowns were detected. Try a clearer or higher-resolution image."* KML doesn't overlap → *"The boundary you uploaded doesn't overlap the image."* Model error → *"Analysis couldn't be completed. Your original image hasn't been modified."* Never a raw stack trace.

## 18. Deployment Strategy

**Recommended: Hugging Face Spaces, Streamlit SDK, free CPU-basic tier (2 vCPU / 16 GB RAM).** Verified this weekend: Streamlit Community Cloud's free tier is ~1 GB RAM, which is tight once PyTorch + a RetinaNet model are loaded; HF Spaces' free CPU tier gives far more headroom for the same $0, deploys straight from a git push, and needs no login for a judge to open the URL. Cold start after inactivity (~30–60s) is the only real trade-off — acceptable for a weekend project, and mentionable as a known limitation rather than a surprise.

## 19. Testing Strategy (minimum viable)

Example scene end-to-end; a scene with dense/overlapping crowns; a low-resolution image (confirm the "too coarse" message, not a crash); an image with no georeference (confirm pixel-mode branch); a non-forest image (confirm the zero-detections message); KML that doesn't overlap; a fresh machine with no dev tools (the actual "stranger" test the brief asks for).

## 20. Demo Strategy

Open URL → Try Example Forest → Analyze → watch the real processing checklist → read the Forest Overview and reliability badge → flip through Original/Detected/Review views → click into one tree → open "Can I trust this?" → glance at a fact card → download the CSV. Target 2–3 minutes, no part of it requiring you to explain what a bounding box is.

## 21. 2-Page Explanation Outline (draft after building, not before)

Page 1: what it does (3–4 sentences), architecture diagram/description, key decisions (why DeepForest, why bounding-box area instead of segmentation, why no live LLM calls, why HF Spaces). Page 2: what doesn't work / known limitations (write this section first, honestly, before you write the parts that make you look good), technologies used, one sentence on what you'd do with another week.

## 22. Submission Checklist

- [ ] Live demo URL loads with zero setup and no login
- [ ] "Try Example Forest" works from a cold cache
- [ ] Every number in the UI traces to a real calculation (no placeholders left in)
- [ ] Limitations section matches what the code actually does
- [ ] Repo is public, README explains how to run it locally
- [ ] 2-page PDF is ≤ 2 pages and answers what-doesn't-work honestly
- [ ] Form's short-answer questions answered (what you built / what doesn't work / tech used / AI tools used)
- [ ] Solo-submission confirmation checkbox ticked truthfully

## 23. Weekend Schedule (deadline: Mon 14 Sept, 11:59 PM IST)

**Sat (today):** repo scaffold, DeepForest wired to the bundled example end-to-end, area math + reliability scoring, basic Streamlit dashboard. Goal by end of day: a boring but true P0 demo running locally.

**Sun:** visual explorer (original/detected/review toggle), tree inspector, "Can I trust this?" panel, review-flag counts, CSV/PDF export, facts panel. Deploy to HF Spaces early in the day, not at midnight — you want hours of buffer to fix a deploy-only bug.

**Mon (before the deadline):** your own imagery if you got one, KML support if time allows, polish pass on copy and empty/error states, write the 2-pager (limitations section first), fill out the form, submit with hours to spare rather than minutes.

## 24. Risk Register

| Risk | Mitigation |
|---|---|
| Free-tier host sleeps/cold-starts right as a judge opens it | Mention the ~30–60s wake-up in the UI's own loading state so it reads as expected, not broken |
| DeepForest under- or over-counts on an unfamiliar scene | Lean on the bundled NEON scene (in-domain for the pretrained weights) as the primary demo; be upfront in the limitations section that out-of-domain forests will perform differently |
| Bounding-box area overstates true crown shape | Say so explicitly in the UI copy and the 2-pager, don't just bury it in the README |
| Running out of weekend before P1 features land | The priority list in §7 is ordered exactly so you always have a demoable P0 state to fall back to |
| KML edge cases (non-overlapping, malformed) | Handled by the friendly-failure copy in §17, tested explicitly in §19 |

## 25. Likely Reviewer Objections & Ready Answers

*"Is this just a wrapper around someone else's model?"* — Yes, and that's the right call: DeepForest is a peer-reviewed, purpose-built tree-crown detector; reinventing it in a weekend would produce a worse model and eat all the time that instead went into honesty, UX, and the parts that are actually yours. *"Why bounding boxes and not real crown polygons?"* — Named explicitly in §10/§21 as a deliberate simplicity-over-false-precision choice, with SAM-based refinement as a scoped v2. *"Why no carbon numbers — isn't that the point in carbon markets?"* — Because crown count/area alone can't support that claim without a separate validated methodology, and the brief itself says inventing that number is worse than not having it.

## 26. What Makes This Memorable

Not the model — every entrant will point at a pretrained detector. What a judge will remember is the moment the "Can I trust this?" panel gives a *specific, correct* answer about *this* image, and the moment a flagged review region turns out to actually be the dense/shadowed patch it claims to be. Honesty that's checkable, not just claimed, is the differentiator this brief is explicitly designed to reward.
