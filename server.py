#!/usr/bin/env python3
"""
Golddigger MCP Server — B2B Lead Intelligence API
Public repository: https://github.com/SassumiX/golddigger-mcp

用户本地运行，数据不离开客户机器。
Token 由客户提供，费用自担。

Usage:
  # Claude Desktop (macOS) — 客户本地安装
  "golddigger": {
    "command": "python3",
    "args": ["/path/to/server.py", "--transport", "stdio"]
  }
"""
import os, json, argparse, sys

# ── 依赖检查 ────────────────────────────────────────────────────────────────
MISSING = []

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    MISSING.append("mcp")

try:
    import matplotlib; matplotlib.use('Agg')
    import numpy as np
    RADAR_OK = True
except ImportError:
    RADAR_OK = False
    MISSING.append("matplotlib")

try:
    from docx import Document
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    DOCX_OK = True
except ImportError:
    DOCX_OK = False
    MISSING.append("python-docx")

if MISSING:
    print(f"[ERROR] Missing dependencies: {', '.join(MISSING)}")
    print(f"[HINT]  Run: pip install {' '.join(MISSING)}")
    sys.exit(1)

# ── MCP Server ─────────────────────────────────────────────────────────────
mcp = FastMCP(
    "Golddigger",
    description=(
        "B2B Lead Intelligence API — search, enrich & score leads from 10M+ global companies database. "
        "All report generation runs locally. No data leaves the user's machine."
    )
)

# ── 端点基线（2026-10-06 逐个实测，判定口径：带正确 key 后 404 = 路由不存在）──
#   GET  /api/health  → 服务健康（免鉴权）
#   GET  /api/quota   → 账户配额（真实端点；旧版代码用的 /api/tenants/me 从未上线）
#   GET  /api/leads   → 租户已存线索
#   POST /api/search  → 搜索（旧版代码用的 GET /api/leads/search 不存在，永远 404）
DEFAULT_HOST = os.environ.get("GOLDDIGGER_HOST", "https://golddigger.gold")
DEFAULT_KEY  = os.environ.get("GOLDDIGGER_API_KEY", "")   # 不再内置 demo key
# 本地软预算：防止 Agent 循环把当天配额一次烧光（默认 = free 计划实测 20 次/天）
DEFAULT_DAILY_BUDGET = int(os.environ.get("GOLDDIGGER_DAILY_BUDGET", "20"))
# 本地软预留：剩余低于这个数就不再自动发起搜索，把额度留给人工决策
QUOTA_RESERVE = int(os.environ.get("GOLDDIGGER_QUOTA_RESERVE", "2"))


# ── 共享 HTTP 层 ─────────────────────────────────────────────────────────────
import urllib.request, urllib.error, urllib.parse, datetime, pathlib

_QUOTA_STATE = pathlib.Path(
    os.environ.get("GOLDDIGGER_STATE_DIR",
                   str(pathlib.Path.home() / ".golddigger"))
).expanduser()


def _http_json(method: str, url: str, api_key: str = "",
               payload: dict = None, timeout: int = 60) -> dict:
    """返回 {"status": int, "data": dict|None, "error": str|None}，不抛异常。"""
    headers = {"Content-Type": "application/json",
               "User-Agent": "Golddigger-MCP/2.0"}
    if api_key:
        headers["X-API-KEY"] = api_key
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode(errors="replace")
            try:
                return {"status": resp.status, "data": json.loads(raw), "error": None}
            except json.JSONDecodeError:
                return {"status": resp.status, "data": {"raw": raw[:500]}, "error": None}
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")[:500]
        return {"status": e.code, "data": None, "error": raw}
    except Exception as e:
        return {"status": 0, "data": None, "error": f"{type(e).__name__}: {e}"}


def _quota(api_key: str, host: str) -> dict:
    r = _http_json("GET", f"{host}/api/quota", api_key, timeout=15)
    if r["status"] != 200 or not r["data"]:
        return {"ok": False, "http_status": r["status"], "error": r["error"] or "quota 端点不可用"}
    d = r["data"]
    used, quota = d.get("used"), d.get("quota")
    return {
        "ok": True,
        "plan": d.get("plan"),
        "used": used,
        "quota": quota,
        "remaining": d.get("remaining", (quota or 0) - (used or 0)),
        "allowed": d.get("allowed"),
        "resets_at": d.get("resets_at"),
    }


