#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_headers
from airtable import (
    get_messages, get_location_log, update_location_log,
    create_place, update_place, get_places, get_parameter_options,
    get_contacts, create_contact, update_contact, delete_entry, get_birthdays
)

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
    description="Get entries from the user's location log. These are automatic check-ins recorded every 30 minutes. Set limit=1 for the latest check-in, limit=10 for the last 10, or leave empty for full history. Filter by place_id to see when the user was at a specific place, or by status='warning' to quickly find entries that need attention. Each log entry has a record ID that can be used with update_location_log to link it to a saved place or mark it as transit."
)(get_location_log)

mcp.tool(
    description="Update a location log entry. Either link it to a saved place (provide place_id from get_places) or mark it as transit (set transit=true). When marking as transit, leave place_id empty. Only mark as transit if you are confident the user was traveling — if unsure, ask the user first. Requires the log entry's record ID (from get_location_log)."
)(update_location_log)

mcp.tool(
    description="Save a new place the user has visited or wants to remember. Requires a name, address, and type (e.g. cafe, restaurant, coworking, bar, park, gym). Optionally include a rating (1-5) and personal notes. Before saving, consider using get_places to check if the place already exists."
)(create_place)

mcp.tool(
    description="Update an existing saved place. Use the place's record ID (from get_places) and provide any combination of name, address, type, rating, or notes to update. Only the provided fields will change, everything else stays the same."
)(update_place)

mcp.tool(
    description="Search the user's saved places. Filter by name, one or multiple types at once (e.g. ['cafe', 'coworking'] to find cafes and coworking spaces together), minimum rating to find top-rated spots, or address. Use this to suggest places the user has been to before, check if a place is already saved, or recommend a place based on what they need. Call get_parameter_options(source='place', parameter='type') first to see the available type values for filtering."
)(get_places)

mcp.tool(
    description="Get available options for a parameter. First pick the source ('place' or 'contact'), then the parameter name (e.g. 'type' for place categories, 'relationship' or 'location' for contacts). Call this before creating or filtering to use the correct existing values and avoid duplicates."
)(get_parameter_options)

# Contact tools
mcp.tool(
    description="Search the user's contacts. Filter by name, nickname, location (city for Turkey, country for abroad), sex, relationship type (e.g. 'friend', 'colleague', 'family'), or company. Returns all contacts if no filters are provided. Use this to look up someone's details, find contacts in a specific location, list contacts by relationship, or find people at a company."
)(get_contacts)

mcp.tool(
    description="Save a new contact. Only the name is required, all other fields (nickname, birthday, location, sex, relationship, phone, email, company, linkedin, website, notes) are optional. Before saving, consider using get_contacts to check if the person already exists."
)(create_contact)

mcp.tool(
    description="Update an existing contact. Use the contact's record ID (from get_contacts) and provide any fields to update. Only the provided fields will change, everything else stays the same."
)(update_contact)

mcp.tool(
    description="Permanently delete a record. Pick the source ('place' or 'contact') and provide the record ID. Get the record ID from the corresponding search tool (get_places or get_contacts). Use with caution — this cannot be undone."
)(delete_entry)

mcp.tool(
    description="Check for upcoming birthdays. Returns contacts grouped into three lists: 'today' for birthdays today, 'this_week' for birthdays in the next 7 days, and 'this_month' for all birthdays this month. Use this proactively to remind the user about birthdays."
)(get_birthdays)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"

    print(f"Starting FastMCP server on {host}:{port}")
    mcp.run(transport="http", host=host, port=port)
