#!/usr/bin/env python3
"""Compute PD-disaggregation kv_port / engine_id / dp sizes and proxy host/port lists."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


KV_PORT_BASE = 36000
KV_PORT_STEP = 100
DEFAULT_VLLM_PORT = 7100


def npu_per_node(machine_type: str) -> int:
    mt = (machine_type or "").strip().upper().replace(" ", "")
    if "A3" in mt:
        return 16
    return 8


def _parse_hosts_table(md: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    in_table = False
    headers: list[str] = []
    for line in md.splitlines():
        if line.strip().startswith("|") and "host_ip" in line:
            headers = [c.strip() for c in line.strip().strip("|").split("|")]
            in_table = True
            continue
        if in_table:
            if not line.strip().startswith("|"):
                break
            if re.match(r"^\|\s*-+", line.strip()):
                continue
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cols) != len(headers):
                continue
            row = dict(zip(headers, cols))
            if row.get("host_ip"):
                rows.append(row)
    return rows


def _field(md: str, name: str, default: str = "") -> str:
    m = re.search(rf"-\s*{re.escape(name)}:\s*(.+)", md)
    return m.group(1).strip() if m else default


def _cmd_block(md: str, *titles: str) -> str:
    """Extract a fenced bash block under a ## heading."""
    for title in titles:
        m = re.search(
            rf"##\s*{re.escape(title)}\s*\n+```(?:bash)?\n(.*?)```",
            md,
            re.IGNORECASE | re.DOTALL,
        )
        if m:
            return m.group(1)
    return ""


def _extract_tp_sizes(md: str) -> tuple[int, int]:
    """Prefer explicit config fields; else parse from bash kv_transfer_config JSON snippets."""
    p_tp = _field(md, "prefill_tp_size") or _field(md, "Prefill TP")
    d_tp = _field(md, "decode_tp_size") or _field(md, "Decode TP")
    if p_tp and d_tp:
        return int(p_tp), int(d_tp)

    # Fallback: first "tp_size": N under prefill/decode blocks in file
    pref = re.search(
        r'"prefill"\s*:\s*\{[^}]*"tp_size"\s*:\s*(\d+)',
        md,
        re.IGNORECASE | re.DOTALL,
    )
    dec = re.search(
        r'"decode"\s*:\s*\{[^}]*"tp_size"\s*:\s*(\d+)',
        md,
        re.IGNORECASE | re.DOTALL,
    )
    prefill_tp = int(pref.group(1)) if pref else int(p_tp or "1")
    decode_tp = int(dec.group(1)) if dec else int(d_tp or "1")
    return prefill_tp, decode_tp


def _parse_int_flag(cmd: str, flag: str) -> int | None:
    m = re.search(rf"{re.escape(flag)}\s+(\d+)", cmd)
    return int(m.group(1)) if m else None


def _parse_json_int(cmd: str, key: str) -> int | None:
    m = re.search(rf'"{re.escape(key)}"\s*:\s*(\d+)', cmd)
    return int(m.group(1)) if m else None


def _parse_dp_from_cmd(cmd: str, role: str) -> int | None:
    """Prefer CLI --data-parallel-size (local), else kv_connector_extra_config.<role>.dp_size."""
    cli = _parse_int_flag(cmd, "--data-parallel-size")
    if cli is not None:
        return cli
    block = re.search(
        rf'"{role}"\s*:\s*\{{[^}}]*"dp_size"\s*:\s*(\d+)',
        cmd,
        re.IGNORECASE | re.DOTALL,
    )
    if block:
        return int(block.group(1))
    return None


def _parse_tp_from_cmd(cmd: str, role: str) -> int | None:
    """Prefer CLI --tensor-parallel-size, else kv_connector_extra_config.<role>.tp_size."""
    cli = _parse_int_flag(cmd, "--tensor-parallel-size")
    if cli is not None:
        return cli
    block = re.search(
        rf'"{role}"\s*:\s*\{{[^}}]*"tp_size"\s*:\s*(\d+)',
        cmd,
        re.IGNORECASE | re.DOTALL,
    )
    if block:
        return int(block.group(1))
    return None


