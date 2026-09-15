# Golddigger MCP Server

> B2B Lead Intelligence API — search, enrich & score 10M+ global companies from any MCP-compatible client.

[![MCP Server](https://img.shields.io/badge/MCP-Server-green)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![B2B Data](https://img.shields.io/badge/Data-10M%2B%20Companies-blue)](https://golddigger.gold)

## What is this?

A Model Context Protocol (MCP) server that wraps the [Golddigger API](https://golddigger.gold) — giving AI assistants (Claude, Cline, Cursor, etc.) the ability to search, enrich, and score B2B leads in real time.

**3 tools exposed:**

| Tool | Description |
|------|-------------|
| `search_leads(keyword, limit)` | Search 10M+ global companies by name, industry, product, country |
| `enrich_company(company)` | Get full contact details: email, phone, address, source |
| `score_lead(company, source)` | Rate lead quality hot/warm/cold (0-100 score) |

## Installation

```bash
git clone https://github.com/SassumiX/golddigger-mcp.git
cd golddigger-mcp
pip install -r requirements.txt
```

## Configuration

Set your API key as an environment variable:

```bash
export GOLDIGGER_API_KEY="golddigger_2024"   # Get yours at https://golddigger.gold
export GOLDIGGER_HOST="https://golddigger.geodinvest.com"
```

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
        "GOLDIGGER_API_KEY": "golddigger_2024"
      }
    }
  }
}
```

### HTTP Endpoint

```bash
./start.sh http 8080
# Or directly
python3 server.py --transport streamable-http --port 8080
```

## API Endpoints (Direct REST)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/leads/search?q=&limit=` | Search leads |
| GET | `/api/leads/enrich?company=` | Enrich company |
| GET | `/api/leads/score?company=&source=` | Score lead |

Base URL: `https://golddigger.geodinvest.com`

## Pricing

| Plan | Leads | Rate Limit | Period |
|------|-------|------------|--------|
| Free | 3 previews | 10/day | Forever |
| Super | 50,000 | 100/day | 90 days |
| Premium | 1,000,000 | Unlimited | 365 days |
| Buyout | Self-host + FDE setup | — | — |

Get your key at [https://golddigger.gold](https://golddigger.gold)

## License

MIT — SassumiX 2026
