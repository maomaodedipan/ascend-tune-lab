#!/usr/bin/env python3
"""Fit suggested PD instance counts to available cluster NPUs/hosts.

min instance NPU size = DP * TP from launch (passed in as cost_p / cost_d).

avail_npus is the cluster/host *total* card count (device type × hosts), NOT the
cards assigned to the 1P1D QPS baseline. Baseline measurement uses min P + min D
only; leftover NPUs stay idle until this fit decides how many instances to scale.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def fit(
    suggested_n_p: int,
    suggested_n_d: int,
    cost_p: int,
    cost_d: int,
    avail_npus: int,
    avail_hosts: int | None = None,
) -> dict:
    if suggested_n_p < 1 or suggested_n_d < 1:
        raise SystemExit("suggested_n_p/n_d must be >= 1")
    if cost_p < 1 or cost_d < 1:
        raise SystemExit("cost_p/cost_d (DP*TP) must be >= 1")
    if avail_npus < 1:
        raise SystemExit("avail_npus must be >= 1")

    need = suggested_n_p * cost_p + suggested_n_d * cost_d
    ratio = suggested_n_d / suggested_n_p

    # Optional host packing: each instance needs at least one host slot if
    # exclusive; when avail_hosts set, also require n_p+n_d <= avail_hosts
    # (conservative; colocated P+D on one host can share — pass larger hosts
    # or None to skip).
    def fits(n_p: int, n_d: int) -> bool:
        if n_p * cost_p + n_d * cost_d > avail_npus:
            return False
        if avail_hosts is not None and (n_p + n_d) > avail_hosts:
            # allow colocated 1 host for 1P1D when both fit on one machine
            if not (n_p == 1 and n_d == 1 and cost_p + cost_d <= avail_npus):
                return False
        return True

    if fits(suggested_n_p, suggested_n_d):
        return {
            "suggested_n_p": suggested_n_p,
            "suggested_n_d": suggested_n_d,
            "deploy_n_p": suggested_n_p,
            "deploy_n_d": suggested_n_d,
            "deploy_ratio_desc": f"{suggested_n_p}P:{suggested_n_d}D",
            "feasible": True,
            "reason": "cluster can host suggested PD ratio",
            "need_npus": need,
            "avail_npus": avail_npus,
            "avail_hosts": avail_hosts,
            "cost_p_npus": cost_p,
            "cost_d_npus": cost_d,
            "target_n_d_over_n_p": ratio,
        }

    # Max feasible under approx same ratio: search n_p descending
    best = (1, 1)
    for n_p in range(suggested_n_p, 0, -1):
        n_d = max(1, int(math.ceil(n_p * ratio - 1e-12)))
        # also try n_d-1..n_d+1 for packing
        for nd in range(max(1, n_d - 1), n_d + 2):
            if fits(n_p, nd):
                # prefer closer to ratio, then larger scale
                cur_r = nd / n_p
                best_r = best[1] / best[0]
                if (n_p * cost_p + nd * cost_d) > (best[0] * cost_p + best[1] * cost_d) or (
                    abs(cur_r - ratio) < abs(best_r - ratio)
                    and (n_p * cost_p + nd * cost_d) >= (best[0] * cost_p + best[1] * cost_d)
                ):
                    best = (n_p, nd)
        if best != (1, 1) and best[0] >= n_p:
            break

    # brute force small space
    for n_p in range(1, suggested_n_p + 1):
        for n_d in range(1, max(suggested_n_d, int(math.ceil(suggested_n_p * ratio)) + 2)):
            if not fits(n_p, n_d):
                continue
            score = n_p * cost_p + n_d * cost_d
            best_score = best[0] * cost_p + best[1] * cost_d
            if score > best_score or (
                score == best_score and abs(n_d / n_p - ratio) < abs(best[1] / best[0] - ratio)
            ):
                best = (n_p, n_d)

    n_p, n_d = best
    return {
        "suggested_n_p": suggested_n_p,
        "suggested_n_d": suggested_n_d,
        "deploy_n_p": n_p,
        "deploy_n_d": n_d,
        "deploy_ratio_desc": f"{n_p}P:{n_d}D",
        "feasible": False,
        "reason": "suggested exceeds capacity; using max feasible near target ratio",
        "need_npus": need,
        "avail_npus": avail_npus,
        "avail_hosts": avail_hosts,
        "cost_p_npus": cost_p,
        "cost_d_npus": cost_d,
        "deploy_need_npus": n_p * cost_p + n_d * cost_d,
        "target_n_d_over_n_p": ratio,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suggested-n-p", type=int, required=True)
    ap.add_argument("--suggested-n-d", type=int, required=True)
    ap.add_argument("--cost-p", type=int, required=True, help="DP*TP for one Prefill instance")
    ap.add_argument("--cost-d", type=int, required=True, help="DP*TP for one Decode instance")
    ap.add_argument("--avail-npus", type=int, required=True)
    ap.add_argument("--avail-hosts", type=int, default=0, help="0 = ignore host count")
    ap.add_argument("--out-json", required=True)
    args = ap.parse_args()
    hosts = args.avail_hosts if args.avail_hosts > 0 else None
    result = fit(
        args.suggested_n_p,
        args.suggested_n_d,
        args.cost_p,
        args.cost_d,
        args.avail_npus,
        hosts,
    )
    Path(args.out_json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
