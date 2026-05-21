"""Query L1000CDS2 with each ALS motor-neuron signature in REVERSE mode.

API: POST https://maayanlab.cloud/L1000CDS2/query
Docs: https://maayanlab.cloud/L1000CDS2/help/

Reverse mode (`aggravate: false`) returns small-molecule perturbations whose
LINCS L1000 signatures invert the input — i.e., putative repurposable hits.

We query every per-genotype signature plus the SHARED_MN aggregate, save the
raw JSON response (for reproducibility), and emit a compact CSV per query
of the top 50 perturbations with score, cell-line, dose, and time-point.

Limitations to remember when reading results:
- L1000 spans ~12,328 genes; input genes not on the platform are dropped
  silently. Signatures of <10 overlapping genes per direction are unreliable.
- The cell line context (~62 lines) does not include motor neurons. Most hits
  come from MCF7, PC3, HA1E, etc — a TDP-43 / FUS gain-of-function signal in
  iPSC-MN may or may not transfer.
- Scores are based on the connectivity-map cosine distance; magnitudes are
  not P-values. Use as ranking only.
"""

from __future__ import annotations
import json
import pathlib
import sys
import time
import urllib.request

ENDPOINT = "https://maayanlab.cloud/L1000CDS2/query"
SIG_DIR = pathlib.Path("results/signatures")
OUT_DIR = pathlib.Path("results/lincs_queries")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SIGNATURES = [
    "FUS_KO",
    "FUS_R495X",
    "FUS_P525L_heteroz",
    "FUS_P525L_homoz",
    "TARDBP_M337V",
    "SHARED_MN",
]


def query(up_genes: list[str], dn_genes: list[str], label: str) -> dict:
    payload = {
        "data": {
            "upGenes": up_genes,
            "dnGenes": dn_genes,
        },
        "config": {
            "aggravate": False,         # reverse mode
            "searchMethod": "geneSet",
            "share": False,
            "combination": False,
            "db-version": "latest",
        },
        "metadata": [
            {"key": "Tag", "value": "ALS-iPSC-MN-signature-reversal"},
            {"key": "Source", "value": "Schweingruber et al. 2025, Nat Commun"},
            {"key": "Signature", "value": label},
        ],
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def to_rows(label: str, response: dict) -> list[dict]:
    rows = []
    for i, hit in enumerate(response.get("topMeta", [])):
        rows.append({
            "signature": label,
            "rank": i + 1,
            "score": hit.get("score"),
            "perturbation": hit.get("pert_desc") or hit.get("pert_id"),
            "pert_id": hit.get("pert_id"),
            "cell_line": hit.get("cell_id"),
            "dose_um": hit.get("pert_dose"),
            "time_h": hit.get("pert_time"),
            "overlap_up": hit.get("overlap", {}).get("up") if isinstance(hit.get("overlap"), dict) else None,
            "overlap_dn": hit.get("overlap", {}).get("dn") if isinstance(hit.get("overlap"), dict) else None,
        })
    return rows


def write_csv(rows: list[dict], path: pathlib.Path) -> None:
    import csv
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    all_rows = []
    for label in SIGNATURES:
        sig_path = SIG_DIR / f"{label}.json"
        if not sig_path.exists():
            print(f"SKIP {label}: no signature file at {sig_path}")
            continue
        sig = json.loads(sig_path.read_text())
        up = sig["upGenes"]
        dn = sig["dnGenes"]
        if len(up) < 5 or len(dn) < 5:
            print(f"SKIP {label}: too few genes (up={len(up)}, dn={len(dn)})")
            continue
        print(f"Querying L1000CDS2: {label} ({len(up)} up, {len(dn)} dn) ...",
              end=" ", flush=True)
        try:
            resp = query(up, dn, label)
        except Exception as e:
            print(f"FAILED: {e}")
            continue
        raw = OUT_DIR / f"{label}.json"
        raw.write_text(json.dumps(resp, indent=2))
        rows = to_rows(label, resp)
        csv_path = OUT_DIR / f"{label}.csv"
        write_csv(rows, csv_path)
        all_rows.extend(rows)
        print(f"top hit: {rows[0]['perturbation'] if rows else 'none'} "
              f"(score={rows[0]['score'] if rows else 'n/a'})")
        time.sleep(2.0)  # be polite to a free public API

    if all_rows:
        write_csv(all_rows, OUT_DIR / "ALL_TOP50.csv")
        print(f"\nWrote {len(all_rows)} rows across {len({r['signature'] for r in all_rows})} "
              f"signatures to {OUT_DIR / 'ALL_TOP50.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
