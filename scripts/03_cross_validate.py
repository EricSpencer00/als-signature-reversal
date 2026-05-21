"""Cross-validate L1000CDS2 hits against:

  (a) Broad Drug Repurposing Hub — annotate clinical phase + MoA + target.
      Source: https://clue.io/repurposing
      File: data/raw/repurposing_drugs.txt (Corsello et al. 2017, Nat Med)

  (b) Curated ALS-trial drug table — flag drugs already tried in ALS, with
      their outcome. A drug that ALREADY FAILED in a well-powered ALS trial
      is a NEGATIVE signal for repurposing (already-explored hypothesis).
      Approved drugs (riluzole, edaravone, tofersen) are POSITIVE controls.

Output: results/ranked_candidates.csv with composite ranking columns.

Scoring:
  - lincs_score: max |L1000CDS2 score| across signatures the drug appears in
  - n_signatures: how many of the 6 signatures (5 genotypes + SHARED_MN)
                  rank this drug in their top-50
  - clinical_phase: from Repurposing Hub
  - als_trial_status: from curated table — approved / failed / mixed / null
  - moa: mechanism of action
  - target: gene targets

The composite_score is intentionally simple:
  composite = (n_signatures * lincs_score_mean) -
              (5 if als_trial_status == 'failed' else 0)

We do NOT add ad-hoc weights for MoA categories beyond the trial-status
penalty — interpretation is left to the reader.
"""

from __future__ import annotations
import csv
import json
import pathlib
import re

LINCS_DIR = pathlib.Path("results/lincs_queries")
ALL_TOP50 = LINCS_DIR / "ALL_TOP50.csv"
HUB_DRUGS = pathlib.Path("data/raw/repurposing_drugs.txt")
TRIAL_TSV = pathlib.Path("data/curated/als_trial_drugs.tsv")
OUT = pathlib.Path("results/ranked_candidates.csv")
OUT.parent.mkdir(parents=True, exist_ok=True)

NORM_RE = re.compile(r"[\s,\-/()\[\]]+")


def norm(name: str | None) -> str:
    if not name:
        return ""
    return NORM_RE.sub("", name).lower()


def load_lincs_rows() -> list[dict]:
    with ALL_TOP50.open() as f:
        return list(csv.DictReader(f))


def load_hub() -> dict[str, dict]:
    """Return normalized-name -> {clinical_phase, moa, target, indication}."""
    out: dict[str, dict] = {}
    if not HUB_DRUGS.exists():
        return out
    with HUB_DRUGS.open() as f:
        # The Hub file has metadata lines starting with ! and a tab header.
        header = None
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("!") or not line.strip():
                continue
            fields = line.split("\t")
            if header is None:
                header = fields
                continue
            row = dict(zip(header, fields))
            n = norm(row.get("pert_iname"))
            if n:
                out[n] = {
                    "pert_iname": row.get("pert_iname"),
                    "clinical_phase": row.get("clinical_phase"),
                    "moa": row.get("moa"),
                    "target": row.get("target"),
                    "indication": row.get("indication"),
                }
    return out


def load_trial_drugs() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not TRIAL_TSV.exists():
        return out
    with TRIAL_TSV.open() as f:
        rdr = csv.DictReader(f, delimiter="\t")
        for row in rdr:
            n = norm(row["drug"])
            if n:
                out[n] = row
            # Also index hyphen-separated synonyms (e.g. "sodium phenylbutyrate-taurursodiol")
            for syn in row["drug"].split("-"):
                ns = norm(syn)
                if ns and ns not in out:
                    out[ns] = row
    return out


def main() -> None:
    lincs_rows = load_lincs_rows()
    hub = load_hub()
    trials = load_trial_drugs()
    print(f"Loaded: {len(lincs_rows)} LINCS rows, "
          f"{len(hub)} Hub drugs, {len(trials)} trial-drug entries.")

    # Aggregate per drug
    by_drug: dict[str, dict] = {}
    for r in lincs_rows:
        name = r["perturbation"] or r["pert_id"]
        if not name:
            continue
        n = norm(name)
        try:
            score = float(r["score"]) if r["score"] else 0.0
        except ValueError:
            score = 0.0
        d = by_drug.setdefault(n, {
            "perturbation": name,
            "signatures": set(),
            "scores": [],
            "best_rank": int(r["rank"]) if r["rank"] else 9999,
        })
        d["signatures"].add(r["signature"])
        d["scores"].append(score)
        d["best_rank"] = min(d["best_rank"], int(r["rank"]) if r["rank"] else 9999)

    rows = []
    for n, d in by_drug.items():
        hub_row = hub.get(n, {})
        trial_row = trials.get(n, {})
        n_sigs = len(d["signatures"])
        score_mean = sum(d["scores"]) / len(d["scores"])
        score_max = max(d["scores"])
        trial_status = trial_row.get("status") or ""
        penalty = 5 if trial_status == "failed" else 0
        composite = (n_sigs * score_mean) - penalty
        rows.append({
            "perturbation": d["perturbation"],
            "n_signatures": n_sigs,
            "signatures": ";".join(sorted(d["signatures"])),
            "lincs_score_mean": round(score_mean, 4),
            "lincs_score_max": round(score_max, 4),
            "best_rank": d["best_rank"],
            "clinical_phase": hub_row.get("clinical_phase", ""),
            "moa": hub_row.get("moa", ""),
            "target": hub_row.get("target", ""),
            "indication": hub_row.get("indication", ""),
            "als_trial_status": trial_status,
            "als_trial_notes": trial_row.get("notes", ""),
            "composite_score": round(composite, 4),
        })

    rows.sort(key=lambda r: (-r["composite_score"], r["best_rank"]))
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} unique drugs to {OUT}")

    # Quick summary
    multi = [r for r in rows if r["n_signatures"] >= 2]
    in_hub = [r for r in rows if r["clinical_phase"]]
    failed = [r for r in rows if r["als_trial_status"] == "failed"]
    approved = [r for r in rows if r["als_trial_status"] == "approved"]
    print(f"  hit >=2 signatures: {len(multi)}")
    print(f"  matched to Repurposing Hub: {len(in_hub)}")
    print(f"  already-failed ALS trials in list: {len(failed)}")
    print(f"  already-approved ALS drugs in list: {len(approved)}")
    if approved:
        print(f"    {[r['perturbation'] for r in approved]}")
    print("\nTop 15 by composite score:")
    for r in rows[:15]:
        print(f"  {r['perturbation'][:42]:42s}  n_sig={r['n_signatures']}  "
              f"score={r['lincs_score_mean']:.4f}  "
              f"phase={r['clinical_phase']:<14s}  "
              f"moa={(r['moa'] or '')[:38]}")


if __name__ == "__main__":
    main()
