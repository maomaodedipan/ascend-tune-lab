#!/usr/bin/env python3
"""Validate PD config consistency (roles, cards, kv fields, proxy lists)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from compute_pd_params import compute  # noqa: E402


KEEP_FIELDS = (
    "kv_connector",
    "kv_role",
    "kv_buffer_device",
    "kv_parallel_size",
    "kv_rank",
    "tp_size",
)

REPLACE_ONLY = (
    "kv_port",
    "engine_id",
    "kv_connector_extra_config.prefill.dp_size",
    "kv_connector_extra_config.decode.dp_size",
)


def _bash_blocks(md: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = None
    buf: list[str] = []
    in_bash = False
    for line in md.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            buf = []
            in_bash = False
            continue
        if current is None:
            continue
        if line.strip().startswith("```bash"):
            in_bash = True
            buf = []
            continue
        if in_bash and line.strip().startswith("```"):
            in_bash = False
            sections[current] = "\n".join(buf).strip()
            continue
        if in_bash:
            buf.append(line)
    return sections


def _find(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return m.group(1) if m else None


def validate(md: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or compute(md)
    blocks = _bash_blocks(md)
    prefill = blocks.get("Prefill 拉起命令", "") or blocks.get("Prefill", "")
    decode = blocks.get("Decode 拉起命令", "") or blocks.get("Decode", "")

    errors: list[str] = []
    warnings: list[str] = []

    if not prefill.strip():
        errors.append("missing Prefill launch command")
    if not decode.strip():
        errors.append("missing Decode launch command")

    p_role = _find(r'"kv_role"\s*:\s*"([^"]+)"', prefill) or ""
    d_role = _find(r'"kv_role"\s*:\s*"([^"]+)"', decode) or ""
    if p_role and p_role != "kv_producer":
        errors.append(f"Prefill kv_role should be kv_producer, got {p_role}")
    if d_role and d_role != "kv_consumer":
        errors.append(f"Decode kv_role should be kv_consumer, got {d_role}")

    p_conn = _find(r'"kv_connector"\s*:\s*"([^"]+)"', prefill)
    d_conn = _find(r'"kv_connector"\s*:\s*"([^"]+)"', decode)
    if p_conn and d_conn and p_conn != d_conn:
        warnings.append(f"Prefill/Decode kv_connector differ: {p_conn} vs {d_conn} (keep both as-is; confirm tutorial)")

    # Visible devices vs tp * (local expectation): count commas+1 in ASCEND_RT_VISIBLE_DEVICES if present
    def _visible_count(cmd: str) -> int | None:
        m = re.search(r"ASCEND_RT_VISIBLE_DEVICES=([0-9,\s]+)", cmd)
        if not m:
            return None
        parts = [x.strip() for x in m.group(1).split(",") if x.strip()]
        return len(parts) if parts else None

    p_vis = _visible_count(prefill)
    d_vis = _visible_count(decode)
    p_need = params["prefill_tp_size"]  # per-process; if launch is multi-DP one process may differ
    # Prefer: visible cards on a node should equal tp * dp_size_local when single-node full launch
    p_node_need = params["prefill_tp_size"] * params["prefill_dp_size_local"]
    d_node_need = params["decode_tp_size"] * params["decode_dp_size_local"]
    min_p = int(params.get("min_p_instance_npus") or p_node_need)
    min_d = int(params.get("min_d_instance_npus") or d_node_need)
    if p_vis is not None and p_vis != p_node_need and p_vis != params["prefill_tp_size"]:
        warnings.append(
            f"Prefill ASCEND_RT_VISIBLE_DEVICES count={p_vis}, expected {p_node_need} "
            f"(tp*dp_local) or {params['prefill_tp_size']} (single rank); verify manually"
        )
    if d_vis is not None and d_vis != d_node_need and d_vis != params["decode_tp_size"]:
        warnings.append(
            f"Decode ASCEND_RT_VISIBLE_DEVICES count={d_vis}, expected {d_node_need} "
            f"(tp*dp_local) or {params['decode_tp_size']} (single rank); verify manually"
        )
    # Path C QPS baseline: visible cards must equal min instance (DP×TP), not the whole node.
    if params.get("colocated_pd"):
        if p_vis is not None and p_vis != min_p:
            errors.append(
                f"colocated Prefill ASCEND_RT_VISIBLE_DEVICES count={p_vis} != min instance {min_p} "
                "(DP×TP); QPS test must not occupy leftover NPUs"
            )
        if d_vis is not None and d_vis != min_d:
            errors.append(
                f"colocated Decode ASCEND_RT_VISIBLE_DEVICES count={d_vis} != min instance {min_d} "
                "(DP×TP); QPS test must not occupy leftover NPUs"
            )

    # Proxy list lengths
    pref_h = params["proxy"]["prefiller_hosts"]
    pref_p = params["proxy"]["prefiller_ports"]
    dec_h = params["proxy"]["decoder_hosts"]
    dec_p = params["proxy"]["decoder_ports"]
    if len(pref_h) != len(pref_p):
        errors.append("prefiller hosts/ports length mismatch")
    if len(dec_h) != len(dec_p):
        errors.append("decoder hosts/ports length mismatch")
    expected_p = len(params.get("instances", []))  # rough
    n_p_nodes = sum(1 for i in params["instances"] if i["role"] == "prefill" for _ in i["nodes"])
    n_d_nodes = sum(1 for i in params["instances"] if i["role"] == "decode" for _ in i["nodes"])
    if len(pref_h) != n_p_nodes * params["prefill_dp_size_local"]:
        errors.append(
            f"prefiller list length {len(pref_h)} != nodes({n_p_nodes})*dp_local({params['prefill_dp_size_local']})"
        )
    if len(dec_h) != n_d_nodes * params["decode_dp_size_local"]:
        errors.append(
            f"decoder list length {len(dec_h)} != nodes({n_d_nodes})*dp_local({params['decode_dp_size_local']})"
        )

    # kv_port uniqueness / reserved
    ports = [i["kv_port"] for i in params["instances"]]
    if len(ports) != len(set(ports)):
        errors.append(f"duplicate kv_port values: {ports}")
    reserved_hi = 20000 + params["npu_per_node"] * 1000 - 1
    for kp in ports:
        if 20000 <= kp <= reserved_hi:
            errors.append(f"kv_port={kp} overlaps AscendDirectTransport reserved [20000,{reserved_hi}]")

    for w in params.get("warnings") or []:
        warnings.append(w)

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "keep_fields": list(KEEP_FIELDS),
        "replace_only_fields": list(REPLACE_ONLY),
        "kv_connectors": {"prefill": p_conn, "decode": d_conn},
        "proxy_counts": {
            "prefiller": len(pref_h),
            "decoder": len(dec_h),
            "prefill_nodes": n_p_nodes,
            "decode_nodes": n_d_nodes,
        },
        "expected_p_note": expected_p,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--params-json", default="")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    md = Path(args.config).read_text(encoding="utf-8")
    params = json.loads(Path(args.params_json).read_text(encoding="utf-8")) if args.params_json else None
    result = validate(md, params)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        Path(args.json).write_text(text, encoding="utf-8")
    print(text)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
