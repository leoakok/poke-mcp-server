#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_headers
from airtable import get_messages

# Load environment variables from .env file
load_dotenv()

# Middleware to log all incoming HTTP headers
class HeaderLoggerMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        headers = get_http_headers() or {}
        print(f"\n=== {context.method} ===")
        for key, value in headers.items():
            print(f"  {key}: {value}")
        print("========================\n")
        return await call_next(context)

mcp = FastMCP(name="Poke MCP Server", instructions="An MCP server for Poke")

# Add middleware
mcp.add_middleware(HeaderLoggerMiddleware())


@mcp.tool(description="Greet a user by name with a welcome message from the MCP server")
def greet(name: str) -> str:
    return f"Hello, {name}! Welcome to our sample MCP server running on Heroku!"


@mcp.tool(
    description="Get information about the MCP server including name, version, environment, and Python version"
)
def get_server_info() -> dict:
    return {
        "server_name": "Sample MCP Server",
        "version": "1.0.0",
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "python_version": os.sys.version.split()[0],
    }


# Register message tools
mcp.tool(
    description="Get messages, optionally filtered by time range: today, this week, this month, or all. Returns messages sorted by most recent first."
)(get_messages)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"

    print(f"Starting FastMCP server on {host}:{port}")
    mcp.run(transport="http", host=host, port=port)
