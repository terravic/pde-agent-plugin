#!/usr/bin/env python3
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Reference Bring-Your-Own-Algorithm (BYOA) Script: Proprietary CNS BBB Scorer.

Demonstrates how a user or organization can plug a private computational model
or proprietary scoring function into the Pharmakon Discovery Engine (PDE)
without exposing their proprietary source code to external endpoints.

Contract:
  - Accepts `--input <path>` (.json or .csv) and `--output <path>` (optional,
    defaults to stdout).
  - Computes a composite `cns_bbb_score` (0.0 to 1.0, higher is better) from:
      1. Unbound brain partition (`kp_uu_brain`, weight 0.45)
      2. P-gp / BCRP efflux ratio (`mdck_er`, weight 0.30)
      3. CNS physicochemical desirability (`mw`, `tpsa`, `logp`, `hbd`, `pka`, weight 0.25)
  - Emits structured JSON records consumed by `pde custom run` (Phase 1) and
    evaluated offline by `pde custom analyze` (Phase 2).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

ALGORITHM_ID = "proprietary-cns-bbb-mpo@1.2.0"


def _clamp(val: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, val))


def _monotonic_decreasing(val: float, good: float, bad: float) -> float:
    """Piecewise linear desirability: 1.0 at <= good, 0.0 at >= bad."""
    if val <= good:
        return 1.0
    if val >= bad:
        return 0.0
    return (bad - val) / (bad - good)


def _monotonic_increasing(val: float, bad: float, good: float) -> float:
    """Piecewise linear desirability: 0.0 at <= bad, 1.0 at >= good."""
    if val <= bad:
        return 0.0
    if val >= good:
        return 1.0
    return (val - bad) / (good - bad)


def _band_desirability(
    val: float, low_bad: float, low_good: float, high_good: float, high_bad: float
) -> float:
    """Trapezoidal desirability for properties with an optimal window (e.g., TPSA)."""
    if val <= low_bad or val >= high_bad:
        return 0.0
    if low_good <= val <= high_good:
        return 1.0
    if val < low_good:
        return (val - low_bad) / (low_good - low_bad)
    return (high_bad - val) / (high_bad - high_good)


def score_compound(row: dict[str, Any]) -> dict[str, Any]:
    """Compute proprietary CNS penetrance & potency composite score for one record."""
    cid = str(row.get("compound_id") or row.get("id") or "unknown")
    kp_uu = float(row.get("kp_uu_brain", 0.0))
    mdck_er = float(row.get("mdck_er", 10.0))
    ic50_nm = float(row.get("ic50_nm", 1000.0))
    mw = float(row.get("mw", 500.0))
    tpsa = float(row.get("tpsa", 120.0))
    logp = float(row.get("logp", 5.0))
    hbd = float(row.get("hbd", 4.0))
    pka = float(row.get("pka", 10.0))

    # 1. Unbound brain partition desirability (target Kp,uu >= 0.75)
    kp_uu_desirability = _monotonic_increasing(kp_uu, bad=0.05, good=0.80)

    # 2. Efflux desirability (target MDCK-MDR1 ER <= 1.0; severe penalty >= 4.0)
    efflux_desirability = _monotonic_decreasing(mdck_er, good=1.0, bad=4.0)

    # 3. CNS physicochemical desirability across 5 descriptors
    d_mw = _monotonic_decreasing(mw, good=340.0, bad=480.0)
    d_tpsa = _band_desirability(
        tpsa, low_bad=20.0, low_good=40.0, high_good=75.0, high_bad=105.0
    )
    d_logp = _monotonic_decreasing(logp, good=2.0, bad=4.5)
    d_hbd = _monotonic_decreasing(hbd, good=1.0, bad=3.5)
    d_pka = _monotonic_decreasing(pka, good=7.0, bad=9.5)
    physchem_desirability = (d_mw + d_tpsa + d_logp + d_hbd + d_pka) / 5.0

    # 4. Potency adjustment factor (pic50 bonus for sub-10 nM leads)
    pic50 = 9.0 - math.log10(max(ic50_nm, 0.01))
    potency_desirability = _monotonic_increasing(pic50, bad=6.5, good=8.8)

    # Composite weighted score
    cns_bbb_score = _clamp(
        0.40 * kp_uu_desirability
        + 0.25 * efflux_desirability
        + 0.20 * physchem_desirability
        + 0.15 * potency_desirability
    )

    return {
        "compound_id": cid,
        "series": row.get("series"),
        "smiles": row.get("smiles"),
        "cns_bbb_score": round(cns_bbb_score, 4),
        "kp_uu_component": round(kp_uu_desirability, 4),
        "efflux_component": round(efflux_desirability, 4),
        "physchem_component": round(physchem_desirability, 4),
        "potency_component": round(potency_desirability, 4),
        "efflux_liability": mdck_er >= 2.5,
        "raw_inputs": {
            "ic50_nm": ic50_nm,
            "kp_uu_brain": kp_uu,
            "mdck_er": mdck_er,
            "mw": mw,
            "tpsa": tpsa,
            "logp": logp,
            "hbd": hbd,
            "pka": pka,
        },
    }


def load_input_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() in (".csv", ".tsv"):
        delim = "\t" if path.suffix.lower() == ".tsv" else ","
        with path.open("r", encoding="utf-8") as fh:
            return list(csv.DictReader(fh, delimiter=delim))
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("records", "compounds", "items"):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError(f"Unsupported JSON structure in {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run proprietary CNS BBB multiparameter scoring algorithm."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to input .json or .csv compound file.",
    )
    parser.add_argument(
        "--output",
        required=False,
        type=Path,
        default=None,
        help="Optional output JSON path (writes to stdout if omitted).",
    )
    args = parser.parse_args(argv)

    raw_rows = load_input_records(args.input)
    scored_records = [score_compound(row) for row in raw_rows]

    payload = {
        "algorithm_id": ALGORITHM_ID,
        "metric_primary": "cns_bbb_score",
        "records": scored_records,
    }
    output_text = json.dumps(payload, indent=2) + "\n"
    if args.output is not None:
        args.output.write_text(output_text, encoding="utf-8")
    else:
        sys.stdout.write(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
