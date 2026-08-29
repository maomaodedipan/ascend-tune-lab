#!/usr/bin/env python3
"""Pick the recommended PD topology by best per-NPU QPS.

Formula ratio (QPS_P/QPS_D) only selects a *candidate* to verify.
Final recommendation is whichever topology has higher qps_per_npu.
If the candidate does not beat 1P1D baseline, adopt 1P1D.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "qps_per_npu" not in data:
        raise SystemExit(f"{path}: missing qps_per_npu")
    return data


def _parse_nd(topology: str, fallback_n_p: int, fallback_n_d: int) -> tuple[int, int]:
    m = re.match(r"^\s*(\d+)\s*P\s*[:x]?\s*(\d+)\s*D\s*$", topology or "", re.I)
    if m:
        return int(m.group(1)), int(m.group(2))
    return fallback_n_p, fallback_n_d


def recommend(baseline: dict, deploy: dict) -> dict:
    base_per = float(baseline["qps_per_npu"])
    dep_per = float(deploy["qps_per_npu"])
    improved = dep_per > base_per
    base_np, base_nd = _parse_nd(str(baseline.get("topology") or "1P1D"), 1, 1)
    cand_np, cand_nd = _parse_nd(
        str(deploy.get("topology") or ""),
        int(deploy.get("n_p") or 1),
        int(deploy.get("n_d") or 1),
    )
    if improved:
        rec_np, rec_nd = cand_np, cand_nd
        reason = (
            f"candidate per-NPU {dep_per:.4f} > baseline {base_per:.4f}; "
            f"recommend {rec_np}P:{rec_nd}D"
        )
    else:
        rec_np, rec_nd = base_np, base_nd
        reason = (
            f"candidate per-NPU {dep_per:.4f} <= baseline {base_per:.4f}; "
            f"adopt baseline {rec_np}P:{rec_nd}D"
        )
    return {
        "candidate_n_p": cand_np,
        "candidate_n_d": cand_nd,
        "candidate_ratio_desc": f"{cand_np}P:{cand_nd}D",
        "candidate_qps_per_npu": dep_per,
        "baseline_n_p": base_np,
        "baseline_n_d": base_nd,
        "baseline_ratio_desc": f"{base_np}P:{base_nd}D",
        "baseline_qps_per_npu": base_per,
        "per_npu_improved": improved,
        "recommended_n_p": rec_np,
        "recommended_n_d": rec_nd,
        "recommended_ratio_desc": f"{rec_np}P:{rec_nd}D",
        "rule": "final PD ratio = topology with best per-NPU QPS; no-improve -> 1P1D baseline",
        "reason": reason,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline-json", required=True)
    ap.add_argument("--deploy-json", required=True)
    ap.add_argument("--out-json", required=True)
    args = ap.parse_args()
    result = recommend(_load(Path(args.baseline_json)), _load(Path(args.deploy_json)))
    Path(args.out_json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