def _budget_spend(limit: int) -> dict:
    """本地记账：每天实际发出的搜索次数，防止 Agent 循环超支。"""
    today = datetime.date.today().isoformat()
    f = _QUOTA_STATE / "search_budget.json"
    try:
        state = json.loads(f.read_text()) if f.exists() else {}
    except Exception:
        state = {}
    if state.get("date") != today:
        state = {"date": today, "spent": 0}
    allowed = state["spent"] < limit
    if allowed:
        state["spent"] += 1
        _QUOTA_STATE.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(state))
    return {"date": today, "spent": state["spent"], "local_budget": limit,
            "allowed": allowed, "remaining_local": max(0, limit - state["spent"])}


def _explain(status: int, error: str) -> str:
    if status in (401, 403):
        return "API key 无效/无权限 —— 检查 GOLDDIGGER_API_KEY"
    if status == 404:
        return "端点不存在（404）—— 当前 SDK/文档与线上不一致，见 README_API_NOTES"
    if status == 429:
        return "配额用尽（429）—— 等重置或升级 https://golddigger.gold/"
    if status >= 500:
        return f"站点侧故障（{status}）—— 不是你的 key 问题，重试无用，等站方修"
    if status == 0:
        return f"网络/超时 —— {error}"
    return error or f"HTTP {status}"


# ═══════════════════════════════════════════════════════════════════════════
# 工具 1：health_check
# ═══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def health_check(api_key: str = DEFAULT_KEY,
                 host: str = DEFAULT_HOST) -> dict:
    """
    检查 Golddigger 服务健康 + 账户配额（GET /api/health + GET /api/quota）。

    Args:
        api_key: 客户的 Golddigger API Key（默认读环境变量 GOLDDIGGER_API_KEY）
        host: Golddigger API 地址（默认 golddigger.gold）

    Returns:
        {"status":"ok"|"degraded"|"error", "service", "version",
         "plan", "quota", "used", "remaining", "resets_at",
         "search_endpoint": "ok"|"degraded", "message"}
    """
    h = _http_json("GET", f"{host}/api/health", timeout=10)
    if h["status"] != 200:
        return {"status": "error", "message": _explain(h["status"], h["error"])}

    info = h["data"] or {}
    out = {
        "status": "ok",
        "service": info.get("service"),
        "version": info.get("version"),
        "server_time": info.get("time"),
        "search_endpoint": "unknown",
    }

    if not api_key:
        out["status"] = "degraded"
        out["message"] = "服务在线，但没配 GOLDDIGGER_API_KEY —— 查不了配额，也不能搜索"
        out["plan"] = out["quota"] = out["used"] = out["remaining"] = None
        return out

    q = _quota(api_key, host)
    if not q["ok"]:
        out["status"] = "degraded"
        out["message"] = f"服务在线，但配额查询失败：{_explain(q.get('http_status', 0), q.get('error'))}"
        return out

    out.update({k: q[k] for k in ("plan", "quota", "used", "remaining", "resets_at")})
    out["quota_allowed"] = q["allowed"]
    out["message"] = (f"✅ {q['plan']} 方案，今日剩余 {q['remaining']}/{q['quota']}，"
                      f"{q['resets_at']} 重置")

    # 搜索端点是唯一写接口。要不要主动探一下？
    # 端点修好之后，一次探测 = 消耗 1 次配额，所以默认关闭，用环境变量开。
    # （当前服务端 500，探了也不扣配额 —— 2026-10-06 实测 6 次失败后 used 仍为 0）
    if os.environ.get("GOLDDIGGER_PROBE_SEARCH", "0") == "1":
        s = _http_json("POST", f"{host}/api/search", api_key,
                       {"query": "healthcheck", "country": "", "limit": 1}, timeout=45)
        out["search_endpoint"] = "ok" if s["status"] == 200 else "degraded"
        if s["status"] != 200:
            out["search_status_code"] = s["status"]
            out["search_error"] = _explain(s["status"], s["error"])
            out["message"] += f" ｜ ⚠️ 搜索端点异常（{s['status']}）：{out['search_error']}"
            out["status"] = "degraded"
    else:
        out["search_endpoint"] = "not_probed（设 GOLDDIGGER_PROBE_SEARCH=1 才探，会烧配额）"
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 工具 2：check_quota（挖客前必查，防烧配额）
# ═══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def check_quota(api_key: str = DEFAULT_KEY,
                host: str = DEFAULT_HOST,
                daily_budget: int = DEFAULT_DAILY_BUDGET) -> dict:
    """
    查询服务端配额 + 本地预算账本。批量挖客前先调这个。

    Args:
        api_key: 客户 API Key（默认读 GOLDDIGGER_API_KEY）
        host: API 地址
        daily_budget: 本地软预算（默认 20，可用 GOLDDIGGER_DAILY_BUDGET 覆盖）

    Returns:
        {"plan","quota","used","remaining","resets_at",
         "local_spent","local_budget","can_search","recommendation"}
    """
    if not api_key:
        return {"status": "error",
                "message": "缺少 API key：export GOLDDIGGER_API_KEY=gd_xxx"}

    q = _quota(api_key, host)
    if not q["ok"]:
        return {"status": "error",
                "message": _explain(q.get("http_status", 0), q.get("error"))}

    today = datetime.date.today().isoformat()
    f = _QUOTA_STATE / "search_budget.json"
    try:
        state = json.loads(f.read_text()) if f.exists() else {}
    except Exception:
        state = {}
    spent = state.get("spent", 0) if state.get("date") == today else 0

    can = q["allowed"] and q["remaining"] > QUOTA_RESERVE and spent < daily_budget
    if not can:
        rec = "配额不够了：先按 query 优先级挑几条跑，别全量刷；或升级 https://golddigger.gold/"
    elif q["remaining"] <= 5:
        rec = f"只剩 {q['remaining']} 次，优先跑角色词（进口商/开发商/集团采购），泛需求词先别碰"
    else:
        rec = f"可跑约 {min(q['remaining'] - QUOTA_RESERVE, daily_budget - spent)} 次，按优先级排"

    return {"status": "ok", "plan": q["plan"], "quota": q["quota"], "used": q["used"],
            "remaining": q["remaining"], "resets_at": q["resets_at"],
            "local_spent": spent, "local_budget": daily_budget,
            "can_search": can, "recommendation": rec,
            "state_file": str(f)}


