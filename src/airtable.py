#!/usr/bin/env python3
import os
import requests
from typing import Optional, Literal, Dict, Any
from fastmcp import Context


def airtable_request(
    token: str,
    table_id: str,
    method: str = "GET",
    endpoint: str = "",
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generic function to make authenticated API requests.
    
    Args:
        token: Bearer token (passed from client request)
        table_id: Target table identifier
        method: HTTP method (GET, POST, PATCH, DELETE)
        endpoint: Additional endpoint path (e.g., "/recXXX")
        params: Optional query parameters
        json_data: Optional JSON body for POST/PATCH requests
    
    Returns:
        dict: Response data or error
    """
    base_id = os.environ.get("AIRTABLE_BASE_ID")
    
    if not token:
        return {"error": "No authentication token provided."}
    
    if not base_id or not table_id:
        return {"error": "Server configuration is incomplete."}
    
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_data
        )
        response.raise_for_status()
        
        return response.json()
    
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}


def get_messages(
    ctx: Context,
    range: Optional[Literal["today", "this week", "this month", "all"]] = "all"
) -> dict:
    """
    Retrieve messages, optionally filtered by a time range.
    
    Args:
        ctx: FastMCP context (injected automatically)
        range: Time range to filter by — "today", "this week", "this month", or "all" (default: "all")
    
    Returns:
        dict: Messages sorted by most recent first
    """
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    table_id = os.environ.get("AIRTABLE_MESSAGES_TABLE_ID")
    if not table_id:
        return {"error": "Messages table is not configured."}
    
    params = {
        "view": range,
        "sort[0][field]": "timestamp",
        "sort[0][direction]": "desc"
    }
    
    data = airtable_request(token=token, table_id=table_id, method="GET", params=params)
    
    if "error" in data:
        return {"error": data["error"], "range": range}
    
    return {
        "range": range,
        "messages": data.get("records", []),
        "count": len(data.get("records", [])),
    }


def get_location(
    ctx: Context,
    limit: Optional[int] = None
) -> dict:
    """
    Retrieve the most recent location records from the location log.
    
    Args:
        ctx: FastMCP context (injected automatically)
        limit: Number of recent location records to return (e.g. 1, 2, 10). Leave empty to get all.
    
    Returns:
        dict: Location records sorted by most recent first
    """
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    table_id = os.environ.get("AIRTABLE_LOCATION_LOGS_TABLE_ID")
    if not table_id:
        return {"error": "Location table is not configured."}
    
    params = {
        "sort[0][field]": "timestamp",
        "sort[0][direction]": "desc"
    }
    
    if limit:
        params["maxRecords"] = str(limit)
    
    data = airtable_request(token=token, table_id=table_id, method="GET", params=params)
    
    if "error" in data:
        return {"error": data["error"]}
    
    records = data.get("records", [])
    
    return {
        "locations": records,
        "count": len(records),
    }
