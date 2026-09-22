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
| `health_check` | Check API status & DB quota | External API call |
| `search_leads` | Search 10M+ global companies | External API call |
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
export GOLDIGGER_API_KEY="gd_your_key_here"
export GOLDIGGER_HOST="https://golddigger.gold"
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
      "command": "uvicorn",
      "args": ["server:app", "--host", "0.0.0.0", "--port", "8080"],
      "env": {
        "GOLDIGGER_API_KEY": "gd_your_key_here"
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

| Plan | Leads | Rate Limit | Period |
|------|-------|------------|--------|
| Free | 3 previews | 10/day | Forever |
| Super | 50,000 | 100/day | 90 days |
| Premium | 1,000,000 | Unlimited | 365 days |

Get your key at [https://golddigger.gold](https://golddigger.gold)

## License

MIT — SassumiX 2026
