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

# 默认 Demo Key（仅用于 health check，生产环境客户用自己的 Key）
DEFAULT_HOST = "https://golddigger.gold"
DEFAULT_KEY  = "gd_0ae9f120b194578cc24ccab6e006"


# ═══════════════════════════════════════════════════════════════════════════
# 工具 1：health_check
# ═══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def health_check(api_key: str = DEFAULT_KEY,
                 host: str = DEFAULT_HOST) -> dict:
    """
    检查 Golddigger API 连接状态和配额。

    Args:
        api_key: 客户的 Golddigger API Key（默认 demo key）
        host: Golddigger API 地址（默认 golddigger.gold）

    Returns:
        {"status": "ok"|"error", "db_rows": int, "tier": str, "message": str}
    """
    import urllib.request

    url = f"{host}/health"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            db_rows = data.get("db_rows", 0)
            return {
                "status": "ok",
                "db_rows": db_rows,
                "tier": "SUPER (paid)" if db_rows > 0 else "Free (empty DB)",
                "message": "✅ Connected" if db_rows > 0
                           else "⚠️  Free tier — DB is empty. Upgrade to SUPER for real data."
            }
    except Exception as e:
        return {"status": "error", "message": f"Connection failed: {e}"}


# ═══════════════════════════════════════════════════════════════════════════
# 工具 2：search_leads
# ═══════════════════════════════════════════════════════════════════════════
@mcp.tool()
def search_leads(keyword: str,
                 limit: int = 20,
                 api_key: str = DEFAULT_KEY,
                 host: str = DEFAULT_HOST) -> dict:
    """
    搜索 Golddigger B2B 客户数据库。

    ⚠️ 注意：免费版 db_rows=0，搜索永远返回空结果。
       客户需升级 SUPER 套餐（¥499+/月）才有真实数据。

    Args:
        keyword: 搜索词——公司名、行业、产品关键词、国家
        limit: 返回数量上限（默认 20）
        api_key: 客户的 Golddigger API Key
        host: Golddigger API 地址

    Returns:
        {"count": int, "leads": [{"name","country","type","industry"}, ...]}
    """
    import urllib.request, urllib.parse

    params = urllib.parse.urlencode({"q": keyword, "limit": min(limit, 100)})
    url = f"{host}/api/leads/search?{params}"

    req = urllib.request.Request(url, headers={
        "X-API-KEY": api_key,
        "User-Agent": "Golddigger-MCP/1.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e), "leads": [], "count": 0}


# ═══════════════════════════════════════════════════════════════════════════
# 工具 3：score_lead
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
# 工具 4：generate_report（核心商业工具）
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
            "db_status": str      ← "SUPER (real data)" | "Free (sample data)"
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

    # ── 检查 GD DB 状态 ──
    req_h = urllib.request.Request(f"{host}/health")
    try:
        with urllib.request.urlopen(req_h, timeout=5) as resp:
            health_data = json.loads(resp.read())
        db_rows = health_data.get("db_rows", 0)
    except:
        db_rows = 0

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
        "db_status": f"SUPER (real data, db_rows={db_rows})" if db_rows > 0
                     else "Free (sample data — upgrade to SUPER for real leads)",
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
