#!/usr/bin/env python3
"""Build the site's *-data.js files from the CSVs in data/.

Each dataset is optional: if its CSV is missing, the corresponding .js file is
left exactly as it is. That way you can refresh one dataset without having to
re-upload the others.

Run from anywhere:  python3 tools/build_data.py
"""

import csv
import glob
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

# CSV culture_condition -> key used in __CFG__ and in the target-data column names.
CONDITIONS = {'Rest': 'rest', 'Stim8hr': 'stim8hr', 'Stim48hr': 'stim48hr'}

# Main gene table. Keys are emitted under their CSV names so that the detail
# page's "All feature values" list stays self-documenting; the two dotted names
# are the only ones renamed, because a dot is awkward as a JS property.
TARGET_RENAME = {'lof.oe_ci.upper': 'lof_oe_ci_upper', 'mis.z_score': 'mis_z_score'}

TARGET_TEXT = ['drug_status', 'furthest_stage']

# Exports have shipped both spellings of the trial label; the site keys off
# 'in trial', so fold the hyphenated form into it and reject anything else
# rather than letting an unknown value silently read as non-target.
DRUG_STATUS = {'approved': 'approved', 'in trial': 'in trial',
               'in-trial': 'in trial', 'non-target': 'non-target'}

TARGET_NUMERIC = [
    'pu_score', 'lof.oe_ci.upper', 'mis.z_score', 'IEI', 'gwas_score',
    'gene_burden_score',
    'crossdonor_confidence', 'crossdonor_correlation_mean',
    'expected_n_regulators_residuals',
    'zscore_Th1', 'zscore_Th2', 'zscore_Th17', 'zscore_Treg',
    'polar_coef_rank_Rest', 'polar_coef_rank_Stim8hr', 'polar_coef_rank_Stim48hr',
    'polar_rank_range',
    'reg_burden_sig_Rest', 'reg_burden_sig_Stim8hr', 'reg_burden_sig_Stim48hr',
] + ['n_sig_regulated_%s_%s' % (w, s)
     for w in ('cytokines', 'cytokine_receptors')
     for s in ('Rest', 'Stim8hr', 'Stim48hr')]

# Integral features - kept as ints so the table's filters and pips stay exact.
TARGET_INTEGRAL = {'IEI', 'reg_burden_sig_Rest', 'reg_burden_sig_Stim8hr',
                   'reg_burden_sig_Stim48hr'} | {
    'n_sig_regulated_%s_%s' % (w, s)
    for w in ('cytokines', 'cytokine_receptors')
    for s in ('Rest', 'Stim8hr', 'Stim48hr')}

TARGET_COLUMNS = ['gene'] + TARGET_TEXT + TARGET_NUMERIC

# Dropped on purpose, all verified redundant against what is kept:
#   rank, rank_pctile - rank is exactly pu_score descending and rank_pctile is
#     1-(rank-1)/n; the page computes modelRank itself at load.
#   pu_role           - 1:1 with drug_status.
#   has_cytokine      - identical, gene for gene, to "cytokine counts present",
#                       so it gates the card rather than being a feature.
TARGET_DROP = ['rank', 'rank_pctile', 'pu_role', 'has_cytokine']

CFG_COLUMNS = ['gene', 'kNN_max_score', 'nearest_immune_target', 'drug_name',
               'is_approved_target', 'n_downstream_z3', 'culture_condition']

POL_COLUMNS = ['gene', 'pol', 'dir', 'signs', 'z8', 'z48', 'zRest',
               'coef8', 'coef48', 'knownReg', 'regType']


class BuildError(Exception):
    pass


# ---------------------------------------------------------------- value coercion

def num(row, col, where):
    """CSV cell -> float, or None for blank/NA/NaN."""
    v = (row.get(col) or '').strip()
    if v == '' or v.upper() in ('NA', 'N/A', 'NAN', 'NULL', 'NONE'):
        return None
    try:
        f = float(v)
    except ValueError:
        raise BuildError('%s: %r is not a number in column %r' % (where, v, col))
    return None if math.isnan(f) or math.isinf(f) else f


