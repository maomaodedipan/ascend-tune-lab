#!/usr/bin/env python3
"""Fetch real vllm-ascend PD proxy scripts into rendered/proxy/."""

from __future__ import annotations

import argparse
import json
import shutil
import urllib.request
from pathlib import Path

PROXY_FILES = (
    "load_balance_proxy_server_example.py",
    "load_balance_proxy_layerwise_server_example.py",
)

DEFAULT_RAW_BASE = (
    "https://raw.githubusercontent.com/vllm-project/vllm-ascend/main/"
    "examples/disaggregated_prefill_v1"
)


def _copy_local(src_dir: Path, out_dir: Path) -> dict:
    copied = []
    missing = []
    for name in PROXY_FILES:
        src = src_dir / name
        if not src.is_file():
            missing.append(str(src))
            continue
        dst = out_dir / name
        shutil.copy2(src, dst)
        copied.append(str(dst))
    return {"mode": "local_copy", "copied": copied, "missing": missing, "ok": not missing}


def _download(raw_base: str, out_dir: Path, timeout: float = 60.0) -> dict:
    copied = []
    errors = []
    for name in PROXY_FILES:
        url = f"{raw_base.rstrip('/')}/{name}"
        dst = out_dir / name
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                data = resp.read()
            if len(data) < 1000:
                errors.append(f"{name}: downloaded content too small ({len(data)} bytes)")
                continue
            dst.write_bytes(data)
            copied.append(str(dst))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")
    return {
        "mode": "github_raw",
        "raw_base": raw_base,
        "copied": copied,
        "errors": errors,
        "ok": len(copied) == len(PROXY_FILES),
    }


def fetch(out_dir: Path, local_dir: str = "", raw_base: str = DEFAULT_RAW_BASE) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    if local_dir:
        result = _copy_local(Path(local_dir), out_dir)
        if result["ok"]:
            return result
        # fall through to download if local incomplete
        local_result = result
    else:
        local_result = None

    dl = _download(raw_base, out_dir)
    if local_result:
        dl["local_attempt"] = local_result
    return dl


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", required=True, help="rendered/proxy directory")
    ap.add_argument(
        "--local-dir",
        default="",
        help="optional local vllm-ascend/.../disaggregated_prefill_v1 directory",
    )
    ap.add_argument("--raw-base", default=DEFAULT_RAW_BASE)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    result = fetch(Path(args.out_dir), local_dir=args.local_dir, raw_base=args.raw_base)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        Path(args.json).write_text(text, encoding="utf-8")
    print(text)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
