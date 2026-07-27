#!/usr/bin/env python3
"""Fetch high-throughput vLLM-Ascend baseline configs from official model tutorials.

Fallback when local baseline-docs/ has no 5-field match.

Docs index:
  https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models/

Example:
  python3 fetch_docs_baseline.py --config workspace/config.md --json
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

DOCS_BASE = "https://docs.vllm.ai/projects/vllm-ascend-cn/zh-cn/latest/tutorials/models"
DOCS_INDEX = f"{DOCS_BASE}/"
_USER_AGENT = "ascend-tune-lab/fetch_docs_baseline"
_SKILL_ROOT = Path(__file__).resolve().parents[1]
_ALIAS_PATH = _SKILL_ROOT / "references" / "docs_model_page_aliases.json"
_CACHE_DIR = _SKILL_ROOT / ".cache" / "docs"

# Curated aliases: user model_name → docs page stem (without .html)
_BUILTIN_ALIASES: dict[str, str] = {
    "glm5": "GLM5",
    "glm-5": "GLM5",
    "glm_5": "GLM5",
    "glm-5.1": "GLM5",
    "glm5.1": "GLM5",
    "glm-5.2": "GLM5.2",
    "glm5.2": "GLM5.2",
    "qwen3.5-27b": "Qwen3.5-27B-Qwen3.6-27B",
    "qwen3.6-27b": "Qwen3.5-27B-Qwen3.6-27B",
    "qwen3.5-397b": "Qwen3.5-397B-A17B",
    "qwen3.5-397b-a17b": "Qwen3.5-397B-A17B",
    "minimax-m2": "MiniMax-M2",
    "minimax-m2.5": "MiniMax-M2",
    "deepseek-v3.2": "DeepSeek-V3.2",
    "deepseek-v3.1": "DeepSeek-V3.1",
}


@dataclass
class ServeCandidate:
    bash: str
    heading_path: str
    context: str
    source_url: str
    device_hint: str | None = None
    quant_hint: str | None = None
    machines_hint: int | None = None
    dies_hint: int | None = None
    tp: int | None = None
    dp: int | None = None
    max_model_len: int | None = None
    max_num_seqs: int | None = None
    model_path: str | None = None
    enable_expert_parallel: bool = False
    is_pd: bool = False
    is_multi_node: bool = False
    is_low_latency_labeled: bool = False
    is_high_throughput_labeled: bool = False
    score: float = 0.0
    score_notes: list[str] = field(default_factory=list)


def _http_get(url: str, timeout: float = 45.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read()
    for enc in ("utf-8", "gb18030", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _load_aliases() -> dict[str, str]:
    out = dict(_BUILTIN_ALIASES)
    if _ALIAS_PATH.exists():
        try:
            data = json.loads(_ALIAS_PATH.read_text(encoding="utf-8"))
            for k, v in (data.get("aliases") or data or {}).items():
                if k and v:
                    out[_norm(str(k))] = str(v).removesuffix(".html")
        except (OSError, json.JSONDecodeError):
            pass
    return out


def parse_basic_params(md_text: str) -> dict[str, Any]:
    keys = {
        "输入长度": "input_seq_len",
        "输出长度": "output_seq_len",
        "设备类型": "device_type",
        "模型名称": "model_name",
        "量化格式": "quantization",
        "NPU卡数": "num_npus",
        "部署策略": "deploy_strategy",
    }
    out: dict[str, Any] = {}
    for cn, en in keys.items():
        m = re.search(rf"^-\s*{re.escape(cn)}\s*[:：]\s*(.+?)\s*$", md_text, re.M)
        if not m:
            continue
        val = m.group(1).strip()
        if en in ("input_seq_len", "output_seq_len", "num_npus"):
            try:
                out[en] = int(val)
            except ValueError:
                out[en] = val
        else:
            out[en] = val
    return out


class _DocWalk(HTMLParser):
    """Walk HTML into ordered (heading / text / code) events."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple] = []
        self._skip = 0
        self._in_pre = False
        self._pre: list[str] = []
        self._in_h = False
        self._h_tag = ""
        self._h_buf: list[str] = []
        self._text_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "nav", "header", "footer"):
            self._skip += 1
            return
        if self._skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5"):
            self._flush_text()
            self._in_h = True
            self._h_tag = tag
            self._h_buf = []
        elif tag == "pre":
            self._flush_text()
            self._in_pre = True
            self._pre = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "nav", "header", "footer") and self._skip:
            self._skip -= 1
            return
        if self._skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5") and self._in_h:
            self._in_h = False
            title = re.sub(r"\s+", " ", "".join(self._h_buf)).strip()
            title = re.sub(r"[¶\u00b6]", "", title).strip()
            self.events.append(("h", tag, title))
        elif tag == "pre" and self._in_pre:
            self._in_pre = False
            self.events.append(("code", "".join(self._pre).strip()))

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_h:
            self._h_buf.append(data)
        elif self._in_pre:
            self._pre.append(data)
        else:
            self._text_buf.append(data)

    def _flush_text(self) -> None:
        t = re.sub(r"\s+", " ", "".join(self._text_buf)).strip()
        self._text_buf = []
        if t:
            self.events.append(("text", t))

    def close(self) -> None:  # type: ignore[override]
        self._flush_text()
        super().close()


