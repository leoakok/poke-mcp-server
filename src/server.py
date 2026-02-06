#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_headers
from airtable import get_messages, get_location

# Load environment variables from .env file
load_dotenv()

# Middleware to log headers and extract bearer token for Airtable
class HeaderLoggerMiddleware(Middleware):
    async def on_message(self, context: MiddlewareContext, call_next):
        headers = get_http_headers() or {}
        print(f"\n=== {context.method} ===")
        for key, value in headers.items():
            print(f"  {key}: {value}")
        print("========================\n")

        # Extract bearer token and store it in context state
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            if context.fastmcp_context:
                context.fastmcp_context.set_state("airtable_token", token)

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


# Register tools
mcp.tool(
    description="Retrieve the user's messages. Use the 'range' parameter to filter by time period: 'today' for today's messages, 'this week' for the current week, 'this month' for the current month, or 'all' for the complete history. Messages are always returned with the most recent first."
)(get_messages)

mcp.tool(
    description="Get the user's current or recent locations. Location is logged automatically every 30 minutes. Set limit=1 to get the current location, limit=10 for the last 10 check-ins, or leave limit empty to retrieve the full location history. Results are ordered from most recent to oldest."
)(get_location)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"

    print(f"Starting FastMCP server on {host}:{port}")
    mcp.run(transport="http", host=host, port=port)