def _parse_extra_dp_size(cmd: str, role: str) -> int | None:
    """Global dp_size from kv_connector_extra_config.<role>.dp_size only."""
    block = re.search(
        rf'"{role}"\s*:\s*\{{[^}}]*"dp_size"\s*:\s*(\d+)',
        cmd,
        re.IGNORECASE | re.DOTALL,
    )
    return int(block.group(1)) if block else None


def _visible_npu_count(cmd: str) -> int | None:
    m = re.search(r"ASCEND_RT_VISIBLE_DEVICES=([0-9,\s]+)", cmd)
    if not m:
        return None
    parts = [x.strip() for x in m.group(1).split(",") if x.strip()]
    return len(parts) if parts else None


def _row_npu_count(row: dict[str, str]) -> int | None:
    raw = (row.get("npu_count") or "").strip()
    if raw.isdigit():
        return int(raw)
    ids = (row.get("npu_ids") or "").strip()
    if ids:
        parts = [x.strip() for x in ids.split(",") if x.strip()]
        return len(parts) if parts else None
    return None


def _role_rows(hosts: list[dict[str, str]], roles: set[str]) -> list[dict[str, str]]:
    out = []
    for h in hosts:
        r = h.get("role", "").strip().upper()
        if r in roles:
            out.append(h)
    return out


def _group_instances(
    rows: list[dict[str, str]],
    instances: int,
    nodes_per_instance: int,
) -> list[list[dict[str, str]]]:
    """Group host rows into instances. If instance_id column present, use it; else chunk by nodes_per_instance."""
    if not rows:
        return [[] for _ in range(instances)]

    if any(r.get("instance_id") for r in rows):
        groups: dict[str, list[dict[str, str]]] = {}
        for r in rows:
            key = r.get("instance_id") or "0"
            groups.setdefault(key, []).append(r)
        ordered = [groups[k] for k in sorted(groups.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x))]
        while len(ordered) < instances:
            ordered.append([])
        return ordered[:instances]

    groups = []
    for i in range(instances):
        start = i * nodes_per_instance
        end = start + nodes_per_instance
        chunk = rows[start:end]
        groups.append(chunk)
    return groups


def expand_proxy_lists(
    nodes: list[dict[str, Any]],
    dp_size_local: int,
    vllm_start_port: int = DEFAULT_VLLM_PORT,
) -> tuple[list[str], list[int]]:
    """Each node IP × dp_size_local; ports start_port..start_port+dp_size_local-1 per node."""
    hosts: list[str] = []
    ports: list[int] = []
    for n in nodes:
        ip = n["host_ip"]
        base = int(n.get("vllm_port", vllm_start_port))
        for i in range(dp_size_local):
            hosts.append(ip)
            ports.append(base + i)
    return hosts, ports