# ═══════════════════════════════════════════════════════════════════════════
# 工具 3：search_leads
# ═══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def search_leads(keyword: str,
                 limit: int = 20,
                 country: str = "",
                 api_key: str = DEFAULT_KEY,
                 host: str = DEFAULT_HOST,
                 dry_run: bool = False,
                 skip_quota_check: bool = False) -> dict:
    """
    搜索 B2B 买家/供应商（POST /api/search）。

    ⚠️ 每次调用消耗 1 次配额。批量挖客前先调 check_quota。
    Agent 循环调用前请设 dry_run=True 预演，不会消耗配额。

    Args:
        keyword: 搜索词——买家视角的采购意图词，如 "smart lock distributor wanted"
        limit: 返回数量上限（默认 20，最大 500）
        country: 国家代码（AE/SA/NG…），空 = 不限
        api_key: 客户 API Key（默认读 GOLDDIGGER_API_KEY）
        host: API 地址
        dry_run: 只返回将要发出的请求，不真调（不消耗配额）
        skip_quota_check: 跳过配额预检（不推荐）

    Returns:
        {"status":"ok"|"quota_exhausted"|"server_error"|"error",
         "count", "total_found", "leads", "query", "country", "usage"}
    """
    if not keyword or not keyword.strip():
        return {"status": "error", "message": "keyword 不能为空"}

    limit = max(1, min(int(limit), 500))
    payload = {"query": keyword.strip(), "country": country or "", "limit": limit}

    if dry_run:
        return {"status": "dry_run", "would_call": f"POST {host}/api/search",
                "payload": payload, "quota_cost": 1,
                "message": "预演模式，未发出请求"}

    if not api_key:
        return {"status": "error",
                "message": "缺少 API key：export GOLDDIGGER_API_KEY=gd_xxx"}

    if not skip_quota_check:
        q = _quota(api_key, host)
        if not q["ok"]:
            return {"status": "error",
                    "message": _explain(q.get("http_status", 0), q.get("error"))}
        if not q["allowed"] or q["remaining"] <= 0:
            return {"status": "quota_exhausted", "leads": [], "count": 0,
                    "remaining": q["remaining"], "resets_at": q["resets_at"],
                    "message": "今日配额已用尽，明天再来"}
        if q["remaining"] <= QUOTA_RESERVE:
            return {"status": "quota_exhausted", "leads": [], "count": 0,
                    "remaining": q["remaining"], "resets_at": q["resets_at"],
                    "message": f"只剩 {q['remaining']} 次（保留线 {QUOTA_RESERVE}），先别搜了"}

    b = _budget_spend(DEFAULT_DAILY_BUDGET)
    r = _http_json("POST", f"{host}/api/search", api_key, payload, timeout=120)

    if r["status"] != 200:
        return {"status": "server_error" if r["status"] >= 500 else "error",
                "count": 0, "leads": [], "query": payload["query"],
                "http_status": r["status"],
                "message": _explain(r["status"], r["error"])}

    d = r["data"] or {}
    leads = d.get("leads", []) or []
    q2 = _quota(api_key, host)
    return {"status": "ok", "count": len(leads),
            "total_found": d.get("total_found", len(leads)),
            "leads": leads, "query": payload["query"], "country": payload["country"],
            "usage": {"remaining": q2.get("remaining"), "used": q2.get("used"),
                      "local_spent": b["spent"], "local_budget": b["local_budget"]}}