def integer(row, col, where):
    f = num(row, col, where)
    return None if f is None else int(f)


def boolean(row, col, where):
    v = (row.get(col) or '').strip().lower()
    if v in ('true', '1', 'yes', 'y', 't'):
        return True
    if v in ('false', '0', 'no', 'n', 'f', ''):
        return False
    raise BuildError('%s: %r is not a boolean in column %r' % (where, v, col))


def text(row, col):
    return (row.get(col) or '').strip()


def read_csv(path, required):
    with open(path, newline='', encoding='utf-8-sig') as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise BuildError('%s: file has no data rows' % os.path.basename(path))
    missing = [c for c in required if c not in rows[0]]
    if missing:
        raise BuildError('%s: missing column(s): %s'
                         % (os.path.basename(path), ', '.join(missing)))
    return rows


def find(*patterns):
    hits = []
    for p in patterns:
        hits += sorted(glob.glob(os.path.join(DATA, p)))
    seen, out = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def write_js(filename, body):
    path = os.path.join(ROOT, filename)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(body)
    os.replace(tmp, path)


def dump(obj):
    return json.dumps(obj, separators=(',', ':'), allow_nan=False,
                      ensure_ascii=False)


def percentiles(values):
    """Percentile rank 0-100 for each value, ties averaged, rounded to 0.1.

    Min maps to 0 and max to 100, matching the "kNN percentile (within
    condition)" figure the detail page shows.
    """
    n = len(values)
    if n == 1:
        return [100.0]
    order = sorted(range(n), key=lambda i: values[i])
    out = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        rank = (i + j) / 2.0
        for k in range(i, j + 1):
            out[order[k]] = round(100.0 * rank / (n - 1), 1)
        i = j + 1
    return out


# ---------------------------------------------------------------------- builders

def read_ensembl():
    """gene -> ENSG id, from data/ensembl.csv. Optional; absent is not an error.

    The main table CSV carries no Ensembl id, but the gene detail page uses one
    for its gnomAD deep link (it falls back to a symbol search without one).
    """
    paths = find('ensembl.csv')
    if not paths:
        return {}, 'no ensembl.csv'
    rows = read_csv(paths[0], ['gene', 'ensembl'])
    m = {}
    for row in rows:
        gene, ensg = text(row, 'gene'), text(row, 'ensembl')
        if gene and ensg:
            m[gene] = ensg
    return m, '%d ids from %s' % (len(m), os.path.basename(paths[0]))


def build_targets():
    paths = find('ranked_atlas.csv', 'targets.csv', 'target*.csv')
    if not paths:
        return 'target-data.js: no ranked_atlas.csv in data/ - left unchanged'
    path = paths[0]
    rows = read_csv(path, TARGET_COLUMNS)
    ensembl, ens_note = read_ensembl()

    out, seen, matched = [], set(), 0
    for n_, row in enumerate(rows, 2):
        where = '%s line %d' % (os.path.basename(path), n_)
        gene = text(row, 'gene')
        if not gene:
            raise BuildError('%s: blank gene' % where)
        if gene in seen:
            raise BuildError('%s: duplicate gene %r' % (where, gene))
        seen.add(gene)

        rec = {'gene': gene, 'ensembl': ensembl.get(gene, '')}
        if rec['ensembl']:
            matched += 1
        for col in TARGET_TEXT:
            rec[col] = text(row, col)
        if rec['drug_status'] not in DRUG_STATUS:
            raise BuildError('%s: %r is not a known drug_status (expected %s)'
                             % (where, rec['drug_status'],
                                ', '.join(sorted(DRUG_STATUS))))
        rec['drug_status'] = DRUG_STATUS[rec['drug_status']]
        for col in TARGET_NUMERIC:
            v = num(row, col, where)
            if v is not None and col in TARGET_INTEGRAL:
                v = int(v)
            rec[TARGET_RENAME.get(col, col)] = v
        out.append(rec)

    write_js('target-data.js',
             'window.__TARGETS__ = %s;\nwindow.__TARGET_TOTAL__ = %d;\n'
             % (dump(out), len(out)))
    return ('target-data.js: %d genes from %s, %d with an ensembl id (%s)'
            % (len(out), os.path.basename(path), matched, ens_note))