def compute(md: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    overrides = overrides or {}
    machine_type = overrides.get("machine_type") or _field(md, "设备类型") or _field(md, "machine_type") or "A2"
    npu = npu_per_node(str(machine_type))

    prefill_instances = int(
        overrides.get("prefill_instances")
        or _field(md, "prefill_instances")
        or _field(md, "P实例数")
        or "1"
    )
    decode_instances = int(
        overrides.get("decode_instances")
        or _field(md, "decode_instances")
        or _field(md, "D实例数")
        or "1"
    )
    nodes_per_p = int(
        overrides.get("nodes_per_prefill_instance")
        or _field(md, "nodes_per_prefill_instance")
        or _field(md, "每P实例节点数")
        or "1"
    )
    nodes_per_d = int(
        overrides.get("nodes_per_decode_instance")
        or _field(md, "nodes_per_decode_instance")
        or _field(md, "每D实例节点数")
        or "1"
    )
    vllm_start_port = int(
        overrides.get("vllm_start_port") or _field(md, "vllm_start_port") or str(DEFAULT_VLLM_PORT)
    )
    proxy_type = (
        overrides.get("proxy_type")
        or _field(md, "proxy_type")
        or _field(md, "PROXY_TYPE")
        or "basic"
    )
    # basic | layerwise
    if "layer" in str(proxy_type).lower():
        proxy_script = "load_balance_proxy_layerwise_server_example.py"
        proxy_type_norm = "layerwise"
    else:
        proxy_script = "load_balance_proxy_server_example.py"
        proxy_type_norm = "basic"

    hosts = _parse_hosts_table(md)
    p_rows = _role_rows(hosts, {"P", "PREFILL", "PREFILLER"})
    d_rows = _role_rows(hosts, {"D", "DECODE", "DECODER"})
    proxy_rows = _role_rows(hosts, {"PROXY"})
    master_rows = _role_rows(hosts, {"MOONCAKE_MASTER", "MASTER", "MOONCAKE"})

    prefill_cmd = _cmd_block(md, "Prefill 拉起命令", "Prefill")
    decode_cmd = _cmd_block(md, "Decode 拉起命令", "Decode")

    prefill_tp, decode_tp = _extract_tp_sizes(md)
    p_tp_cmd = _parse_tp_from_cmd(prefill_cmd, "prefill")
    d_tp_cmd = _parse_tp_from_cmd(decode_cmd, "decode")
    if p_tp_cmd:
        prefill_tp = p_tp_cmd
    if d_tp_cmd:
        decode_tp = d_tp_cmd
    if "prefill_tp_size" in overrides:
        prefill_tp = int(overrides["prefill_tp_size"])
    if "decode_tp_size" in overrides:
        decode_tp = int(overrides["decode_tp_size"])

    if prefill_tp <= 0 or decode_tp <= 0:
        raise SystemExit("tp_size must be > 0")

    p_ips = {r["host_ip"] for r in p_rows}
    d_ips = {r["host_ip"] for r in d_rows}
    colocated = bool(p_ips & d_ips)

    def _dp_local(
        *,
        role: str,
        tp: int,
        rows: list[dict[str, str]],
        cmd: str,
    ) -> tuple[int, str]:
        """Return (dp_size_local, source). Prefer launch cmd; never inflate DP to fill the node."""
        from_cmd = _parse_dp_from_cmd(cmd, role)
        if from_cmd is not None and from_cmd > 0:
            return from_cmd, "launch_cmd"
        cards = None
        if rows:
            cards = _row_npu_count(rows[0])
        if cards is None:
            cards = _visible_npu_count(cmd)
        if cards is not None and cards > 0:
            if cards % tp != 0:
                raise SystemExit(f"{role}: npu_count={cards} not divisible by tp_size={tp}")
            # Colocated 1P1D: a row that claims the whole node would steal leftover cards.
            if colocated and cards == npu:
                return 1, "colocated_ignore_full_node_npu_count"
            return cards // tp, "role_npu_count/tp" if colocated or cards != npu else "npu_count/tp"
        # Path C QPS baseline: min instance = DP×TP from launch (or DP=1). Do not use npu/tp.
        return 1, "min_instance_fallback_dp_local=1"

    prefill_dp_local, prefill_dp_src = _dp_local(role="prefill", tp=prefill_tp, rows=p_rows, cmd=prefill_cmd)
    decode_dp_local, decode_dp_src = _dp_local(role="decode", tp=decode_tp, rows=d_rows, cmd=decode_cmd)

    # Global dp_size in kv_connector_extra_config: prefer explicit JSON in cmds when present
    prefill_dp_size = _parse_extra_dp_size(prefill_cmd, "prefill")
    decode_dp_size = _parse_extra_dp_size(decode_cmd, "decode")
    if prefill_dp_size is None:
        prefill_dp_size = prefill_instances * nodes_per_p * prefill_dp_local
    if decode_dp_size is None:
        decode_dp_size = decode_instances * nodes_per_d * decode_dp_local

    user_p_port = _parse_int_flag(prefill_cmd, "--port")
    user_d_port = _parse_int_flag(decode_cmd, "--port")
    user_p_kv = _parse_json_int(prefill_cmd, "kv_port")
    user_d_kv = _parse_json_int(decode_cmd, "kv_port")
    user_p_engine = _parse_json_int(prefill_cmd, "engine_id")
    user_d_engine = _parse_json_int(decode_cmd, "engine_id")

    skip_master_raw = (
        overrides.get("skip_mooncake_master")
        or _field(md, "skip_mooncake_master")
        or "false"
    )
    skip_mooncake_master = str(skip_master_raw).strip().lower() in ("1", "true", "yes", "y")
    mooncake_port = int(
        overrides.get("mooncake_master_port")
        or _field(md, "mooncake_master_port")
        or "50088"
    )
    mooncake_host = (
        overrides.get("mooncake_master_host")
        or _field(md, "mooncake_master_host")
        or (master_rows[0]["host_ip"] if master_rows else "")
        or (proxy_rows[0]["host_ip"] if proxy_rows else "")
        or (p_rows[0]["host_ip"] if p_rows else "127.0.0.1")
    )
    mooncake_container = ""
    if master_rows:
        mooncake_container = master_rows[0].get("container_name", "")
    elif proxy_rows:
        mooncake_container = proxy_rows[0].get("container_name", "")
    elif p_rows:
        mooncake_container = p_rows[0].get("container_name", "")

    global_segment = _field(md, "mooncake_global_segment_size") or "1GB"
    protocol = _field(md, "mooncake_protocol") or "ascend"
    metadata_server = _field(md, "mooncake_metadata_server") or "P2PHANDSHAKE"
    require_master = str(_field(md, "require_mooncake_master") or "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "n",
    )

    p_groups = _group_instances(p_rows, prefill_instances, nodes_per_p)
    d_groups = _group_instances(d_rows, decode_instances, nodes_per_d)

    prefill_nodes_flat: list[dict[str, Any]] = []
    decode_nodes_flat: list[dict[str, Any]] = []
    instances: list[dict[str, Any]] = []

    for inst_idx, nodes in enumerate(p_groups):
        kv_port = (
            user_p_kv
            if user_p_kv is not None and prefill_instances == 1
            else KV_PORT_BASE + inst_idx * KV_PORT_STEP
        )
        engine_id = (
            user_p_engine
            if user_p_engine is not None and prefill_instances == 1
            else inst_idx + 1
        )
        node_infos = []
        for node_i, row in enumerate(nodes):
            # node_index_in_instance starts at 1
            dp_rank_start = node_i * prefill_dp_local
            p_port = user_p_port if user_p_port is not None else vllm_start_port
            info = {
                "role": "prefill",
                "instance_index": inst_idx,
                "node_index_in_instance": node_i + 1,
                "host_ip": row["host_ip"],
                "container_name": row.get("container_name", ""),
                "npu_ids": (row.get("npu_ids") or "").strip(),
                "kv_port": kv_port,
                "engine_id": engine_id,
                "dp_rank_start": dp_rank_start,
                "vllm_port": p_port,
            }
            node_infos.append(info)
            prefill_nodes_flat.append(info)
        instances.append(
            {
                "role": "prefill",
                "instance_index": inst_idx,
                "kv_port": kv_port,
                "engine_id": engine_id,
                "nodes": node_infos,
            }
        )

    for inst_idx, nodes in enumerate(d_groups):
        kv_port = (
            user_d_kv
            if user_d_kv is not None and decode_instances == 1
            else KV_PORT_BASE + prefill_instances * KV_PORT_STEP + inst_idx * KV_PORT_STEP
        )
        engine_id = (
            user_d_engine
            if user_d_engine is not None and decode_instances == 1
            else prefill_instances + inst_idx + 1
        )
        node_infos = []
        for node_i, row in enumerate(nodes):
            dp_rank_start = node_i * decode_dp_local
            d_port = user_d_port if user_d_port is not None else vllm_start_port
            info = {
                "role": "decode",
                "instance_index": inst_idx,
                "node_index_in_instance": node_i + 1,
                "host_ip": row["host_ip"],
                "container_name": row.get("container_name", ""),
                "npu_ids": (row.get("npu_ids") or "").strip(),
                "kv_port": kv_port,
                "engine_id": engine_id,
                "dp_rank_start": dp_rank_start,
                "vllm_port": d_port,
            }
            node_infos.append(info)
            decode_nodes_flat.append(info)
        instances.append(
            {
                "role": "decode",
                "instance_index": inst_idx,
                "kv_port": kv_port,
                "engine_id": engine_id,
                "nodes": node_infos,
            }
        )

    # Proxy backends: on colocated single-host, prefer loopback if user launch uses 127.0.0.1
    prefer_loopback = colocated and (
        'LOCAL_IP="127.0.0.1"' in prefill_cmd
        or "LOCAL_IP='127.0.0.1'" in prefill_cmd
        or "HCCL_IF_IP=127.0.0.1" in prefill_cmd
        or 'NIC_NAME="lo"' in prefill_cmd
    )

    def _proxy_expand(nodes: list[dict[str, Any]], dp_local: int, default_port: int) -> tuple[list[str], list[int]]:
        hosts_out: list[str] = []
        ports_out: list[int] = []
        for n in nodes:
            ip = "127.0.0.1" if prefer_loopback else n["host_ip"]
            base = int(n.get("vllm_port", default_port))
            for i in range(dp_local):
                hosts_out.append(ip)
                ports_out.append(base + i)
        return hosts_out, ports_out

    pref_hosts, pref_ports = _proxy_expand(
        prefill_nodes_flat, prefill_dp_local, user_p_port or vllm_start_port
    )
    dec_hosts, dec_ports = _proxy_expand(
        decode_nodes_flat, decode_dp_local, user_d_port or vllm_start_port
    )
    proxy_host = proxy_rows[0]["host_ip"] if proxy_rows else (prefill_nodes_flat[0]["host_ip"] if prefill_nodes_flat else "0.0.0.0")

    # Validate kv_port ranges
    reserved_hi = 20000 + npu * 1000 - 1
    warnings: list[str] = []
    for inst in instances:
        kp = inst["kv_port"]
        if kp < 28000 or (npu == 16 and kp < 36000):
            warnings.append(f"kv_port={kp} may collide with AscendDirectTransport reserved range ending {reserved_hi}")
        if 20000 <= kp <= reserved_hi:
            warnings.append(f"kv_port={kp} overlaps reserved [{20000}, {reserved_hi}]")

    min_p_instance_npus = prefill_dp_local * prefill_tp
    min_d_instance_npus = decode_dp_local * decode_tp
    n_hosts = len({r["host_ip"] for r in hosts if r.get("host_ip")})
    host_avail_npus = max(n_hosts, 1) * npu

    def _suggest_ids(start: int, count: int) -> str:
        return ",".join(str(i) for i in range(start, start + count))

    suggested_p_npu_ids = _suggest_ids(0, min_p_instance_npus)
    suggested_d_npu_ids = _suggest_ids(min_p_instance_npus, min_d_instance_npus)
    leftover_start = min_p_instance_npus + min_d_instance_npus
    leftover_npu_ids = _suggest_ids(leftover_start, max(0, npu - leftover_start)) if leftover_start < npu else ""

    p_assigned = _row_npu_count(p_rows[0]) if p_rows else _visible_npu_count(prefill_cmd)
    d_assigned = _row_npu_count(d_rows[0]) if d_rows else _visible_npu_count(decode_cmd)
    if p_assigned is not None and p_assigned != min_p_instance_npus:
        warnings.append(
            f"Prefill assigned npu_count={p_assigned} != min instance DP×TP={min_p_instance_npus}; "
            "Path C QPS baseline must use exactly min P cards; leftover NPUs stay unused"
        )
    if d_assigned is not None and d_assigned != min_d_instance_npus:
        warnings.append(
            f"Decode assigned npu_count={d_assigned} != min instance DP×TP={min_d_instance_npus}; "
            "Path C QPS baseline must use exactly min D cards; leftover NPUs stay unused"
        )
    if leftover_npu_ids:
        warnings.append(
            f"baseline uses P[{suggested_p_npu_ids}] + D[{suggested_d_npu_ids}]; "
            f"leftover NPUs {leftover_npu_ids} unused until Phase 4 capacity fit "
            f"(avail_npus={host_avail_npus})"
        )

    if colocated:
        warnings.append(
            "colocated P+D on same host_ip: dp_size_local derived from launch_cmd/npu_count "
            f"(prefill={prefill_dp_src}, decode={decode_dp_src}); not npu_per_node/tp"
        )

    return {
        "machine_type": machine_type,
        "npu_per_node": npu,
        "host_avail_npus": host_avail_npus,
        "min_p_instance_npus": min_p_instance_npus,
        "min_d_instance_npus": min_d_instance_npus,
        "baseline_npus_in_use": min_p_instance_npus + min_d_instance_npus,
        "suggested_p_npu_ids": suggested_p_npu_ids,
        "suggested_d_npu_ids": suggested_d_npu_ids,
        "leftover_npu_ids": leftover_npu_ids,
        "colocated_pd": colocated,
        "prefill_instances": prefill_instances,
        "decode_instances": decode_instances,
        "nodes_per_prefill_instance": nodes_per_p,
        "nodes_per_decode_instance": nodes_per_d,
        "prefill_tp_size": prefill_tp,
        "decode_tp_size": decode_tp,
        "prefill_dp_size_local": prefill_dp_local,
        "decode_dp_size_local": decode_dp_local,
        "prefill_dp_size_local_source": prefill_dp_src,
        "decode_dp_size_local_source": decode_dp_src,
        "prefill_dp_size": prefill_dp_size,
        "decode_dp_size": decode_dp_size,
        "kv_port_base": KV_PORT_BASE,
        "kv_port_step": KV_PORT_STEP,
        "vllm_start_port": vllm_start_port,
        "proxy_type": proxy_type_norm,
        "proxy_script": proxy_script,
        "proxy_listen_host": proxy_host,
        "proxy_listen_port": int(_field(md, "proxy_port") or "1999"),
        "instances": instances,
        "proxy": {
            "prefiller_hosts": pref_hosts,
            "prefiller_ports": pref_ports,
            "decoder_hosts": dec_hosts,
            "decoder_ports": dec_ports,
        },
        "mooncake_master": {
            "required": require_master and not skip_mooncake_master,
            "skip": skip_mooncake_master,
            "host_ip": mooncake_host,
            "container_name": mooncake_container,
            "port": mooncake_port,
            "master_server_address": f"{mooncake_host}:{mooncake_port}",
            "protocol": protocol,
            "metadata_server": metadata_server,
            "global_segment_size": global_segment,
            "start_order": 0,
            "note": "Must start mooncake_master BEFORE Prefill/Decode when required=true",
        },
        "kv_transfer_replace_fields": [
            "kv_port",
            "engine_id",
            "kv_connector_extra_config.prefill.dp_size",
            "kv_connector_extra_config.decode.dp_size",
        ],
        "kv_connector_policy": "keep_template_value_no_rename",
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True, help="pd-deploy-config.md")
    ap.add_argument("--json", default="", help="write result JSON")
    ap.add_argument("--machine-type", default="")
    ap.add_argument("--prefill-instances", type=int, default=0)
    ap.add_argument("--decode-instances", type=int, default=0)
    ap.add_argument("--prefill-tp-size", type=int, default=0)
    ap.add_argument("--decode-tp-size", type=int, default=0)
    ap.add_argument("--nodes-per-prefill-instance", type=int, default=0)
    ap.add_argument("--nodes-per-decode-instance", type=int, default=0)
    ap.add_argument("--proxy-type", default="")
    ap.add_argument("--vllm-start-port", type=int, default=0)
    args = ap.parse_args()

    md = Path(args.config).read_text(encoding="utf-8")
    ov: dict[str, Any] = {}
    if args.machine_type:
        ov["machine_type"] = args.machine_type
    if args.prefill_instances:
        ov["prefill_instances"] = args.prefill_instances
    if args.decode_instances:
        ov["decode_instances"] = args.decode_instances
    if args.prefill_tp_size:
        ov["prefill_tp_size"] = args.prefill_tp_size
    if args.decode_tp_size:
        ov["decode_tp_size"] = args.decode_tp_size
    if args.nodes_per_prefill_instance:
        ov["nodes_per_prefill_instance"] = args.nodes_per_prefill_instance
    if args.nodes_per_decode_instance:
        ov["nodes_per_decode_instance"] = args.nodes_per_decode_instance
    if args.proxy_type:
        ov["proxy_type"] = args.proxy_type
    if args.vllm_start_port:
        ov["vllm_start_port"] = args.vllm_start_port

    result = compute(md, ov)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        Path(args.json).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