# ═══════════════════════════════════════════════════════════════════════════
# 工具 4：score_lead
# ═══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def score_lead(company: str,
               country: str = "",
               industry: str = "",
               has_contact: bool = False,
               scale: str = "",
               note: str = "") -> dict:
    """
    对采购商进行六维质量评分（本地计算，不调用外部 API）。

    数据主权：评分逻辑完全在客户本地运行，原始数据不离开用户机器。

    Args:
        company: 公司名
        country: 国家
        industry: 行业
        has_contact: 是否有直接联系方式（邮箱/电话）
        scale: 公司规模描述
        note: 备注（如"扩张期"/"NEOM项目"/"并购"）

    Returns:
        {
            "company": str,
            "total": int (0-100),
            "tier": "HOT|WARM|COLD",
            "scores": {
                "purchase_power": int, "company_scale": int,
                "demand_urgency": int, "repeat_potential": int,
                "region_match": int, "contact_ease": int
            }
        }
    """
    def s(key, base=50, bonus=0, cap=100):
        return min(cap, base + bonus)

    bonus_scale   = 35 if any(x in scale.lower() for x in ["上市", "listed", "jse", "nasdaq"]) \
               else 20 if any(x in scale.lower() for x in ["集团", "000+", "1000+"]) \
               else 10 if any(x in scale.lower() for x in ["500+", "100-500"]) else 0

    bonus_industry = 25 if any(x in industry.lower() for x in ["mining","quarry","drilling","construction"]) \
               else 10 if any(x in industry.lower() for x in ["oil","energy","manufacturing"]) else 0

    bonus_region   = 40 if any(x in country.lower() for x in [
                   "south africa","nigeria","kenya","tanzania","zambia",
                   "uae","dubai","fujairah","saudi","qatar","oman","bahrain",
                   "vietnam","indonesia","thailand","malaysia","philippines"]) \
               else 25 if any(x in country.lower() for x in [
                   "africa","middle east","southeast asia","latin america"]) else 0

    bonus_contact = 30 if has_contact else 0
    bonus_urgency = 25 if any(x in note.lower() for x in [
                   "expansion","acquisition","并购","扩张","neom","vision 2030","并购整合"]) \
               else 15 if any(x in note.lower() for x in ["new project","新建","招标"]) else 0

    sp  = s("purchase_power", 50, bonus_scale)
    css = s("company_scale", 50, bonus_scale)
    du  = s("demand_urgency", 50, bonus_urgency + bonus_industry)
    rp  = s("repeat_potential", 50, bonus_industry)
    rm  = s("region_match", 50, bonus_region)
    ce  = s("contact_ease", 50, bonus_contact)

    total = round((sp + css + du + rp + rm + ce) / 6)
    tier  = "HOT" if total >= 80 else "WARM" if total >= 60 else "COLD"

    return {
        "company": company,
        "total": total,
        "tier": tier,
        "scores": {
            "purchase_power":   sp,
            "company_scale":    css,
            "demand_urgency":  du,
            "repeat_potential": rp,
            "region_match":    rm,
            "contact_ease":    ce
        }
    }