def list_model_pages(index_html: str) -> list[str]:
    """Return page stems linked from models index (e.g. GLM5)."""
    stems: list[str] = []
    for m in re.finditer(r'href="([^"#?]+\.html)"', index_html):
        href = m.group(1)
        if "/" in href.strip("./"):
            # keep only same-dir model pages
            if href.startswith("../") or href.startswith("http"):
                continue
        name = Path(href).name
        if name.lower() in ("index.html",):
            continue
        stem = name[:-5]
        if stem and stem not in stems:
            stems.append(stem)
    return stems


def resolve_model_page(model_name: str, page_stems: list[str]) -> tuple[str | None, list[str]]:
    """Map model_name to a docs page stem. Returns (stem, tried)."""
    tried: list[str] = []
    aliases = _load_aliases()
    name = (model_name or "").strip()
    n = _norm(name)

    def add_try(x: str | None) -> None:
        if x and x not in tried:
            tried.append(x)

    # 1) curated alias
    if n in aliases:
        add_try(aliases[n])
    for k, v in aliases.items():
        if k and (k in n or n in k):
            add_try(v)

    # 2) direct / fuzzy against index stems
    stem_by_norm = {_norm(s): s for s in page_stems}
    add_try(stem_by_norm.get(n))
    # strip common suffixes
    for suf in ("instruct", "chat", "base", "w8a8", "w4a8", "bf16", "fp8", "mtp"):
        nn = _norm(re.sub(rf"[-_]?{suf}$", "", name, flags=re.I))
        add_try(stem_by_norm.get(nn))

    # substring: model contained in page or page in model
    scored: list[tuple[int, str]] = []
    for stem in page_stems:
        sn = _norm(stem)
        if not sn:
            continue
        if n == sn:
            scored.append((1000, stem))
        elif n in sn or sn in n:
            scored.append((500 + min(len(n), len(sn)), stem))
        else:
            # token overlap (qwen35 / 27b)
            nt = set(re.findall(r"[a-z]+|\d+", n))
            st = set(re.findall(r"[a-z]+|\d+", sn))
            ov = len(nt & st)
            if ov >= 2 and ("qwen" in nt) == ("qwen" in st):
                scored.append((100 + ov * 10, stem))
    scored.sort(key=lambda x: -x[0])
    for _, stem in scored[:5]:
        add_try(stem)

    # pick first that exists in index
    index_set = set(page_stems)
    for t in tried:
        if t in index_set:
            return t, tried
        # case-insensitive
        for s in page_stems:
            if s.lower() == t.lower():
                return s, tried
    return (tried[0] if tried else None), tried


def _extract_device(text: str) -> str | None:
    if re.search(r"\bA3\b|800I?\s*A3|Atlas\s+800\s*A3", text, re.I):
        if re.search(r"\bA2\b|800I?\s*A2|Atlas\s+800\s*A2", text, re.I):
            # both mentioned — leave ambiguous for scoring
            return "A2+A3"
        return "A3"
    if re.search(r"\bA2\b|800I?\s*A2|Atlas\s+800\s*A2", text, re.I):
        return "A2"
    return None


def _extract_quant(text: str) -> str | None:
    tl = text.lower()
    for q in ("w8a8", "w4a8", "w8a16", "w4a16", "fp8", "bf16", "fp16"):
        if q in tl:
            return q
    if re.search(r"\bbf16\b|bfloat16", tl):
        return "bf16"
    return None


