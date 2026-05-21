# als-signature-reversal

End-to-end, reproducible pipeline for **reverse-signature drug repurposing** in ALS using published per-genotype iPSC motor-neuron transcriptomic profiles + the L1000 connectivity-map database.

> Input: published per-genotype DEGs from Schweingruber et al. 2025 (Nat Commun, [doi:10.1038/s41467-025-59679-1](https://doi.org/10.1038/s41467-025-59679-1), Supplementary Data 4).
>
> Output: a ranked list of small-molecule candidates whose own L1000 signatures invert the ALS motor-neuron signature, cross-validated against the Broad Drug Repurposing Hub and a curated table of compounds already trialled in ALS.

The novel contribution here is the **end-to-end reproducible pipeline + cross-validation layer**. The same end-to-end workflow has been described in published analyses (e.g. Krishnan et al. 2024 *ACS Omega* — Integrating Transcriptomic and Structural Insights for sporadic ALS), but to our knowledge no public repository ships the full pipeline with both the LINCS query layer **and** an ALS-trial cross-check.

## Status

This repo is a draft prepared in a single research session. It is **not** a peer-reviewed therapeutic claim. See [§ Limitations](#limitations).

## Repo layout

```
.
├── data/
│   ├── raw/
│   │   ├── schweingruber_2025_MOESM{3..7}.xlsx   (Nat Commun supplementary)
│   │   ├── repurposing_drugs.txt                  (Broad Drug Repurposing Hub, Corsello 2017)
│   │   ├── repurposing_samples.txt
│   │   └── GSE226482_counts.txt.gz                (raw counts — NOT used by current pipeline; kept for future re-DE)
│   └── curated/
│       └── als_trial_drugs.tsv                    (hand-curated ALS-trial outcomes table with citations)
├── scripts/
│   ├── 01_load_signatures.py                      (parse MOESM6 → per-genotype up/down JSON)
│   ├── 02_lincs_query.py                          (POST L1000CDS² /query in reverse mode)
│   ├── 03_cross_validate.py                       (merge with Repurposing Hub + ALS-trial table)
│   └── build_notebook.py                          (assemble the storytelling notebook)
├── notebooks/
│   └── als_signature_reversal.ipynb               (final report)
├── results/
│   ├── signatures/         (per-genotype up/down gene JSON + SHARED_MN consensus)
│   ├── lincs_queries/      (raw L1000CDS² responses + per-signature top-50 CSVs + ALL_TOP50.csv)
│   └── ranked_candidates.csv  (final composite ranking)
├── pyproject.toml
└── README.md
```

## Reproducing from scratch

```bash
cd /Users/eric/als-research/path1-signature-reversal
uv sync                                            # installs locked deps
uv run python scripts/01_load_signatures.py
uv run python scripts/02_lincs_query.py            # ~6 calls to L1000CDS², ~2s apart
uv run python scripts/03_cross_validate.py
uv run python scripts/build_notebook.py
uv run jupyter lab notebooks/als_signature_reversal.ipynb
```

Step 02 is the only network step that hits an external API. Step 01 reads pre-downloaded supplementary data; step 03 reads pre-downloaded Drug Repurposing Hub.

## Methodology summary

1. **Per-genotype DEG ingestion.** Six motor-neuron sheets from the Schweingruber supplementary Excel: `DEG_MN_{FUS_KO, FUS_R495X, FUS_P525L_heteroz, FUS_P525L_homoz, TARDBP_M337V}`. Keep `padj < 0.05`. Rank by `|log2FoldChange|`. Take top 150 up + top 150 down per genotype.
2. **Shared signature.** Genes called significant + concordant-sign in ≥ 3 / 5 genotypes (and never opposite-sign in the same set). This is the ALS-convergent core.
3. **L1000CDS² query.** For each signature: `POST https://maayanlab.cloud/L1000CDS2/query` with `aggravate: false`. Save raw JSON + flat CSV of top 50.
4. **Annotate against Broad Drug Repurposing Hub.** Name-normalize and merge to pull `clinical_phase`, `moa`, `target`.
5. **Cross-check ALS trials.** Merge against `data/curated/als_trial_drugs.tsv` (33 ALS-trialled compounds with cited outcomes). Apply a `−5` penalty to drugs that already failed in well-powered ALS trials.
6. **Composite rank.** `composite = n_signatures * mean_score − trial_penalty`. Output `results/ranked_candidates.csv`.

## What the top results look like

Sample of top composite-ranked candidates that map to the Repurposing Hub (full output in `results/ranked_candidates.csv`):

| Candidate | n_sigs | Mean LINCS score | Clinical phase | MoA |
|---|---|---|---|---|
| YM-155 | 5 | 0.0651 | Phase 2 | survivin inhibitor |
| vorinostat | 5 | 0.0616 | Launched | HDAC inhibitor |
| PLX-4720 | 4 | 0.0693 | Preclinical | RAF inhibitor |
| importazole | 5 | 0.0626 | — | importin-β inhibitor |
| PF-562271 | 3 | 0.0750 | Phase 1 | FAK inhibitor |
| CGP-60474 | 4 | 0.0570 | Preclinical | CDK inhibitor |

Hits cluster into mechanistic categories overlapping known ALS biology: **HDAC inhibition** (Guo et al. 2017), **nuclear–cytoplasmic transport restoration** (Boeynaems et al. 2016 — TDP-43/FUS mislocalization is a central ALS phenotype), and **B-Raf / MAPK inhibition** (independently flagged in *Brain* 2025 multi-omics repurposing). The Schweingruber paper itself concluded that **mitochondrial dysfunction is the shared MN pathology across FUS and TARDBP**, which matches several lipid/PKC hits.

## Limitations

These matter — please read before using or citing.

- **L1000 lacks motor-neuron context.** Cell lines in the L1000 panel are predominantly cancer + immortalized (MCF7, PC3, HA1E, A549, …). A reversal observed in MCF7 may not transfer to human motor neurons.
- **iPSC-MN DEGs have weak power.** The 2024 ALS iPSC-MN meta-analysis ([PMC11059082](https://pmc.ncbi.nlm.nih.gov/articles/PMC11059082/)) reports 13–43 DEGs between ALS and control cohorts on average. The isogenic design Schweingruber used boosts this to 500–2400 / genotype, but signal is still iPSC-stage and may not capture mature-MN biology.
- **L1000CDS² scores are not P-values.** They are connectivity-map cosine-distance derived; treat strictly as ranking.
- **Reverse signatures generate hypotheses, not validations.** No candidate here is recommended for clinical follow-up without independent preclinical confirmation in motor-neuron-relevant models (iPSC-MN rescue assays, *C9orf72* mouse models, *SOD1*-G93A mouse, postmortem signature comparison).
- **The ALS-trial cross-check is curated, not exhaustive.** It covers ~30 well-publicized trials but misses many smaller phase-1/2 studies. A drug not flagged is **not** "untried in ALS" — only "untried in our table."
- **The composite score is deliberately simple.** We do not weight MoA categories ad hoc.
- **No correction for L1000 cell-line popularity bias.** Some drugs appear in many cell-line-specific signatures and may score artificially high.
- **No statistical multiple-hypothesis correction.** N=6 signatures × 50 hits = 300 perturbation-signature pairs; we have not formally controlled FDR across this surface.

## Honest framing for any downstream use

This is a **computational hypothesis-generation tool**, not a treatment-prioritization framework. Top hits should be filtered by:

1. Does the MoA make biological sense for ALS (mitochondrial function, proteostasis, nucleocytoplasmic transport, glutamate, axonal transport)?
2. Has the compound been tested in an iPSC-MN ALS rescue assay (e.g. via Answer ALS or NeuroLINCS phenotypic screens)?
3. Is the clinical phase consistent with drug-like / safety properties?
4. Is the compound *not* already in ALS-trial failure logs?

Even after these filters, any candidate is a hypothesis pending wet-lab validation.

## Citations

- Schweingruber, C. et al. (2025). Single-cell RNA-sequencing reveals early mitochondrial dysfunction unique to motor neurons shared across FUS- and TARDBP-ALS. *Nat Commun* 16. doi:10.1038/s41467-025-59679-1. PMID 40389397.
- Duan, Q. et al. (2016). L1000CDS²: LINCS L1000 characteristic direction signatures search engine. *npj Syst Biol Appl* 2, 16015.
- Corsello, S. M. et al. (2017). The Drug Repurposing Hub: a next-generation drug library and information resource. *Nat Med* 23, 405–408.
- Subramanian, A. et al. (2017). A next generation connectivity map: L1000 platform and the first 1,000,000 profiles. *Cell* 171, 1437–1452.
- Boeynaems, S. et al. (2016). Inside out: the role of nucleocytoplasmic transport in ALS and FTLD. *Acta Neuropathol* 132, 159–173.
- Guo, W. et al. (2017). HDAC6 inhibition reverses axonal transport defects in motor neurons derived from FUS-ALS patients. *Nat Commun* 8, 861.

## License

Code: MIT. Data: subject to source-data licenses (Schweingruber supplementary tables are licensed CC-BY-4.0 per Nature Communications policy; Drug Repurposing Hub redistribution per its terms).

## Author

Eric Spencer ([EricSpencer00](https://github.com/EricSpencer00)). Drafted as part of an open-source ALS computational-biology contribution.
