# Data folder

Drop CSVs here and commit. The **Build site data** GitHub Action regenerates the
`*-data.js` files at the repo root and commits them, and the live site updates.

Each dataset is independent: upload only the file you want to refresh, and the
other two are left untouched.

To do it by hand instead:

```bash
python3 tools/build_data.py
```

Blank cells (and `NA`/`NaN`) become `null`. Column names must match exactly.

## `ranked_atlas.csv` → `target-data.js`

The main scored gene table. One row per gene; the gene column must be unique.

**Required — shown in the table and the "Model evidence" card**

| Column | Notes |
| --- | --- |
| `gene` | Gene symbol. |
| `pu_score` | PU-learning model score. The table is ranked by this. |
| `lof.oe_ci.upper` | LOEUF. Emitted as `lof_oe_ci_upper`. |
| `mis.z_score` | Missense Z. Emitted as `mis_z_score`. |
| `IEI` | 0 or 1. Drives the IEI badge. |
| `gwas_score` | |
| `drug_status` | `approved`, `in trial`, or `non-target`. Drives the Status column and badge. `in-trial` is accepted and normalized to `in trial`; any other value fails the build. |
| `furthest_stage` | Carried through to "All feature values"; no label uses it. |

**Required — the three analysis blocks.** Each block is all-or-nothing per gene: a gene
either has the whole block or shows a "no data" note for that card.

| Block | Columns |
| --- | --- |
| Regulator burden | `reg_burden_sig_Rest`, `reg_burden_sig_Stim8hr`, `reg_burden_sig_Stim48hr` (0/1), `expected_n_regulators_residuals` |
| Subset polarization | `zscore_Th1`, `zscore_Th2`, `zscore_Th17`, `zscore_Treg` |
| Cytokine regulation | `n_sig_regulated_cytokines_{Rest,Stim8hr,Stim48hr}`, `n_sig_regulated_cytokine_receptors_{Rest,Stim8hr,Stim48hr}` |

Also required, carried through to "All feature values" without a dedicated card:
`crossdonor_confidence`, `crossdonor_correlation_mean`, `gene_burden_score`,
`polar_coef_rank_{Rest,Stim8hr,Stim48hr}`, `polar_rank_range`.

**Ignored if present.** These are redundant with what the page already derives, so the
build drops them rather than letting a stale copy ship:

- `rank`, `rank_pctile` — the page computes model rank itself from `pu_score` at load.
- `pu_role` — 1:1 with `drug_status`.
- `has_cytokine` — identical to "the cytokine columns are filled in", which already gates that card.

The gene count in the header is the row count. Model rank and the quartile highlight
cutoffs (LOEUF <P25, Mis. Z >P75, GWAS >P75) are computed in the browser at load, so they
re-derive themselves from whatever you upload.

## `ensembl.csv` → gnomAD deep links

Two columns, `gene,ensembl`. Optional. The gene detail page links to gnomAD by Ensembl ID
when it has one and falls back to a symbol search when it does not, so a gene missing here
still works — it just gets a less precise link. Keep it in step with `ranked_atlas.csv` when
you add genes.

## `knn_*.csv` → `cfg-data.js`

Functional-genomics similarity, **one file per activation state** (any filename
starting with `knn_`). The condition is read from the `culture_condition` column,
which must be `Rest`, `Stim8hr`, or `Stim48hr` — each becomes one panel on the gene
detail page. A gene missing from a file simply shows "no hit" for that condition.

| Column | Notes |
| --- | --- |
| `gene` | Unique within a file. |
| `kNN_max_score` | Cosine similarity, −1 to 1. |
| `nearest_immune_target` | |
| `nearest_target_approved_drug` | Not used by the site. |
| `drug_name` | Semicolon-separated; rendered as chips. |
| `immune_indications` | Not used by the site. |
| `is_approved_target` | `True`/`False`. |
| `n_downstream_z3` | Integer. |
| `culture_condition` | `Rest`, `Stim8hr`, or `Stim48hr`. |

The kNN **percentile** is not a column — it is recomputed on every build as the
percentile rank of `kNN_max_score` within its condition, so it always describes the
data you actually uploaded.

## `polarization.csv` → `polarization-data.js`

| Column | Notes |
| --- | --- |
| `gene` | Must be unique. |
| `pol` | Polarization score. |
| `dir` | `toward_signature_pos` or `toward_signature_neg`. |
| `signs` | `True`/`False` — signs agree. |
| `z8`, `z48`, `zRest` | |
| `coef8`, `coef48` | |
| `knownReg` | `True`/`False`. |
| `regType` | Label shown when `knownReg` is true. |

The absolute polarization value is derived from `pol`, so there is no column for it.

## If a build fails

The Action fails loudly and writes nothing for the offending dataset — the site keeps
serving the previous data. Check the Actions log; the error names the file, the line,
and the column.