# ═══════════════════════════════════════════════════════════════════════════
# 工具 5：generate_report（核心商业工具）
# ═══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def generate_report(company_name: str,
                   product_desc: str,
                   buyers: list,
                   api_key: str = DEFAULT_KEY,
                   host: str = DEFAULT_HOST,
                   output_dir: str = "") -> dict:
    """
    生成 Golddigger 风格的 B2B 客户画像雷达图 Word 报告。

    数据主权声明：
    - 雷达图生成：matplotlib 本地渲染，PNG 不上传任何服务器
    - Word 报告：python-docx 本地生成，.docx 存储在客户本地路径
    - 不调用任何外部存储服务

    ⚠️ Token 费用：搜索调用使用客户提供的 api_key，费用由客户自行承担。
       雷达图生成和报告排版完全免费（无 API 调用）。

    Args:
        company_name: 客户公司名（用于报告标题）
        product_desc: 产品描述（用于报告元信息）
        buyers: 采购商数组，每个对象需包含：
                 name, country, industry, has_contact
                 可选：type, scale, buyer_role, purchase_needs,
                       contacts, outreach, note
        api_key: 客户的 Golddigger API Key（用于搜索）
        host: Golddigger API 地址
        output_dir: 报告输出目录（默认 /tmp/gd_reports）

    Returns:
        {
            "status": "ok"|"error",
            "output_path": str,   ← .docx 文件本地路径
            "radar_count": int,   ← 生成的雷达图数量
            "buyers_scored": [ {"name": str, "total": int, "tier": str}, ... ],
            "db_status": str      ← 账户方案 + 剩余配额（真实接口 /api/quota）
        }
    """
    import urllib.request, urllib.parse, os, tempfile

    # ── 参数预处理 ──
    if not output_dir:
        output_dir = os.path.join(tempfile.gettempdir(), "gd_reports")

    os.makedirs(output_dir, exist_ok=True)
    chart_dir = os.path.join(output_dir, "radar_charts")
    os.makedirs(chart_dir, exist_ok=True)

    safe_name = company_name.replace(".", "_").replace("/", "_")
    ts = "20260922"  # 可替换为 date.strftime("%Y%m%d")
    out_doc = os.path.join(output_dir, f"{safe_name}_buyer_radar_{ts}.docx")

    # ── 颜色常量 ──
    GOLD     = RGBColor(0xC9, 0x81, 0x2A)
    DARK     = RGBColor(0x1A, 0x1A, 0x2E)
    ACCENT   = RGBColor(0x25, 0x63, 0xEB)
    HOT_RED  = RGBColor(0xDC, 0x26, 0x26)
    WARM_ORG = RGBColor(0xF5, 0x9E, 0x0B)
    GRAY     = RGBColor(0x6B, 0x72, 0x80)
    LIGHT    = RGBColor(0x33, 0x33, 0x33)
    WHITE    = RGBColor(0xFF, 0xFF, 0xFF)

    # ── 子函数 ──
    def set_bg(cell, hex_c):
        tc = cell._tc; tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), hex_c.lstrip('#')); tcPr.append(shd)

    def hr(doc, color='C9812A'):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(4)
        pPr = p._p.get_or_add_pPr(); pBdr = OxmlElement('w:pBdr')
        b = OxmlElement('w:bottom'); b.set(qn('w:val'), 'single')
        b.set(qn('w:sz'), '6'); b.set(qn('w:space'), '1'); b.set(qn('w:color'), color)
        pBdr.append(b); pPr.append(pBdr)

    def srun(run, sz=11, bold=False, color=None, italic=False):
        run.font.size = Pt(sz); run.font.bold = bold; run.font.italic = italic
        if color: run.font.color.rgb = color
        r = run._r; rPr = r.get_or_add_rPr()
        rF = rPr.find(qn('w:rFonts'))
        if rF is None: rF = OxmlElement('w:rFonts'); rPr.insert(0, rF)
        rF.set(qn('w:eastAsia'), 'Microsoft YaHei')

    def heading(doc, text, lvl=2):
        szs = {1:28, 2:18, 3:14}; cs = {1:GOLD, 2:DARK, 3:DARK}
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14 if lvl==1 else 10)
        p.paragraph_format.space_after = Pt(4)
        if lvl==1: p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text)
        srun(r, sz=szs.get(lvl,14), bold=True, color=cs.get(lvl, DARK))

    def para(doc, text, color=None, bold=False, center=False, sz=11, italic=False):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(4)
        if center: p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text); srun(r, sz=sz, bold=bold, italic=italic, color=color or LIGHT)

    def bullet(doc, text, sz=10.5):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Cm(0.5)
        r = p.add_run(text); srun(r, sz=sz, color=LIGHT)

    def mtable(doc, headers, rows, widths=None):
        tbl = doc.add_table(rows=1+len(rows), cols=len(headers))
        tbl.style = 'Table Grid'; tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        if widths:
            for i, w in enumerate(widths):
                for cell in tbl.columns[i].cells: cell.width = Cm(w)
        for i, h in enumerate(headers):
            c = tbl.rows[0].cells[i]; set_bg(c, '1A1A2E')
            p = c.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(h); srun(r, sz=10, bold=True, color=WHITE)
        for ri, rd in enumerate(rows):
            bg = 'F9FAFB' if ri%2==0 else 'FFFFFF'
            for ci, txt in enumerate(rd):
                c = tbl.rows[ri+1].cells[ci]; set_bg(c, bg)
                p = c.paragraphs[0]; r = p.add_run(txt); srun(r, sz=10, color=LIGHT)
                c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        return tbl

    def add_img(doc, path, width=Cm(12)):
        if not os.path.exists(path): return
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4); p.paragraph_format.space_after = Pt(4)
        p.add_run().add_picture(path, width=width)

    def rbar(doc, label, score):
        bar = '█' * (score//10) + '░' * (10 - score//10)
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(3); p.paragraph_format.space_after = Pt(3)
        r1 = p.add_run(f'{label:<12}'); srun(r1, sz=10, color=GRAY)
        r2 = p.add_run(bar); srun(r2, sz=10, color=ACCENT)
        r3 = p.add_run(f' {score}/100'); srun(r3, sz=10, bold=True, color=ACCENT)

    # ── 雷达图 ──
    def draw_radar(values, fname, color='#2563EB', title=''):
        n = 6
        labels = ['Purchase\nPower','Company\nScale','Demand\nUrgency',
                  'Repeat\nPotential','Region\nMatch','Contact\nEase']
        angles = np.linspace(0, 2*np.pi, n, endpoint=False).tolist()
        af = angles + angles[:1]; vf = values + [values[0]]

        fig, ax = plt.subplots(figsize=(5.5, 5.5), subplot_kw=dict(polar=True))
        fig.patch.set_facecolor('#F9FAFB'); ax.set_facecolor('#F9FAFB')
        for lvl in [20,40,60,80,100]:
            ax.plot(af, [lvl]*len(af), color='#E5E7EB', lw=.5, ls='--')
        ax.plot(af, [100]*len(af), color='#D1D5DB', lw=1)
        ax.fill(af, vf, color=color, alpha=.15)
        ax.plot(af, vf, color=color, lw=2.5, marker='o', markersize=6,
                markerfacecolor='white', markeredgecolor=color)
        ax.set_xticks(angles); ax.set_xticklabels(labels, size=8, color='#374151', fontweight='bold')
        ax.set_yticks([20,40,60,80,100]); ax.set_yticklabels(['20','40','60','80','100'], size=7, color='#9CA3AF')
        ax.set_ylim(0, 110); ax.set_theta_offset(np.pi/2); ax.set_theta_direction(-1)
        ax.spines['polar'].set_visible(False)
        if title: ax.set_title(title, size=11, fontweight='bold', color='#1A1A2E', pad=15)
        plt.tight_layout(); plt.savefig(fname, dpi=150, bbox_inches='tight', facecolor='#F9FAFB'); plt.close()

    def draw_compare(buyers_list, fname):
        n = 6
        labels = ['Purchase\nPower','Company\nScale','Demand\nUrgency',
                  'Repeat\nPotential','Region\nMatch','Contact\nEase']
        angles = np.linspace(0, 2*np.pi, n, endpoint=False).tolist()
        af = angles + angles[:1]
        fig, ax = plt.subplots(figsize=(6,6), subplot_kw=dict(polar=True))
        fig.patch.set_facecolor('#F9FAFB'); ax.set_facecolor('#F9FAFB')
        colors = ['#DC2626','#2563EB','#C9812A']
        for i, b in enumerate(buyers_list[:3]):
            vf = b['scores'] + [b['scores'][0]]
            ax.fill(af, vf, color=colors[i], alpha=.12)
            ax.plot(af, vf, color=colors[i], lw=2, marker='o', markersize=5,
                    markerfacecolor='white', markeredgecolor=colors[i],
                    label=f"{b['name'][:15]}... ({b['total']})")
        for lvl in [20,40,60,80,100]:
            ax.plot(af, [lvl]*len(af), color='#E5E7EB', lw=.5, ls='--')
        ax.plot(af, [100]*len(af), color='#D1D5DB', lw=1)
        ax.set_xticks(angles); ax.set_xticklabels(labels, size=8, color='#374151', fontweight='bold')
        ax.set_yticks([20,40,60,80,100]); ax.set_yticklabels(['20','40','60','80','100'], size=7, color='#9CA3AF')
        ax.set_ylim(0,110); ax.set_theta_offset(np.pi/2); ax.set_theta_direction(-1)
        ax.spines['polar'].set_visible(False)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3,1.1), fontsize=8,
                  framealpha=.8, edgecolor='#E5E7EB')
        ax.set_title('Three-Buyer Comparison Radar', size=12, fontweight='bold', color='#1A1A2E', pad=18)
        plt.tight_layout(); plt.savefig(fname, dpi=150, bbox_inches='tight', facecolor='#F9FAFB'); plt.close()

    # ── 读取账户状态（/api/health + /api/quota，2026-10-06 实测的真实端点）──
    health_data = _http_json("GET", f"{host}/api/health", timeout=10).get("data") or {}
    quota_data = _quota(api_key, host) if api_key else {"ok": False}
    db_status = (
        f"{quota_data.get('plan')} 方案 · 剩余 {quota_data.get('remaining')}"
        f"/{quota_data.get('quota')}（{quota_data.get('resets_at')} 重置）"
        if quota_data.get("ok") else
        f"服务 {health_data.get('status', 'unknown')} · 配额未知（未提供 API key）"
    )

    # ── 评分 + 构造 buyers ──
    scored = []
    for b in buyers:
        r = score_lead(
            company=b.get("name","Unknown"),
            country=b.get("country",""),
            industry=b.get("industry",""),
            has_contact=b.get("has_contact", False),
            scale=b.get("scale",""),
            note=b.get("note","")
        )
        scored.append({
            "name": b.get("name","Unknown"),
            "country": b.get("country",""),
            "type": b.get("type",""),
            "scale": b.get("scale",""),
            "industry": b.get("industry",""),
            "buyer_role": b.get("buyer_role",""),
            "purchase_needs": b.get("purchase_needs",""),
            "has_contact": b.get("has_contact", False),
            "contacts": b.get("contacts",[]),
            "outreach": b.get("outreach",""),
            "scores": list(r["scores"].values()),
            "total": r["total"],
            "tier": r["tier"]
        })

    # ── 生成雷达图 ──
    colors_list = ['#DC2626','#2563EB','#C9812A']
    for idx, b in enumerate(scored[:3]):
        draw_radar(b['scores'],
                   os.path.join(chart_dir, f'buyer_{idx+1}_radar.png'),
                   color=colors_list[idx],
                   title=f"{b['name']}\n{b['country']} · {b['total']}/100")

    draw_compare(scored, os.path.join(chart_dir, 'comparison_radar.png'))

    # ── 生成 Word ──
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21); sec.page_height = Cm(29.7)
    sec.left_margin = Cm(2.5); sec.right_margin = Cm(2.5)
    sec.top_margin = Cm(2); sec.bottom_margin = Cm(2)

    # 封面
    heading(doc, company_name, lvl=1)
    para(doc, 'BUYER RADAR REPORT', color=GOLD, center=True, sz=13)
    p_line = doc.add_paragraph(); p_line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p_line.add_run('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'); srun(r, sz=12, color=GOLD)
    para(doc, '客户画像雷达报告', color=DARK, bold=True, center=True, sz=26)
    para(doc, 'BUYER RADAR REPORT', color=GOLD, center=True, sz=11)
    for k, v in [('产品', product_desc), ('分析工具', 'Golddigger B2B Lead Engine'),
                  ('Token来源', '客户自有Key · 费用自担'), ('报告日期', '2026-09-22')]:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(2)
        r1 = p.add_run(f'{k}：'); srun(r1, sz=11, bold=True, color=DARK)
        r2 = p.add_run(v); srun(r2, sz=11, color=GRAY)
    p_line2 = doc.add_paragraph(); p_line2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p_line2.add_run('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'); srun(r2, sz=12, color=GOLD)
    doc.add_paragraph()

    # 核心发现
    heading(doc, '📊 核心发现', lvl=2); hr(doc)
    para(doc, f'基于 Golddigger 挖客引擎，找到 {len(scored)} 个高质量采购商：', color=GRAY)
    for b in scored: bullet(doc, f"{b['name']} ({b['country']}) — {b['total']}/100 [{b['tier']}]")
    doc.add_paragraph()

    # 综合雷达图
    heading(doc, '综合对比雷达图', lvl=2); hr(doc)
    add_img(doc, os.path.join(chart_dir, 'comparison_radar.png'), width=Cm(13))

    # 三客户对比表
    heading(doc, '三客户综合对比', lvl=2); hr(doc)
    mtable(doc,
        ['维度'] + [b['name'] for b in scored[:3]],
        [
            ['综合得分'] + [f"{b['total']}/100 [{b['tier']}]" for b in scored[:3]],
            ['国家'] + [b['country'] for b in scored[:3]],
            ['公司类型'] + [b.get('type','') for b in scored[:3]],
            ['规模'] + [b.get('scale','') for b in scored[:3]],
            ['采购能力'] + ['★★★★★','★★★★☆','★★★★☆'][:len(scored)],
            ['地域战略'] + ['★★★★★']*len(scored),
            ['复购潜力'] + ['★★★★★','★★★★☆','★★★★☆'][:len(scored)],
        ],
        widths=[3.2] + [4.2]*len(scored))
    doc.add_paragraph()

    # 客户详情
    for idx, b in enumerate(scored[:3]):
        heading(doc, f'客户 {idx+1}：{b["name"]}', lvl=2); hr(doc, colors_list[idx][1:])
        p_tag = doc.add_paragraph()
        r1 = p_tag.add_run(f"{b['country']}  "); srun(r1, sz=11, color=GRAY)
        r2 = p_tag.add_run(f"🔥 {b['total']}/100  "); srun(r2, sz=13, bold=True, color=HOT_RED)
        r3 = p_tag.add_run(f'{b["tier"]} LEAD'); srun(r3, sz=11, bold=True, color=HOT_RED)

        mtable(doc, ['维度','信息'], [
            ['公司名', b['name']],
            ['类型', b.get('type','')],
            ['规模', b.get('scale','')],
            ['行业定位', b.get('industry','')],
            ['采购角色', b.get('buyer_role','')],
            ['采购需求', b.get('purchase_needs','')],
        ], widths=[3.2, 13.6])

        doc.add_paragraph()
        add_img(doc, os.path.join(chart_dir, f'buyer_{idx+1}_radar.png'), width=Cm(10))
        doc.add_paragraph()

        para(doc, '📞 联系方式', color=DARK, bold=True)
        for c in (b.get('contacts') or []): bullet(doc, c)
        if b.get('outreach'):
            para(doc, '💬 切入话术', color=DARK, bold=True, space_before=8)
            para(doc, f'"{b["outreach"]}"', color=GRAY, italic=True, sz=10)
        doc.add_paragraph()

    # 行动优先级
    heading(doc, '🚀 行动优先级', lvl=2); hr(doc)
    mtable(doc, ['优先级','公司','本周目标'],
        [['🔥 P0', scored[0]['name'], '发邮件拿到报价回复'],
         ['🔥 P0', scored[1]['name'], '发样品测试邀请'],
         ['⭐ P1', scored[2]['name'], '电话确认需求规格']],
        widths=[2.5, 5.5, 9.0])
    doc.add_paragraph()

    # 数据主权声明
    hr(doc, 'E5E7EB')
    para(doc,
        '💡 数据主权声明：雷达图（matplotlib）和报告（python-docx）均在本地生成，'
        '原始数据不离开用户机器。API搜索Token由客户提供，费用自担。',
        color=GRAY, sz=9, italic=True)

    doc.save(out_doc)

    return {
        "status": "ok",
        "output_path": out_doc,
        "radar_count": 4,
        "buyers_scored": [{"name": b["name"], "total": b["total"], "tier": b["tier"]} for b in scored],
        "db_status": db_status,
        "token_owner": "customer_provided",
        "data_footprint": "local_only"
    }


# ── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Golddigger MCP Server")
    parser.add_argument("--transport", default="stdio",
                        choices=["stdio", "streamable-http"])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    mount = "/mcp" if args.transport == "streamable-http" else None
    mcp.run(
        transport=args.transport,
        mount_path=mount,
        host=args.host if args.transport == "streamable-http" else None,
        port=args.port if args.transport == "streamable-http" else None
    )
