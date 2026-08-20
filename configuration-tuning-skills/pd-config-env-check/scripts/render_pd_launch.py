#!/usr/bin/env python3
"""Render PD Prefill/Decode/Proxy launch scripts.

Allowed auto-rewrites:
  - network: HCCL_IF_IP / socket ifnames / literal baseline host IP
  - PD computed: kv_port, engine_id, kv_connector_extra_config.*.dp_size
  - if missing: ASCEND_RT_VISIBLE_DEVICES = min-instance npu_ids (do not fill the node)
Never rename kv_connector; never change tp_size / kv_role / model path / etc.
"""

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
from fetch_proxy_scripts import fetch as fetch_proxy_scripts  # noqa: E402

IP_PATTERN = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b"
)

PROXY_BASIC = "load_balance_proxy_server_example.py"
PROXY_LAYERWISE = "load_balance_proxy_layerwise_server_example.py"


def _ensure_visible_devices(cmd: str, npu_ids: str) -> tuple[str, list[dict[str, Any]]]:
    """If launch cmd has no VISIBLE_DEVICES, pin to min-instance cards (leftover NPUs unused)."""
    if not (npu_ids or "").strip():
        return cmd, []
    if re.search(r"ASCEND_RT_VISIBLE_DEVICES=", cmd):
        return cmd, []
    ids = npu_ids.strip()
    export_line = f'export ASCEND_RT_VISIBLE_DEVICES="{ids}"\n'
    return export_line + cmd, [
        {
            "field": "ASCEND_RT_VISIBLE_DEVICES",
            "from": "(missing)",
            "to": ids,
            "reason": "min_instance_baseline",
        }
    ]


