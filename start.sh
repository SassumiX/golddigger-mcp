#!/bin/bash
# Golddigger MCP Server — Start Script
# Usage: ./start.sh [stdio|http] [port]
#
# Claude Desktop (macOS ~/Library/Application Support/Claude/claude_desktop_config.json):
#   "golddigger": {
#     "command": "python3",
#     "args": ["/FULL/PATH/TO/golddigger-mcp/server.py", "--transport", "stdio"]
#   }
#
# Cline (cline_mcp_settings.json):
#   "mcpServers": {
#     "golddigger": {
#       "command": "uvicorn",
#       "args": ["server:app", "--host", "0.0.0.0", "--port", "8080"]
#     }
#   }

TRANSPORT=${1:-stdio}
PORT=${2:-8080}

cd "$(dirname "$0")"

if [ "$TRANSPORT" = "http" ]; then
    echo "[Golddigger MCP] Starting HTTP mode on :$PORT"
    uvicorn server:app --host 0.0.0.0 --port $PORT
else
    echo "[Golddigger MCP] Starting stdio mode..."
    python3 server.py --transport stdio
fi