def _extract_machines_dies(text: str) -> tuple[int | None, int | None]:
    """Parse phrases like '1 台 Atlas 800 A3（64G × 16）'."""
    machines = None
    dies = None
    m = re.search(
        r"(\d+)\s*(?:台|个|节点)?\s*Atlas[^（(]{0,40}[（(][^）)]*?[×xX]\s*(\d+)",
        text,
    )
    if m:
        machines = int(m.group(1))
        dies = int(m.group(2))
    else:
        m2 = re.search(r"(\d+)\s*(?:台|个)\s*Atlas", text)
        if m2:
            machines = int(m2.group(1))
        m3 = re.search(r"[×xX]\s*(\d+)", text)
        if m3:
            dies = int(m3.group(1))
    return machines, dies


def _parse_serve_meta(bash: str) -> dict[str, Any]:
    def flag_int(name: str) -> int | None:
        m = re.search(rf"--{name}\s+(\d+)", bash)
        return int(m.group(1)) if m else None

    path_m = re.search(r"vllm\s+serve\s+(\S+)", bash)
    return {
        "tp": flag_int("tensor-parallel-size"),
        "dp": flag_int("data-parallel-size") or 1,
        "max_model_len": flag_int("max-model-len"),
        "max_num_seqs": flag_int("max-num-seqs"),
        "model_path": path_m.group(1) if path_m else None,
        "enable_expert_parallel": bool(
            re.search(r"--enable-expert-parallel\b", bash)
        ),
    }


def extract_candidates(html: str, source_url: str) -> list[ServeCandidate]:
    parser = _DocWalk()
    parser.feed(html)
    parser.close()

    heading_stack: list[tuple[int, str]] = []
    recent_texts: list[str] = []
    out: list[ServeCandidate] = []

    for ev in parser.events:
        if ev[0] == "h":
            level = int(ev[1][1])
            title = ev[2]
            heading_stack = [(l, t) for l, t in heading_stack if l < level]
            heading_stack.append((level, title))
            recent_texts = []
            continue
        if ev[0] == "text":
            recent_texts.append(ev[1])
            if len(recent_texts) > 4:
                recent_texts = recent_texts[-4:]
            continue
        if ev[0] != "code":
            continue
        code = ev[1]
        if "vllm serve" not in code and "vllm\nserve" not in code:
            continue
        # skip non-serve snippets (curl / eval only)
        if not re.search(r"\bvllm\s+serve\b", code):
            continue

        heading_path = " > ".join(t for _, t in heading_stack)
        context = " ".join(recent_texts)[-800:]
        blob = f"{heading_path}\n{context}\n{code}"
        meta = _parse_serve_meta(code)
        device = _extract_device(blob)
        quant = _extract_quant(blob) or _extract_quant(meta.get("model_path") or "")
        machines, dies = _extract_machines_dies(context)
        if machines is None and dies is None:
            machines, dies = _extract_machines_dies(blob)
        h_low = bool(re.search(r"低时延|低延迟|low\s*latency", blob, re.I))
        h_high = bool(re.search(r"高吞吐|高并发|high\s*throughput", blob, re.I))
        is_pd = bool(re.search(r"\bPD\b|分离|disaggregat|1P1D|P/D", heading_path + context, re.I))
        is_multi = bool(
            re.search(r"多节点|多机|multi-?node|节点\s*[01]", heading_path + context, re.I)
        )
        # section 性能调优 tables often label HT/LL explicitly
        if re.search(r"高吞吐|High Throughput", heading_path + context, re.I):
            h_high = True
        if re.search(r"低时延|低延迟|Low Latency", heading_path + context, re.I):
            h_low = True

        out.append(
            ServeCandidate(
                bash=code.strip() + ("\n" if not code.endswith("\n") else ""),
                heading_path=heading_path,
                context=context,
                source_url=source_url,
                device_hint=device,
                quant_hint=quant,
                machines_hint=machines,
                dies_hint=dies,
                tp=meta["tp"],
                dp=meta["dp"],
                max_model_len=meta["max_model_len"],
                max_num_seqs=meta["max_num_seqs"],
                model_path=meta["model_path"],
                enable_expert_parallel=meta["enable_expert_parallel"],
                is_pd=is_pd,
                is_multi_node=is_multi,
                is_low_latency_labeled=h_low and not h_high,
                is_high_throughput_labeled=h_high,
            )
        )
        recent_texts = []
    return out


def _expected_dies(device_type: str, num_npus: int) -> int:
    """A3 physical cards × 2 dies; A2 cards = dies."""
    dt = (device_type or "").upper()
    if "A3" in dt:
        return int(num_npus) * 2
    return int(num_npus)