def _extract_bash_blocks(md: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current = None
    buf: list[str] = []
    in_bash = False
    for line in md.splitlines():
        if line.startswith("## "):
            if current and in_bash is False and current not in sections and buf:
                pass
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
            buf = []
            continue
        if in_bash:
            buf.append(line)
    return sections


def _rewrite_network(cmd: str, host_ip: str, ifname: str | None, base_ip: str | None) -> tuple[str, list[dict[str, str]]]:
    changes: list[dict[str, str]] = []
    out = cmd

    # User-validated single-node / colocated: keep loopback + lo; do not force host_ip
    loopback = bool(
        re.search(r'LOCAL_IP=["\']?127\.0\.0\.1', out)
        or re.search(r'HCCL_IF_IP=["\']?127\.0\.0\.1', out)
        or re.search(r'NIC_NAME=["\']?lo["\']?', out)
    )
    if loopback:
        changes.append(
            {
                "field": "network",
                "old": "loopback",
                "new": "preserved",
                "reason": "preserve LOCAL_IP=127.0.0.1 / NIC=lo (colocated or single-node validated)",
            }
        )
        return out, changes

    def replace_env(key: str, new_val: str) -> None:
        nonlocal out
        pat = re.compile(rf"(export\s+{key}=)([^\s\\]+)")
        m = pat.search(out)
        if m and m.group(2).strip("\"'") != new_val:
            changes.append({"field": key, "old": m.group(2), "new": new_val, "reason": "multi-host network rewrite"})
            out = pat.sub(rf"\g<1>{new_val}", out, count=1)
        elif f"export {key}=" not in out and key == "HCCL_IF_IP":
            out = f"export {key}={new_val}\n" + out
            changes.append({"field": key, "old": "", "new": new_val, "reason": "inject HCCL_IF_IP for host"})

    replace_env("HCCL_IF_IP", host_ip)
    if ifname:
        for k in ("GLOO_SOCKET_IFNAME", "TP_SOCKET_IFNAME", "HCCL_SOCKET_IFNAME"):
            replace_env(k, ifname)

    if base_ip and base_ip != host_ip:

        def _ip_sub(m: re.Match[str]) -> str:
            old = m.group(0)
            if old == base_ip:
                changes.append({"field": "literal_ip", "old": old, "new": host_ip, "reason": "replace baseline host IP"})
                return host_ip
            return old

        out = IP_PATTERN.sub(_ip_sub, out)
    return out, changes


def _patch_kv_transfer_config(
    cmd: str,
    *,
    kv_port: int,
    engine_id: int,
    prefill_dp_size: int,
    decode_dp_size: int,
    dp_rank_start: int | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Replace only allowed kv_transfer_config fields; keep kv_connector / tp_size / kv_role."""
    changes: list[dict[str, str]] = []
    out = cmd

    def sub_json_field(field: str, new_val: str | int, reason: str) -> None:
        nonlocal out
        # "field": "value" or "field": value
        pat = re.compile(rf'("{field}"\s*:\s*)(?:"[^"]*"|\d+)')
        m = pat.search(out)
        if not m:
            return
        old = m.group(0)
        if isinstance(new_val, int) or (isinstance(new_val, str) and new_val.isdigit()):
            repl = f'{m.group(1)}{int(new_val) if not isinstance(new_val, int) else new_val}'
            # engine_id / kv_port often quoted in tutorials
            if field in ("kv_port", "engine_id") and '"' in old.split(":", 1)[-1]:
                repl = f'{m.group(1)}"{new_val}"'
        else:
            repl = f'{m.group(1)}"{new_val}"'
        if old != repl:
            changes.append({"field": field, "old": old, "new": repl, "reason": reason})
            out = pat.sub(repl, out, count=1)

    sub_json_field("kv_port", kv_port, "computed kv_port")
    sub_json_field("engine_id", engine_id, "computed engine_id")

    # dp_size under prefill / decode blocks — replace both occurrences carefully
    def sub_dp_in_block(block: str, dp_size: int) -> None:
        nonlocal out
        block_pat = re.compile(
            rf'("{block}"\s*:\s*\{{)(.*?)(\}})',
            re.DOTALL | re.IGNORECASE,
        )

        def _repl(m: re.Match[str]) -> str:
            body = m.group(2)
            dp_pat = re.compile(r'("dp_size"\s*:\s*)(\d+)')
            dm = dp_pat.search(body)
            if not dm:
                return m.group(0)
            old_v = dm.group(2)
            if int(old_v) == dp_size:
                return m.group(0)
            changes.append(
                {
                    "field": f"kv_connector_extra_config.{block}.dp_size",
                    "old": old_v,
                    "new": str(dp_size),
                    "reason": "computed dp_size",
                }
            )
            new_body = dp_pat.sub(rf"\g<1>{dp_size}", body, count=1)
            return m.group(1) + new_body + m.group(3)

        out = block_pat.sub(_repl, out, count=1)

    sub_dp_in_block("prefill", prefill_dp_size)
    sub_dp_in_block("decode", decode_dp_size)

    if dp_rank_start is not None:
        # Optional CLI flags commonly used with DP
        for flag in ("--data-parallel-rank-start", "--data-parallel-start-rank"):
            pat = re.compile(rf"({re.escape(flag)}\s+)(\d+)")
            m = pat.search(out)
            if m and int(m.group(2)) != dp_rank_start:
                changes.append(
                    {
                        "field": flag,
                        "old": m.group(2),
                        "new": str(dp_rank_start),
                        "reason": "instance-local dp_rank_start",
                    }
                )
                out = pat.sub(rf"\g<1>{dp_rank_start}", out, count=1)

    # Guard: never rewrite kv_connector value — detect accidental patterns (no-op check)
    return out, changes


def _gen_start_proxy_sh(params: dict[str, Any], user_proxy_cmd: str) -> str:
    proxy = params["proxy"]
    ph = " ".join(proxy["prefiller_hosts"])
    pp = " ".join(str(p) for p in proxy["prefiller_ports"])
    dh = " ".join(proxy["decoder_hosts"])
    dp = " ".join(str(p) for p in proxy["decoder_ports"])
    listen_host = params["proxy_listen_host"]
    listen_port = params["proxy_listen_port"]
    default_type = params["proxy_type"]

    if user_proxy_cmd.strip():
        body = user_proxy_cmd.strip()
        note = "# User-provided proxy command (network-rewritten if needed).\n"
    else:
        note = (
            "# Auto-generated proxy. Both example scripts are placed in this directory.\n"
            "# Set PROXY_TYPE=basic|layerwise per tutorial — do NOT guess from connector name.\n"
        )
        body = "\n".join(
            [
                f'SCRIPT="{PROXY_BASIC}"',
                'if [ "$PROXY_TYPE" = "layerwise" ]; then',
                f'  SCRIPT="{PROXY_LAYERWISE}"',
                "fi",
                'python "$SCRIPT" \\',
                f"  --host {listen_host} \\",
                f"  --port {listen_port} \\",
                f"  --prefiller-hosts {ph} \\",
                f"  --prefiller-ports {pp} \\",
                f"  --decoder-hosts {dh} \\",
                f"  --decoder-ports {dp}",
            ]
        )

    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"PROXY_TYPE=\"${{PROXY_TYPE:-{default_type}}}\"\n"
        f"{note}"
        f"{body}\n"
    )


def _write_mooncake_master(out_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Render mooncake master start script + mooncake.json (must start before P/D)."""
    mm = params.get("mooncake_master") or {}
    moon_dir = out_root / "mooncake"
    moon_dir.mkdir(parents=True, exist_ok=True)

    cfg = {
        "metadata_server": mm.get("metadata_server") or "P2PHANDSHAKE",
        "protocol": mm.get("protocol") or "ascend",
        "device_name": "",
        "master_server_address": mm.get("master_server_address"),
        "global_segment_size": mm.get("global_segment_size") or "1GB",
    }
    cfg_path = moon_dir / "mooncake.json"
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    port = int(mm.get("port") or 50088)
    host = mm.get("host_ip") or "127.0.0.1"
    start_path = moon_dir / "start_mooncake_master.sh"
    start_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f"# Mooncake master MUST be up before Prefill/Decode (host={host}).",
                'export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-/usr/local/lib:$LD_LIBRARY_PATH}"',
                'if ! command -v mooncake_master >/dev/null 2>&1; then',
                '  echo "mooncake_master not found in PATH. Install Mooncake or fix PATH." >&2',
                "  exit 1",
                "fi",
                f'echo "Starting mooncake_master on port {port} (master_server_address={cfg["master_server_address"]})"',
                "mooncake_master \\",
                f"  --port {port} \\",
                "  --eviction_high_watermark_ratio 0.9 \\",
                "  --eviction_ratio 0.1 \\",
                "  --default_kv_lease_ttl 11000",
                "",
            ]
        ),
        encoding="utf-8",
    )

    readme = moon_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Mooncake master",
                "",
                "Deploy order: **mooncake_master → Prefill → Decode → Proxy**.",
                "",
                f"- Config: `mooncake.json` → `master_server_address={cfg['master_server_address']}`",
                "- Start: `bash start_mooncake_master.sh`",
                "- Ensure each node/container that needs store can read the same `mooncake.json`",
                "  (or set `MOONCAKE_CONFIG_PATH` to this file).",
                "- If master already runs cluster-wide, set `skip_mooncake_master: true` in config.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "dir": str(moon_dir),
        "config": str(cfg_path),
        "start_script": str(start_path),
        "required": bool(mm.get("required")),
        "skip": bool(mm.get("skip")),
        "host_ip": host,
        "port": port,
        "container_name": mm.get("container_name") or "",
    }


