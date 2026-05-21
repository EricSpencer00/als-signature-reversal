"""Assemble the final Jupyter notebook stitching all stages together.

We build the notebook deterministically with nbformat so the file is
text-diffable and reproducible. Outputs are not embedded — running the
notebook on a fresh checkout re-derives every cell.
"""

from __future__ import annotations
import pathlib

import nbformat as nbf

OUT = pathlib.Path("notebooks/als_signature_reversal.ipynb")
OUT.parent.mkdir(parents=True, exist_ok=True)

nb = nbf.v4.new_notebook()
nb.metadata["kernelspec"] = {
    "name": "python3",
    "display_name": "Python 3",
    "language": "python",
}

cells: list = []

cells.append(nbf.v4.new_markdown_cell("""\
# ALS iPSC-MN signature reversal → repurposable drug candidates

**Goal.** Take published, per-genotype differential-expression profiles from \
ALS iPSC-derived motor neurons, query the L1000 connectivity-map database in \
**reverse mode**, and produce a cross-validated ranking of small-molecule \
candidates whose own transcriptional fingerprint inverts the disease signature.

**Source DEGs.** Schweingruber et al. (2025) *Nat Commun* 16, \
[doi:10.1038/s41467-025-59679-1](https://doi.org/10.1038/s41467-025-59679-1). \
Isogenic iPSC lines (FUS R495X, FUS P525L het/hom, FUS-KO, TARDBP M337V) \
differentiated to spinal motor neurons via Smart-seq2 scRNA-seq, pseudobulked, \
DESeq2 per-genotype vs. isogenic control. We use Supplementary Data 4 \
(MOESM6) directly — *not* a re-analysis of the raw counts.

**LINCS query.** L1000CDS² REST API \
(https://maayanlab.cloud/L1000CDS2/query), `aggravate: false` (reverse \
mode), top 50 perturbations per signature.

**Cross-validation layers.**
1. *Broad Drug Repurposing Hub* (Corsello 2017) — annotate clinical phase, \
   mechanism of action, primary target.
2. *Curated ALS-trial table* — flag drugs already tried in well-powered \
   ALS trials. Drugs that already **failed** carry a penalty (already-explored \
   hypothesis); approved drugs (riluzole, edaravone, tofersen) act as a \
   positive sanity check.

**Honest caveats up front.**

- L1000 spans ~12,328 genes across ~62 cell lines; **no motor-neuron context**. \
  A signature that reverses in MCF7 may not reverse in human MNs.
- iPSC-MN DEGs have weak power (the 2024 meta-analysis reports 13–43 DEGs \
  between ALS and control iPSC-MN cohorts on average). Schweingruber's \
  isogenic design partially mitigates this — they recover 500–2400 \
  significant genes per genotype.
- Reverse-signature hits are **hypotheses**, not validations. None of the top \
  candidates here are proposed for clinical use without independent \
  preclinical confirmation in MN-relevant models.
- The composite score is intentionally simple. We do not over-fit to known \
  biology with hand-picked MoA weights.\
"""))

cells.append(nbf.v4.new_markdown_cell("""\
## 1 · Environment\

This notebook expects to be launched from the repo root via \
`uv run jupyter lab notebooks/als_signature_reversal.ipynb`. \
Dependencies are pinned in `pyproject.toml`."""))

cells.append(nbf.v4.new_code_cell("""\
from __future__ import annotations
import csv
import json
import pathlib

import pandas as pd

ROOT = pathlib.Path('.').resolve()
if ROOT.name == 'notebooks':
    ROOT = ROOT.parent
print('Working from:', ROOT)
"""))

cells.append(nbf.v4.new_markdown_cell("""\
## 2 · Per-genotype motor-neuron signatures

Each ALS condition vs. isogenic control. Top 150 up- and 150 down-regulated \
genes by |log2FC| among padj < 0.05 hits."""))

cells.append(nbf.v4.new_code_cell("""\
sig_dir = ROOT / 'results' / 'signatures'
sig_summary = []
for path in sorted(sig_dir.glob('*.json')):
    sig = json.loads(path.read_text())
    sig_summary.append({
        'signature': path.stem,
        'n_significant': sig.get('n_significant', '—'),
        'n_up': sig['n_up'],
        'n_down': sig['n_down'],
    })
pd.DataFrame(sig_summary)
"""))

cells.append(nbf.v4.new_code_cell("""\
# Inspect the SHARED_MN consensus signature
shared = json.loads((sig_dir / 'SHARED_MN.json').read_text())
print('Shared MN signature criterion:', shared['criterion'])
print(f"Up ({shared['n_up']}): {', '.join(shared['upGenes'][:25])} ...")
print(f"Down ({shared['n_down']}): {', '.join(shared['dnGenes'][:25])} ...")
"""))

cells.append(nbf.v4.new_markdown_cell("""\
## 3 · LINCS L1000CDS² reverse-mode hits

Top 50 small-molecule perturbations whose L1000 signatures invert each input \
signature. Score is the cosine-distance-based connectivity score; higher \
absolute scores indicate stronger reversal."""))

cells.append(nbf.v4.new_code_cell("""\
top50 = pd.read_csv(ROOT / 'results' / 'lincs_queries' / 'ALL_TOP50.csv')
top50.head(10)
"""))

cells.append(nbf.v4.new_code_cell("""\
# How many distinct perturbations across signatures?
print('Distinct top-50 perturbations:', top50['perturbation'].nunique())
print('Hits per signature:')
print(top50.groupby('signature').size())
"""))

cells.append(nbf.v4.new_markdown_cell("""\
## 4 · Composite ranking with cross-validation"""))

