# IGNITE Interactive Portal

IGNITE (Immune Genomics and fuNctional Integration for Target Enrichment) is a static
web portal for browsing machine-learned drug-target candidates for immune disease. It
ranks 19,502 genes by a PU-learning model score and provides a per-gene detail page for
each: regulator-burden signal, functional-genomics similarity to approved targets,
polarization score, and external validation links.

Dark, monospace-data interface. No build step, no dependencies, no framework
install — plain files served over HTTP.

**Live site:** https://alhanster.github.io/IGNITE-Interactive-Portal/

## Run locally

The page loads its data from JavaScript files, so it must be served over HTTP —
opening `index.html` directly with `file://` will not work. From this folder:

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

## Deploy

The site is hosted on GitHub Pages from the `main` branch (root folder). To publish
changes, just commit and push:

```bash
git add .
git commit -m "Update atlas"
git push
```

Pages rebuilds automatically and the live site updates within a minute. The included
`.nojekyll` file tells Pages to serve every file as-is. Every asset reference is
relative, so the site works unchanged from the `/IGNITE-Interactive-Portal/` project
subpath — no base tag or config needed.

## Updating the data

Data lives in `data/` as CSVs. Replace a CSV there and commit — the **Build site
data** GitHub Action regenerates the JavaScript the site loads and commits it back,
and Pages redeploys. You can do this entirely from the GitHub web UI; no local
tooling needed. Each dataset is independent, so you can refresh one and leave the
others alone.

See [`data/README.md`](data/README.md) for the expected columns. To run the build
yourself instead:

```bash
python3 tools/build_data.py
```

The generated files are committed artifacts — edit the CSVs, not these:

| Generated file | Global | Built from |
| --- | --- | --- |
| `target-data.js` | `__TARGETS__`, `__TARGET_TOTAL__` | `data/ranked_atlas.csv` + `data/ensembl.csv` |
| `cfg-data.js` | `__CFG__` | `data/knn_*.csv` (one per activation state) |
| `polarization-data.js` | `__POL__` | `data/polarization.csv` |

Model rank, the quartile highlight cutoffs (LOEUF <P25, Mis. Z >P75, GWAS >P75) and the
kNN percentiles are all derived from whatever you upload, so they re-scale to the new data
automatically.

## Files

| File | Purpose |
| --- | --- |
| `index.html` | Entry page. |
| `Portal.dc.html` | The app — table, search, and gene detail pages. |
| `support.js` | Runtime. |
| `target-data.js`, `cfg-data.js`, `polarization-data.js` | Generated datasets — built from `data/`. |
| `data/` | Source CSVs. Edit these to update the site. |
| `tools/build_data.py` | Turns the CSVs into the dataset files. |
| `assets/logo.png` | Logo / favicon. |
| `.nojekyll` | Required for GitHub Pages. |