def _proxy_readme() -> str:
    return (
        "# Proxy scripts\n\n"
        f"- `{PROXY_BASIC}` — MooncakeConnector 系常见（P→D 推送）\n"
        f"- `{PROXY_LAYERWISE}` — Layerwise 系常见（D→P 拉取）\n\n"
        "MooncakeConnectorV1 / MooncakeHybridConnector 以教程或用户 `proxy_type` 为准，"
        "禁止凭 connector 名猜 proxy。\n"
        "部署：`PROXY_TYPE=basic|layerwise bash start_proxy.sh`\n"
        "脚本应由 `fetch_proxy_scripts.py` 从 vllm-ascend 拉取真实文件（勿用手写空壳）。\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--json", default="")
    ap.add_argument("--ifname", default="")
    ap.add_argument("--params-json", default="", help="optional precomputed compute_pd_params JSON")
    ap.add_argument(
        "--proxy-local-dir",
        default="",
        help="optional local disaggregated_prefill_v1 dir for real proxy scripts",
    )
    ap.add_argument("--skip-proxy-fetch", action="store_true", help="do not download/copy proxy scripts")
    args = ap.parse_args()

    md = Path(args.config).read_text(encoding="utf-8")
    blocks = _extract_bash_blocks(md)
    prefill_cmd = blocks.get("Prefill 拉起命令", "") or blocks.get("Prefill", "")
    decode_cmd = blocks.get("Decode 拉起命令", "") or blocks.get("Decode", "")
    proxy_cmd = blocks.get("Proxy", "")

    if not prefill_cmd.strip():
        raise SystemExit("missing Prefill launch command in config")
    if not decode_cmd.strip():
        raise SystemExit("missing Decode launch command in config")

    if args.params_json:
        params = json.loads(Path(args.params_json).read_text(encoding="utf-8"))
    else:
        params = compute(md)

    ifname = args.ifname
    m = re.search(r"网卡名:\s*(\S+)", md)
    if m and not ifname:
        ifname = m.group(1)

    out_root = Path(args.out_dir)
    for sub in ("prefill", "decode", "proxy", "mooncake"):
        (out_root / sub).mkdir(parents=True, exist_ok=True)

    mooncake_meta = _write_mooncake_master(out_root, params)

    all_changes: list[dict[str, Any]] = []
    base_p_ip = None
    base_d_ip = None
    for inst in params["instances"]:
        if inst["role"] == "prefill" and inst["nodes"] and base_p_ip is None:
            base_p_ip = inst["nodes"][0]["host_ip"]
        if inst["role"] == "decode" and inst["nodes"] and base_d_ip is None:
            base_d_ip = inst["nodes"][0]["host_ip"]

    prefill_dp = params["prefill_dp_size"]
    decode_dp = params["decode_dp_size"]

    for inst in params["instances"]:
        role = inst["role"]
        template = prefill_cmd if role == "prefill" else decode_cmd
        base_ip = base_p_ip if role == "prefill" else base_d_ip
        for node in inst["nodes"]:
            cmd, net_changes = _rewrite_network(template, node["host_ip"], ifname or None, base_ip)
            cmd, kv_changes = _patch_kv_transfer_config(
                cmd,
                kv_port=inst["kv_port"],
                engine_id=inst["engine_id"],
                prefill_dp_size=prefill_dp,
                decode_dp_size=decode_dp,
                dp_rank_start=node["dp_rank_start"],
            )
            vis_ids = (node.get("npu_ids") or "").strip() or (
                params.get("suggested_p_npu_ids")
                if role == "prefill"
                else params.get("suggested_d_npu_ids")
            )
            cmd, vis_changes = _ensure_visible_devices(cmd, str(vis_ids or ""))
            prefix = "p" if role == "prefill" else "d"
            fname = (
                f"start_{prefix}_i{inst['instance_index']}_n{node['node_index_in_instance']}_"
                f"{node['host_ip'].replace('.', '_')}.sh"
            )
            path = out_root / ("prefill" if role == "prefill" else "decode") / fname
            path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + cmd + "\n", encoding="utf-8")
            for c in net_changes + kv_changes + vis_changes:
                c.update(
                    {
                        "file": str(path),
                        "instance": f"{role[0].upper()}{inst['instance_index']}",
                        "host_ip": node["host_ip"],
                    }
                )
            all_changes.extend(net_changes + kv_changes + vis_changes)

    # Proxy: fetch real upstream scripts (preferred) then write start_proxy.sh
    proxy_fetch_meta: dict[str, Any]
    if args.skip_proxy_fetch:
        proxy_fetch_meta = {"ok": False, "skipped": True, "note": "skip-proxy-fetch set"}
        (out_root / "proxy" / PROXY_BASIC).write_text(
            f"# Placeholder. Run fetch_proxy_scripts.py to replace with real {PROXY_BASIC}\n",
            encoding="utf-8",
        )
        (out_root / "proxy" / PROXY_LAYERWISE).write_text(
            f"# Placeholder. Run fetch_proxy_scripts.py to replace with real {PROXY_LAYERWISE}\n",
            encoding="utf-8",
        )
    else:
        local_dir = args.proxy_local_dir
        if not local_dir:
            # common workdir layout
            for cand in (
                Path("vllm-ascend/examples/disaggregated_prefill_v1"),
                Path("repos/vllm-ascend/examples/disaggregated_prefill_v1"),
            ):
                if (cand / PROXY_BASIC).is_file():
                    local_dir = str(cand.resolve())
                    break
        proxy_fetch_meta = fetch_proxy_scripts(out_root / "proxy", local_dir=local_dir)

    (out_root / "proxy" / "README.md").write_text(_proxy_readme(), encoding="utf-8")

    final_proxy_user = ""
    if proxy_cmd.strip():
        listen_host = params["proxy_listen_host"]
        final_proxy_user, pchanges = _rewrite_network(proxy_cmd, listen_host, ifname or None, None)
        for c in pchanges:
            c.update({"file": "proxy/start_proxy.sh", "instance": "proxy", "host_ip": listen_host})
        all_changes.extend(pchanges)
    else:
        all_changes.append(
            {
                "file": "proxy/start_proxy.sh",
                "instance": "proxy",
                "field": "proxy_command",
                "old": "",
                "new": "auto_generated_with_PROXY_TYPE",
                "reason": "proxy section empty; hosts/ports expanded by dp_size_local",
                "host_ip": params["proxy_listen_host"],
            }
        )

    proxy_path = out_root / "proxy" / "start_proxy.sh"
    proxy_path.write_text(_gen_start_proxy_sh(params, final_proxy_user), encoding="utf-8")

    meta = {
        "params": params,
        "network_and_kv_changes": all_changes,
        "out_dir": str(out_root),
        "mooncake_master": mooncake_meta,
        "proxy_fetch": proxy_fetch_meta,
        "deploy_order": [
            "mooncake_master" if mooncake_meta.get("required") else "mooncake_master_skipped",
            "prefill",
            "decode",
            "proxy",
        ],
        "proxy": {
            "host": params["proxy_listen_host"],
            "port": params["proxy_listen_port"],
            "proxy_type": params["proxy_type"],
            "script": str(proxy_path),
            "scripts_bundled": [PROXY_BASIC, PROXY_LAYERWISE],
            "scripts_ready": bool(proxy_fetch_meta.get("ok")),
        },
    }
    if args.json:
        Path(args.json).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
