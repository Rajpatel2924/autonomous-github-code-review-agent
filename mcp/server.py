from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from app.config import get_settings
from mcp.tools import MCPTools, tool_schemas


async def dispatch(method: str, params: dict[str, Any]) -> Any:
    tools = MCPTools(get_settings())
    if method == "tools/list":
        return {"tools": tool_schemas()}
    if method == "tools/call":
        name = params["name"]
        arguments = params.get("arguments", {})
        handler = getattr(tools, name)
        return await handler(**arguments)
    raise ValueError(f"Unsupported MCP method: {method}")


async def serve_stdio() -> None:
    for line in sys.stdin:
        request = json.loads(line)
        try:
            result = await dispatch(request["method"], request.get("params", {}))
            response = {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
        except Exception as exc:
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32000, "message": str(exc)},
            }
        print(json.dumps(response), flush=True)


def main() -> None:
    asyncio.run(serve_stdio())


if __name__ == "__main__":
    main()
