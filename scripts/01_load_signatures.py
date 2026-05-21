"""Load per-genotype motor-neuron DEG tables from Schweingruber et al. 2025
(Nat Commun, doi:10.1038/s41467-025-59679-1, Supplementary Data 4 / MOESM6).

Produces a JSON sidecar per genotype with top-up and top-down gene lists
suitable for L1000CDS2 reverse-signature queries.

The L1000 platform measures ~978 landmark genes (extrapolated to ~12,328).
L1000CDS2 documentation recommends queries with ≤150 genes per direction.

Methodology notes:
- We keep only genes with padj < 0.05 (Benjamini–Hochberg).
- Rank by absolute log2FoldChange among significant hits.
- The Schweingruber paper used Wilcoxon + DESeq2 pseudobulk on Smart-seq2 data
  with isogenic controls; the DEG tables are already cell-type specific (MN).
- We treat each ALS condition as a separate signature, plus an aggregated
  "shared MN ALS" signature (genes significant + concordant sign in ≥3/5).
"""

from __future__ import annotations
import json
import pathlib

import openpyxl

XLSX = pathlib.Path("data/raw/schweingruber_2025_MOESM6.xlsx")
OUT_DIR = pathlib.Path("results/signatures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Motor-neuron sheets per ALS genotype (vs isogenic Ctrl)
MN_SHEETS = [
    "DEG_MN_FUS_KO",
    "DEG_MN_FUS_R495X",
    "DEG_MN_FUS_P525L_heteroz",
    "DEG_MN_FUS_P525L_homoz",
    "DEG_MN_TARDBP_M337V",
]

PADJ_CUTOFF = 0.05
TOP_N = 150  # per direction; matches L1000CDS2 recommendation


def load_sheet(wb, sheet: str) -> list[dict]:
    ws = wb[sheet]
    rows = ws.iter_rows(min_row=1, values_only=True)
    header = next(rows)
    # Some sheets (e.g. DEG_MN_FUS_KO) carry a title row above the real header.
    # Detect by checking for the canonical column "gene".
    if header is None or "gene" not in [str(c) for c in header if c is not None]:
        header = next(rows)
    out = []
    for r in rows:
        d = dict(zip(header, r))
        # Skip rows where any required numeric is None/NaN
        if d.get("padj") is None or d.get("log2FoldChange") is None:
            continue
        if d.get("gene") is None:
            continue
        out.append({
            "gene": str(d["gene"]).strip(),
            "log2FC": float(d["log2FoldChange"]),
            "padj": float(d["padj"]),
        })
    return out


def signature_from_rows(rows: list[dict]) -> dict:
    sig = [r for r in rows if r["padj"] < PADJ_CUTOFF]
    sig.sort(key=lambda r: abs(r["log2FC"]), reverse=True)
    up = [r for r in sig if r["log2FC"] > 0][:TOP_N]
    down = [r for r in sig if r["log2FC"] < 0][:TOP_N]
    return {
        "n_significant": len(sig),
        "n_up": len(up),
        "n_down": len(down),
        "upGenes": [r["gene"] for r in up],
        "dnGenes": [r["gene"] for r in down],
        "up_details": up,
        "down_details": down,
    }


def shared_signature(per_genotype: dict[str, dict]) -> dict:
    """Genes called significant + concordant-sign in >=3/5 genotypes.

    For each gene, count up-votes and down-votes across genotypes.
    A gene is "shared up" if it appears in upGenes for >=3 conditions
    AND never in down for those same conditions. Same for down.
    """
    up_counts: dict[str, int] = {}
    down_counts: dict[str, int] = {}
    for sig in per_genotype.values():
        for g in sig["upGenes"]:
            up_counts[g] = up_counts.get(g, 0) + 1
        for g in sig["dnGenes"]:
            down_counts[g] = down_counts.get(g, 0) + 1
    shared_up = sorted(
        [g for g, c in up_counts.items() if c >= 3 and down_counts.get(g, 0) == 0],
        key=lambda g: -up_counts[g],
    )
    shared_down = sorted(
        [g for g, c in down_counts.items() if c >= 3 and up_counts.get(g, 0) == 0],
        key=lambda g: -down_counts[g],
    )
    return {
        "n_up": len(shared_up),
        "n_down": len(shared_down),
        "upGenes": shared_up[:TOP_N],
        "dnGenes": shared_down[:TOP_N],
        "criterion": "padj<0.05 in >=3/5 MN genotypes with concordant sign",
    }


def main() -> None:
    wb = openpyxl.load_workbook(XLSX, read_only=True)
    per_genotype = {}
    for sheet in MN_SHEETS:
        genotype = sheet.replace("DEG_MN_", "")
        rows = load_sheet(wb, sheet)
        sig = signature_from_rows(rows)
        per_genotype[genotype] = sig
        path = OUT_DIR / f"{genotype}.json"
        path.write_text(json.dumps(sig, indent=2))
        print(f"  {genotype}: {sig['n_significant']:>5d} sig genes "
              f"(up={sig['n_up']}, down={sig['n_down']}) -> {path}")

    shared = shared_signature(per_genotype)
    (OUT_DIR / "SHARED_MN.json").write_text(json.dumps(shared, indent=2))
    print(f"  SHARED_MN: up={shared['n_up']}, down={shared['n_down']} "
          f"-> {OUT_DIR / 'SHARED_MN.json'}")


if __name__ == "__main__":
    main()