def score_candidate(
    c: ServeCandidate,
    *,
    device_type: str,
    quantization: str,
    num_npus: int,
    deploy_strategy: str,
    input_seq_len: int,
    output_seq_len: int,
) -> ServeCandidate:
    notes: list[str] = []
    score = 0.0
    need = int(input_seq_len) + int(output_seq_len)
    dt = (device_type or "").upper()
    quant = (quantization or "").lower()
    strategy = deploy_strategy or ""

    # --- hard preference: high throughput only ---
    if c.is_low_latency_labeled and not c.is_high_throughput_labeled:
        score -= 500
        notes.append("low_latency_penalty")
    if c.is_high_throughput_labeled:
        score += 80
        notes.append("high_throughput_label")
    # online single-node default scripts with EP are HT for MoE
    if c.enable_expert_parallel:
        score += 25
        notes.append("expert_parallel")
    if c.max_num_seqs:
        score += min(c.max_num_seqs, 256) / 4.0
        notes.append(f"max_num_seqs={c.max_num_seqs}")

    # section relevance by deploy strategy
    if "PD" in strategy or "分离" in strategy:
        if c.is_pd:
            score += 80
            notes.append("pd_section")
            # 高吞吐 PD 推荐（教程 §性能调优 / High Throughput）
            if c.is_high_throughput_labeled:
                score += 40
                notes.append("pd_high_throughput")
            if re.search(r"Decode|D节点|decode", c.heading_path + c.context, re.I):
                # 高吞吐场景 Decode 侧并发通常更大，略作偏好以便选出代表性脚本
                score += 10
                notes.append("pd_decode_side")
        else:
            score -= 60
            notes.append("non_pd_for_pd_strategy")
    elif "双机" in strategy or "多机" in strategy:
        if c.is_pd:
            score -= 40
            notes.append("skip_pd_for_multi_colocated")
        if c.is_multi_node:
            score += 70
            notes.append("multi_node")
        elif re.search(r"单节点|单机|5\.1", c.heading_path):
            score -= 20
            notes.append("single_node_for_multi_strategy")
    else:
        # 单机混部 / 默认：prefer 单节点在线部署
        if re.search(r"单节点|单机|5\.1", c.heading_path):
            score += 50
            notes.append("single_node_section")
        if c.is_pd:
            score -= 30
            notes.append("skip_pd_for_colocated")
        if c.is_multi_node and not c.is_pd:
            score -= 10
            notes.append("multi_node_for_single")

    # prefer 在线服务部署 over 精度评估 / docker install
    if re.search(r"在线服务部署", c.heading_path):
        score += 40
        notes.append("online_serving")
    if re.search(r"精度评估|功能验证|安装|Docker|lm_eval|Benchmark", c.heading_path, re.I):
        score -= 100
        notes.append("non_deploy_section")

    # device match
    if c.device_hint:
        if dt in (c.device_hint or "").upper() or (
            "A3" in dt and "A3" in (c.device_hint or "").upper()
        ) or ("A2" in dt and "A2" in (c.device_hint or "").upper()):
            if c.device_hint == "A2+A3":
                score += 15
                notes.append("device_ambiguous_ok")
            else:
                score += 50
                notes.append("device_match")
        else:
            score -= 40
            notes.append("device_mismatch")

    # quantization match
    if c.quant_hint and quant:
        qh = c.quant_hint.lower()
        if quant in qh or qh in quant:
            score += 50
            notes.append("quant_match")
        elif quant in ("bf16", "fp16") and qh in ("bf16", "fp16"):
            score += 40
            notes.append("quant_fp_match")
        else:
            score -= 25
            notes.append("quant_mismatch")
    elif quant and c.model_path and quant in c.model_path.lower():
        score += 45
        notes.append("quant_in_path")

    # NPU / world-size affinity
    exp_dies = _expected_dies(device_type, int(num_npus))
    world = None
    if c.tp:
        world = c.tp * (c.dp or 1)
    if world and exp_dies:
        if world == exp_dies:
            score += 40
            notes.append("world_eq_dies")
        elif world <= exp_dies:
            score += 15
            notes.append("world_le_dies")
        else:
            score -= 20
            notes.append("world_gt_dies")
    if c.dies_hint and exp_dies and c.machines_hint:
        total = c.dies_hint * c.machines_hint
        # phrase ×16 on 1 machine often means full machine dies
        if abs(total - exp_dies) <= max(1, exp_dies // 8):
            score += 20
            notes.append("dies_hint_close")

    # context length must fit workload
    if c.max_model_len is not None:
        if c.max_model_len >= need:
            score += 30
            notes.append("maxlen_ok")
        else:
            score -= 50
            notes.append("maxlen_too_small")

    c.score = score
    c.score_notes = notes
    return c


def apply_max_model_len(bash: str, input_seq_len: int, output_seq_len: int) -> tuple[str, int, bool]:
    """Ensure --max-model-len can hold input+output; return (bash, len, replaced)."""
    need = int(input_seq_len) + int(output_seq_len)
    m = re.search(r"(--max-model-len\s+)(\d+)", bash)
    if not m:
        # append before trailing newline
        new_len = need
        bash = bash.rstrip() + f" \\\n--max-model-len {new_len}\n"
        return bash, new_len, True
    cur = int(m.group(2))
    if cur >= need:
        return bash, cur, False
    bash = re.sub(r"(--max-model-len\s+)\d+", rf"\g<1>{need}", bash, count=1)
    return bash, need, True


def fetch_and_select(params: dict[str, Any], *, use_cache: bool = True) -> dict[str, Any]:
    model_name = str(params.get("model_name") or "")
    missing = [
        k
        for k in (
            "model_name",
            "device_type",
            "quantization",
            "num_npus",
            "deploy_strategy",
            "input_seq_len",
            "output_seq_len",
        )
        if params.get(k) in (None, "")
    ]
    if missing:
        return {
            "ok": False,
            "error": f"missing_params:{','.join(missing)}",
            "warning": "配置 ## 基本参数 不完整，无法从文档站拉取基线。",
        }

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    index_cache = _CACHE_DIR / "index.html"
    try:
        index_html = _http_get(DOCS_INDEX)
        if use_cache:
            index_cache.write_text(index_html, encoding="utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        if index_cache.exists():
            index_html = index_cache.read_text(encoding="utf-8")
        else:
            return {
                "ok": False,
                "error": f"index_fetch_failed:{e}",
                "warning": (
                    f"无法访问模型教程索引 {DOCS_INDEX}，且无本地缓存。"
                    "请检查网络后重试，或手动补充 baseline-docs/。"
                ),
                "docs_index": DOCS_INDEX,
            }

    pages = list_model_pages(index_html)
    stem, tried = resolve_model_page(model_name, pages)
    if not stem:
        return {
            "ok": False,
            "error": "model_page_not_found",
            "warning": (
                f"在 {DOCS_INDEX} 未找到与模型「{model_name}」对应的教程页。"
                f"尝试过: {tried or '(无)'}。"
                "可在 references/docs_model_page_aliases.json 增加别名后重试。"
            ),
            "docs_index": DOCS_INDEX,
            "available_pages_sample": pages[:30],
            "tried_pages": tried,
        }

    page_url = f"{DOCS_BASE}/{stem}.html"
    page_cache = _CACHE_DIR / f"{stem}.html"
    try:
        page_html = _http_get(page_url)
        if use_cache:
            page_cache.write_text(page_html, encoding="utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        if page_cache.exists():
            page_html = page_cache.read_text(encoding="utf-8")
        else:
            return {
                "ok": False,
                "error": f"page_fetch_failed:{e}",
                "warning": f"无法下载 {page_url}，请检查网络或手动打开该页复制高吞吐启动命令。",
                "source_url": page_url,
                "tried_pages": tried,
            }

    cands = extract_candidates(page_html, page_url)
    if not cands:
        return {
            "ok": False,
            "error": "no_vllm_serve_blocks",
            "warning": f"页面 {page_url} 未解析到 vllm serve 代码块。",
            "source_url": page_url,
        }

    scored = [
        score_candidate(
            c,
            device_type=str(params["device_type"]),
            quantization=str(params["quantization"]),
            num_npus=int(params["num_npus"]),
            deploy_strategy=str(params["deploy_strategy"]),
            input_seq_len=int(params["input_seq_len"]),
            output_seq_len=int(params["output_seq_len"]),
        )
        for c in cands
    ]
    strategy = str(params.get("deploy_strategy") or "")
    is_pd_strategy = bool(re.search(r"PD|分离", strategy))
    is_multi_strategy = bool(re.search(r"双机|多机", strategy))

    # drop clearly non-HT when any HT-labeled exists (within strategy-relevant pool)
    if is_pd_strategy:
        scoped = [c for c in scored if c.is_pd] or scored
    elif is_multi_strategy:
        scoped = [c for c in scored if c.is_multi_node and not c.is_pd] or [
            c for c in scored if c.is_multi_node
        ] or scored
    else:
        scoped = scored

    ht = [c for c in scoped if c.is_high_throughput_labeled]
    pool = ht if ht else [c for c in scoped if not c.is_low_latency_labeled] or scoped
    pool.sort(key=lambda c: c.score, reverse=True)
    best = pool[0]

    bash, used_len, replaced = apply_max_model_len(
        best.bash,
        int(params["input_seq_len"]),
        int(params["output_seq_len"]),
    )

    # For PD: also return sibling serve blocks under the same PD heading family
    related_bash: list[dict[str, Any]] = []
    if is_pd_strategy and best.is_pd:
        prefix = (
            best.heading_path.rsplit(" > ", 1)[0]
            if " > " in best.heading_path
            else best.heading_path
        )
        for c in sorted(scored, key=lambda x: -x.score):
            if not c.is_pd or c.bash.strip() == best.bash.strip():
                continue
            same_family = bool(prefix and prefix in c.heading_path)
            if not same_family and c.score < best.score - 50:
                continue
            related_bash.append(
                {
                    "heading_path": c.heading_path,
                    "tp": c.tp,
                    "dp": c.dp,
                    "max_num_seqs": c.max_num_seqs,
                    "max_model_len": c.max_model_len,
                    "bash": c.bash,
                }
            )
            if len(related_bash) >= 6:
                break

    reason = params.get("_fallback_reason") or "local_unmatched_or_unsupported_strategy"
    selection_note = (
        f"已从官方模型教程拉取高吞吐配置（deploy_strategy={strategy}；reason={reason}）"
    )

    return {
        "ok": True,
        "source": "vllm-ascend-docs",
        "profile": "高吞吐",
        "profile_confirmed": True,
        "selection_note": selection_note,
        "fallback_reason": reason,
        "deploy_strategy": strategy,
        "docs_index": DOCS_INDEX,
        "source_url": page_url,
        "model_page": f"{stem}.html",
        "tried_pages": tried,
        "heading_path": best.heading_path,
        "context": best.context,
        "device_hint": best.device_hint,
        "quant_hint": best.quant_hint,
        "tp": best.tp,
        "dp": best.dp,
        "max_model_len": used_len,
        "max_model_len_replaced": replaced,
        "max_num_seqs": best.max_num_seqs,
        "ref_max_concurrency": best.max_num_seqs,
        "model_path": best.model_path,
        "enable_expert_parallel": best.enable_expert_parallel,
        "is_pd": best.is_pd,
        "is_multi_node": best.is_multi_node,
        "score": best.score,
        "score_notes": best.score_notes,
        "candidates_considered": len(scored),
        "bash": bash,
        "related_bash_blocks": related_bash,
        "top_candidates": [
            {
                "score": c.score,
                "heading_path": c.heading_path,
                "tp": c.tp,
                "dp": c.dp,
                "max_model_len": c.max_model_len,
                "max_num_seqs": c.max_num_seqs,
                "quant_hint": c.quant_hint,
                "device_hint": c.device_hint,
                "high_throughput": c.is_high_throughput_labeled,
                "low_latency": c.is_low_latency_labeled,
                "is_pd": c.is_pd,
                "is_multi_node": c.is_multi_node,
            }
            for c in pool[:5]
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True, help="MD 配置文件路径（含 ## 基本参数）")
    ap.add_argument("--out", help="写入 JSON 结果路径")
    ap.add_argument("--bash-out", help="写入选中的 bash 启动脚本路径")
    ap.add_argument("--json", action="store_true", help="向 stdout 打印 JSON")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args(argv)

    cfg_path = Path(args.config)
    if not cfg_path.is_file():
        err = {"ok": False, "error": "config_not_found", "warning": f"配置文件不存在: {cfg_path}"}
        print(json.dumps(err, ensure_ascii=False, indent=2))
        return 2

    params = parse_basic_params(cfg_path.read_text(encoding="utf-8"))
    result = fetch_and_select(params, use_cache=not args.no_cache)

    if args.out:
        Path(args.out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.bash_out and result.get("ok") and result.get("bash"):
        Path(args.bash_out).write_text(result["bash"], encoding="utf-8")

    if args.json or not args.out:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
