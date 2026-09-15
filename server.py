#!/usr/bin/env python3
"""
Golddigger MCP Server — B2B Lead Intelligence API
Pubic repository: https://github.com/SassumiX/golddigger-mcp

Usage:
  # Claude Desktop (macOS)
  "golddigger": {
    "command": "python3",
    "args": ["/path/to/server.py", "--transport", "stdio"]
  }

  # Cline / other HTTP clients
  "golddigger": {
    "command": "uvicorn",
    "args": ["server:app", "--host", "0.0.0.0", "--port", "8080"]
  }
"""
import os, json, argparse
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Golddigger",
    description="B2B Lead Intelligence API — search, enrich & score leads from 10M+ global companies database"
)

GOLDIGGER_HOST = os.getenv("GOLDIGGER_HOST", "https://golddigger.geodinvest.com")
HEADERS = {
    "X-API-KEY": os.getenv("GOLDIGGER_API_KEY", "golddigger_2024"),
    "Content-Type": "application/json"
}

# ── MCP Tools ───────────────────────────────────────────────────────────────

@mcp.tool()
def search_leads(keyword: str, limit: int = 20) -> dict:
    """
    Search the Golddigger B2B lead database.
    
    Args:
        keyword: Search term — company name, industry, product keyword, or country
        limit: Max results to return (default 20, max 100)
    
    Returns:
        List of leads with company, website, email, country, industry, products
    """
    import urllib.request, urllib.parse
    
    params = urllib.parse.urlencode({"q": keyword, "limit": min(limit, 100)})
    url = f"{GOLDIGGER_HOST}/api/leads/search?{params}"
    
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e), "leads": [], "count": 0}

@mcp.tool()
def enrich_company(company: str) -> dict:
    """
    Enrich a company record with full contact details.
    
    Args:
        company: Company name (partial match supported)
    
    Returns:
        Full lead record: phone, email, address, industry, source, found_at
    """
    import urllib.request, urllib.parse
    
    params = urllib.parse.urlencode({"company": company})
    url = f"{GOLDIGGER_HOST}/api/leads/enrich?{params}"
    
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def score_lead(company: str, source: str = "") -> dict:
    """
    Score a lead's quality (hot/warm/cold) based on data source signals.
    
    Args:
        company: Company name
        source: Data source hint (e.g. "firecrawl", "anysearch", "multi-source")
    
    Returns:
        Score (0-100), tier (hot/warm/cold), company name
    """
    import urllib.request, urllib.parse
    
    params = urllib.parse.urlencode({"company": company, "source": source})
    url = f"{GOLDIGGER_HOST}/api/leads/score?{params}"
    
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

# ── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Golddigger MCP Server")
    parser.add_argument("--transport", default="stdio",
                        choices=["stdio", "streamable-http"],
                        help="MCP transport protocol")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Host for HTTP transport")
    parser.add_argument("--port", type=int, default=8080,
                        help="Port for HTTP transport")
    args = parser.parse_args()

    mount = "/mcp" if args.transport == "streamable-http" else None
    mcp.run(transport=args.transport, mount_path=mount,
            host=args.host if args.transport == "streamable-http" else None,
            port=args.port   if args.transport == "streamable-http" else None)