cells.append(nbf.v4.new_code_cell("""\
ranked = pd.read_csv(ROOT / 'results' / 'ranked_candidates.csv')
# Strip out obvious LINCS metadata placeholders that aren't real compounds
ranked = ranked[~ranked['perturbation'].astype(str).str.fullmatch(r'-?\\d+')]
ranked.head(25)
"""))

cells.append(nbf.v4.new_markdown_cell("""\
### 4a · Top candidates that ALSO appear in the Drug Repurposing Hub

These are clinical-grade compounds with known mechanism — the strongest \
candidates for follow-up because they have annotated targets and are \
typically already drug-like."""))

cells.append(nbf.v4.new_code_cell("""\
clin = ranked[ranked['clinical_phase'].astype(str).str.len() > 0]
clin = clin[~clin['clinical_phase'].isin(['', 'nan'])]
clin = clin[['perturbation', 'n_signatures', 'lincs_score_mean',
             'clinical_phase', 'moa', 'target', 'als_trial_status',
             'composite_score']]
clin.head(20)
"""))

cells.append(nbf.v4.new_markdown_cell("""\
### 4b · Mechanism-of-action distribution among top candidates

Aggregating MoA across the top 50 hits gives a more interpretable read than \
individual compounds — convergence on a pathway is stronger evidence than \
convergence on a single molecule (which can reflect L1000 cell-line biases)."""))

cells.append(nbf.v4.new_code_cell("""\
moa_counts = (
    ranked[ranked['moa'].astype(str).str.len() > 0]
    .head(60)
    .groupby('moa').size()
    .sort_values(ascending=False)
    .head(20)
)
moa_counts
"""))

cells.append(nbf.v4.new_markdown_cell("""\
## 5 · Sanity checks

### 5a · Approved ALS drugs as positive controls

If our pipeline recovers approved ALS drugs from a random direction, that's \
problematic. Below we look up each approved ALS drug in the FULL L1000 \
top-50 lists across all signatures."""))

cells.append(nbf.v4.new_code_cell("""\
approved = ['riluzole', 'edaravone', 'tofersen']
top50_lower = top50.assign(p=top50['perturbation'].astype(str).str.lower())
top50_lower[top50_lower['p'].isin(approved)][
    ['signature', 'rank', 'score', 'perturbation', 'cell_line']
]
"""))

cells.append(nbf.v4.new_markdown_cell("""\
*Expected behaviour:* approved ALS drugs may or may not appear — L1000 \
covers ~20k chemical perturbations and our signatures may not be \
sensitive enough to recover them. **Their absence is uninformative; \
their presence is mildly encouraging.**

### 5b · Failed ALS drugs as negative controls

Lithium, ceftriaxone, minocycline, creatine — all extensively trialled \
and **failed**. If our top hits are dominated by drugs we already know \
don't work, the method is producing recycled-and-disproven hypotheses."""))

cells.append(nbf.v4.new_code_cell("""\
failed = ['lithium', 'ceftriaxone', 'minocycline', 'creatine',
          'coenzyme q10', 'masitinib', 'arimoclomol', 'ibudilast']
top50_lower[top50_lower['p'].isin(failed)][
    ['signature', 'rank', 'score', 'perturbation', 'cell_line']
]
"""))

cells.append(nbf.v4.new_markdown_cell("""\
## 6 · Interpretation\

The top candidates cluster into a few mechanistic categories that overlap \
known ALS biology:

- **HDAC inhibitors** (vorinostat, salermide, panobinostat-like): \
  HDAC6 inhibition is an active ALS-therapeutic hypothesis (improves \
  mitochondrial transport, ameliorates TDP-43 toxicity preclinically — \
  Guo et al. 2017 *Nat Commun*).
- **Nuclear-cytoplasmic transport modulators** (importazole, KPT-330-like): \
  ALS-causative TDP-43 / FUS proteins mislocalize between nucleus and \
  cytoplasm; restoring nucleocytoplasmic transport is a major ALS \
  therapeutic axis (Boeynaems et al. 2016 *Nat Neurosci*).
- **MAPK/RAF/JNK pathway**: independently flagged by *Brain* 2025 \
  multi-omics repurposing study (B-Raf inhibitors).
- **Mitochondrial / lipid signalling**: the Schweingruber paper's own \
  conclusion was that **mitochondrial dysfunction is the shared MN \
  pathology across FUS and TARDBP**. Hits in lipid metabolism (PLA2 \
  inhibitors, ingenol PKC modulators) are consistent.

**Categories that should be treated with extra skepticism:**

- **PMA, ionomycin, and other "common cell perturbants"**: these score \
  high in many L1000 reverse-signature analyses because they perturb \
  many genes non-specifically.
- **YM-155 (survivin inhibitor)**: scores highly across many \
  signature-reversal studies; signal may be cell-line-specific.
- Any **kinase-inhibitor "tool compound"** without a clinical phase.

## 7 · Limitations and what this does NOT do\

- No motor-neuron LINCS data (L1000 platform uses cancer + immortalized lines).
- No validation in iPSC-MN rescue assays — purely computational ranking.
- Schweingruber DEGs are from isogenic iPSC at differentiation days 2-4; \
  post-mortem signatures would differ.
- Combination-therapy / dose-dependence not addressed.
- Statistical significance of L1000CDS² scores is not P-value-like; \
  treat as ranking only.

## 8 · Re-running\

```bash
uv sync
uv run python scripts/01_load_signatures.py
uv run python scripts/02_lincs_query.py    # hits L1000CDS² (be polite, ~6 calls)
uv run python scripts/03_cross_validate.py
uv run python scripts/build_notebook.py
uv run jupyter lab notebooks/als_signature_reversal.ipynb
```\
"""))

nb["cells"] = cells
nbf.write(nb, OUT)
print(f"Wrote {OUT} with {len(cells)} cells.")
