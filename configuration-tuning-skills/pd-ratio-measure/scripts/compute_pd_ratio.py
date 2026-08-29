#!/usr/bin/env python3
"""Compute best PD ratio from P/D QPS JSON results."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "qps" not in data:
        raise SystemExit(f"{path}: missing qps")
    return data


def compute(qps_p: float, qps_d: float, base_n_p: int = 1) -> dict:
    if qps_p <= 0 or qps_d <= 0:
        raise SystemExit("qps_p and qps_d must be > 0")
    ratio = qps_p / qps_d
    # N_D / N_P = QPS_P / QPS_D
    n_p = max(1, base_n_p)
    n_d_exact = ratio * n_p
    n_d = max(1, int(math.ceil(n_d_exact - 1e-12)))
    return {
        "qps_p": qps_p,
        "qps_d": qps_d,
        "ratio_qps_p_over_qps_d": ratio,
        "suggested_n_p": n_p,
        "suggested_n_d": n_d,
        "suggested_n_d_exact": n_d_exact,
        "suggested_ratio_desc": f"{n_p}P:{n_d}D",
        "formula": {
            "ratio": "QPS_P / QPS_D",
            "instances": "N_D / N_P = QPS_P / QPS_D",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--p-json", required=True)
    ap.add_argument("--d-json", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--base-n-p", type=int, default=1)
    args = ap.parse_args()

    p = _load(Path(args.p_json))
    d = _load(Path(args.d_json))
    result = compute(float(p["qps"]), float(d["qps"]), base_n_p=args.base_n_p)
    result["p_source"] = str(args.p_json)
    result["d_source"] = str(args.d_json)
    Path(args.out_json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
