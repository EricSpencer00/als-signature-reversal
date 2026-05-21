"""Emit docs/data.js containing the JSON the static site renders.

Embedded inline so GitHub Pages needs no fetch/CORS dance.
"""
from __future__ import annotations
import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RANKED = ROOT / "results" / "ranked_candidates.csv"
ALL_TOP50 = ROOT / "results" / "lincs_queries" / "ALL_TOP50.csv"
OUT_DIR = ROOT / "docs"
OUT_DIR.mkdir(exist_ok=True)
OUT = OUT_DIR / "data.js"

NUMERIC_PLACEHOLDER = {"-666", "666", "-1", "-999"}


def clean_perturbation(name: str) -> bool:
    """Drop L1000 metadata placeholders and obvious garbage."""
    s = (name or "").strip()
    if not s:
        return False
    if s in NUMERIC_PLACEHOLDER:
        return False
    try:
        float(s)
        return False  # pure numeric strings
    except ValueError:
        return True


def main() -> None:
    candidates = []
    with RANKED.open() as f:
        for row in csv.DictReader(f):
            if not clean_perturbation(row.get("perturbation", "")):
                continue
            candidates.append({
                "name": row["perturbation"],
                "n_sigs": int(row["n_signatures"]),
                "score_mean": float(row["lincs_score_mean"]),
                "score_max": float(row["lincs_score_max"]),
                "best_rank": int(row["best_rank"]),
                "phase": row["clinical_phase"] or "",
                "moa": row["moa"] or "",
                "target": row["target"] or "",
                "indication": row["indication"] or "",
                "trial_status": row["als_trial_status"] or "",
                "trial_notes": row["als_trial_notes"] or "",
                "composite": float(row["composite_score"]),
                "signatures": row["signatures"].split(";") if row["signatures"] else [],
            })

    # Per-signature stats
    sig_stats = {}
    with ALL_TOP50.open() as f:
        for row in csv.DictReader(f):
            s = row["signature"]
            d = sig_stats.setdefault(s, {"signature": s, "n_hits": 0, "top": None})
            d["n_hits"] += 1
            if d["top"] is None and clean_perturbation(row["perturbation"]):
                d["top"] = {
                    "name": row["perturbation"],
                    "score": float(row["score"]) if row["score"] else 0.0,
                    "cell_line": row["cell_line"],
                }

    # MoA category aggregation (top 60)
    moa_counts: dict[str, int] = {}
    for c in candidates[:60]:
        if c["moa"]:
            for m in c["moa"].split("|"):
                m = m.strip()
                if m:
                    moa_counts[m] = moa_counts.get(m, 0) + 1
    moa_top = sorted(moa_counts.items(), key=lambda kv: -kv[1])[:15]

    # Signature gene counts (from result JSON files)
    sig_dir = ROOT / "results" / "signatures"
    sig_genes = []
    order = ["FUS_KO", "FUS_R495X", "FUS_P525L_heteroz",
             "FUS_P525L_homoz", "TARDBP_M337V", "SHARED_MN"]
    for sig in order:
        p = sig_dir / f"{sig}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        sig_genes.append({
            "signature": sig,
            "n_significant": d.get("n_significant"),
            "n_up": d["n_up"],
            "n_down": d["n_down"],
            "up_top10": d["upGenes"][:10],
            "down_top10": d["dnGenes"][:10],
        })

    payload = {
        "generatedAt": "2026-05-20",
        "candidates": candidates,
        "sigStats": [sig_stats[s] for s in order if s in sig_stats],
        "moaTop": [{"moa": m, "count": n} for m, n in moa_top],
        "sigGenes": sig_genes,
        "stats": {
            "n_candidates": len(candidates),
            "n_hits_total": sum(s["n_hits"] for s in sig_stats.values()),
            "n_signatures": len(sig_genes),
            "n_in_hub": sum(1 for c in candidates if c["phase"]),
            "n_multi_sig": sum(1 for c in candidates if c["n_sigs"] >= 2),
        },
    }
    js = "window.ALS_DATA = " + json.dumps(payload, indent=2) + ";\n"
    OUT.write_text(js)
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(f"  candidates: {len(candidates)}")
    print(f"  signatures: {len(sig_genes)}")
    print(f"  moa categories: {len(moa_top)}")


if __name__ == "__main__":
    main()
