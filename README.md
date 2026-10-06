# Golddigger MCP Server

> B2B Lead Intelligence API — search, enrich & score 10M+ global companies from any MCP-compatible client.

[![MCP Server](https://img.shields.io/badge/MCP-Server-green)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Data Sovereignty](https://img.shields.io/badge/Data-Local%20Only-blue)](https://golddigger.gold)

## What is this?

A Model Context Protocol (MCP) server that wraps the [Golddigger API](https://golddigger.gold) — giving AI assistants (Claude, Cline, Cursor, etc.) the ability to search, enrich, and score B2B leads in real time.

**4 tools exposed:**

| Tool | Description | Data Flow |
|------|-------------|-----------|
| `health_check` | Service health + **real** account quota (`/api/health` + `/api/quota`) | External API call |
| `check_quota` | 挖客前预检：服务端剩余 + 本地每日预算账本 | External API call |
| `search_leads` | Search by buyer-intent keyword + country (`POST /api/search`) | External API call, **1 quota each** |
| `score_lead` | Six-dimension quality scoring | **Local only** |
| `generate_report` | Full radar chart + Word report | **Local only** |

## Data Sovereignty

- ✅ **Report generation**: 100% local (matplotlib + python-docx). No data leaves the user's machine.
- ✅ **Scoring**: Pure local computation — six-dimension model runs on-device.
- ⚠️ **Search**: Calls Golddigger API. Customer provides their own API key — costs borne by customer.

## Installation

```bash
git clone https://github.com/SassumiX/golddigger-mcp.git
cd golddigger-mcp
pip install -r requirements.txt
```

## Configuration

```bash
# Set your Golddigger API key (customer provides their own)
export GOLDDIGGER_API_KEY="gd_your_key_here"
export GOLDDIGGER_HOST="https://golddigger.gold"   # 可选
export GOLDDIGGER_DAILY_BUDGET=20     # 可选：本地软预算，默认 20
export GOLDDIGGER_QUOTA_RESERVE=2     # 可选：剩余低于此值不再自动搜
```

> **Token billing**: The `search_leads` tool uses the customer's API key. Report generation is free (no external API calls).

## Usage

### Claude Desktop (macOS)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "golddigger": {
      "command": "python3",
      "args": ["/FULL/PATH/TO/golddigger-mcp/server.py", "--transport", "stdio"]
    }
  }
}
```

Restart Claude Desktop.

### Cline / Other MCP Clients

```json
{
  "mcpServers": {
    "golddigger": {
      "command": "python3",
      "args": ["/FULL/PATH/TO/golddigger-mcp/server.py", "--transport", "stdio"],
      "env": {
        "GOLDDIGGER_API_KEY": "gd_your_key_here"
      }
    }
  }
}
```

### HTTP Endpoint

```bash
python3 server.py --transport streamable-http --port 8080
```

## MCP Tools

### generate_report（商业核心工具）

```
用户说："出客户画像报告"
Agent 自动调用 → 生成本地 .docx 文件
```

```python
# Agent 调用示例
result = golddigger.generate_report(
    company_name="cnpulk.com",
    product_desc="DTH drill bits, rock drilling tools",
    buyers=[
        {
            "name": "Afrimat Limited",
            "country": "南非",
            "industry": "Mining",
            "has_contact": True,
            "scale": "上市矿业集团",
            "buyer_role": "Contract Mining总监",
            "purchase_needs": "DTH钻头，持续消耗",
            "contacts": ["pierre@afrimat.co.za · +27 82 411 7475"],
            "outreach": "We offer 20-30% cost savings on DTH bits."
        },
        # ... 2 more buyers
    ],
    api_key="gd_customer_own_key"   # 客户自己的Key，费用自担
)
# result["output_path"] → 本地 .docx 文件路径
```

### score_lead

```python
result = golddigger.score_lead(
    company="Afrimat Limited",
    country="南非",
    industry="Mining",
    has_contact=True,
    scale="上市矿业集团",
    note="并购整合期"
)
# result["total"] = 91, result["tier"] = "HOT"
```

## Pricing

| Plan | 每日配额 |
|------|---------|
| Free | **20 次/天**（2026-10-06 由 `GET /api/quota` 实测得出，00:00 UTC 重置） |
| Paid | 见 [https://golddigger.gold](https://golddigger.gold) |

> ⚠️ 别信任何写死的配额数字，**以 `check_quota` 的实时返回为准**。
> Get your key at [https://golddigger.gold](https://golddigger.gold)

## 已知问题 / 端点实测（2026-10-06）

| 端点 | 状态 |
|---|---|
| `GET /api/health` | ✅ |
| `GET /api/quota` | ✅ 真实配额端点（旧代码用的 `/api/tenants/me` 从未上线） |
| `GET /api/leads` | ✅ |
| `POST /api/search` | ⚠️ **当前 500**，站点侧故障，重试无用（5xx 不扣配额） |
| `GET /api/leads/search` | ❌ 从未部署（旧 `search_leads` 打的就是这个，恒 404） |

## 配额纪律（Agent 必读）

1. **批量挖客前先调 `check_quota`**，别让 Agent 自由发挥地循环搜索。
2. `search_leads(dry_run=True)` 可以预演请求，不烧配额 —— 先批量预演，再挑着真跑。
3. 本地预算账本写在 `~/.golddigger/search_budget.json`，默认上限 20/天，按天重置。
4. 剩余 ≤ 2 次（`GOLDDIGGER_QUOTA_RESERVE`）时 `search_leads` 直接拒绝发起，留额度给人工决策。
5. 优先级：**采购角色词 > 产品细分词 > 泛需求词**。泛需求词最费额度、命中率最低。

## License

MIT — SassumiX 2026