def build_cfg():
    paths = find('knn_*.csv')
    if not paths:
        return 'cfg-data.js: no knn_*.csv in data/ - left unchanged'

    # Group rows by condition first: pctl is a rank within a condition, so every
    # file for that condition has to be in hand before any of it can be computed.
    by_cond = {}
    for path in paths:
        rows = read_csv(path, CFG_COLUMNS)
        for n_, row in enumerate(rows, 2):
            where = '%s line %d' % (os.path.basename(path), n_)
            raw = text(row, 'culture_condition')
            if raw not in CONDITIONS:
                raise BuildError('%s: unknown culture_condition %r (expected %s)'
                                 % (where, raw, ', '.join(CONDITIONS)))
            gene = text(row, 'gene')
            if not gene:
                raise BuildError('%s: blank gene' % where)
            score = num(row, 'kNN_max_score', where)
            if score is None:
                raise BuildError('%s: blank kNN_max_score for %s' % (where, gene))
            bucket = by_cond.setdefault(CONDITIONS[raw], {})
            if gene in bucket:
                raise BuildError('%s: duplicate gene %r for condition %s'
                                 % (where, gene, raw))
            bucket[gene] = {
                'knn': score,
                'nearest': text(row, 'nearest_immune_target'),
                'drugs': text(row, 'drug_name'),
                'isfda': boolean(row, 'is_approved_target', where),
                'ndown': integer(row, 'n_downstream_z3', where),
            }

    cfg, notes = {}, []
    for cond in ('rest', 'stim8hr', 'stim48hr'):
        bucket = by_cond.get(cond)
        if not bucket:
            continue
        genes = list(bucket)
        pcts = percentiles([bucket[g]['knn'] for g in genes])
        for gene, pctl in zip(genes, pcts):
            rec = bucket[gene]
            rec['pctl'] = pctl
            cfg.setdefault(gene, {})[cond] = rec
        notes.append('%s %d' % (cond, len(genes)))

    write_js('cfg-data.js', 'window.__CFG__ = %s;\n' % dump(cfg))
    return 'cfg-data.js: %d genes (%s) from %d file(s)' % (
        len(cfg), ', '.join(notes), len(paths))


def build_pol():
    paths = find('polarization.csv', 'polarization*.csv', 'pol*.csv')
    if not paths:
        return 'polarization-data.js: no polarization.csv in data/ - left unchanged'
    path = paths[0]
    rows = read_csv(path, POL_COLUMNS)

    pol = {}
    for n_, row in enumerate(rows, 2):
        where = '%s line %d' % (os.path.basename(path), n_)
        gene = text(row, 'gene')
        if not gene:
            raise BuildError('%s: blank gene' % where)
        if gene in pol:
            raise BuildError('%s: duplicate gene %r' % (where, gene))
        score = num(row, 'pol', where)
        if score is None:
            raise BuildError('%s: blank pol for %s' % (where, gene))
        pol[gene] = {
            'pol': score,
            'abs': abs(score),
            'dir': text(row, 'dir'),
            'signs': boolean(row, 'signs', where),
            'z8': num(row, 'z8', where),
            'z48': num(row, 'z48', where),
            'zRest': num(row, 'zRest', where),
            'coef8': num(row, 'coef8', where),
            'coef48': num(row, 'coef48', where),
            'knownReg': boolean(row, 'knownReg', where),
            'regType': text(row, 'regType'),
        }

    write_js('polarization-data.js', 'window.__POL__ = %s;\n' % dump(pol))
    return 'polarization-data.js: %d genes from %s' % (len(pol), os.path.basename(path))


def main():
    if not os.path.isdir(DATA):
        print('error: no data/ directory at %s' % DATA, file=sys.stderr)
        return 1
    try:
        notes = [build_targets(), build_cfg(), build_pol()]
    except BuildError as e:
        print('error: %s' % e, file=sys.stderr)
        print('nothing was written for the failing dataset.', file=sys.stderr)
        return 1
    for n in notes:
        print(n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
