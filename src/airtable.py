#!/usr/bin/env python3
import os
import requests
from typing import Optional, Literal, Dict, Any

def airtable_request(
    method: str = "GET",
    endpoint: str = "",
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generic function to make Airtable API requests with authentication.
    
    Args:
        method: HTTP method (GET, POST, PATCH, DELETE)
        endpoint: API endpoint path (appended to base table URL, e.g., "/recXXX")
        params: Optional query parameters
        json_data: Optional JSON body for POST/PATCH requests
    
    Returns:
        dict: Response data or error
    """
    # Get configuration from environment variables
    token = os.environ.get("AIRTABLE_TOKEN")
    base_id = os.environ.get("AIRTABLE_BASE_ID")
    table_id = os.environ.get("AIRTABLE_TABLE_ID")
    
    if not token:
        return {"error": "Airtable token not provided. Set AIRTABLE_TOKEN environment variable."}
    
    if not base_id or not table_id:
        return {"error": "Missing AIRTABLE_BASE_ID or AIRTABLE_TABLE_ID environment variables."}
    
    # Construct API URL
    url = f"https://api.airtable.com/v0/{base_id}/{table_id}{endpoint}"
    
    # Set up headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Make API request
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
        return {"error": f"Airtable API request failed: {str(e)}"}


def get_messages(
    range: Optional[Literal["today", "this week", "this month", "all"]] = "all"
) -> dict:
    """
    Get messages from Airtable, optionally filtered by time range and sorted descending by timestamp.
    
    Args:
        range: Time range filter - can be "today", "this week", "this month", or "all" (default: "all")
    
    Returns:
        dict: Messages sorted descending by timestamp
    """
    # Build query parameters with view
    params = {
        "view": range,
        "sort[0][field]": "timestamp",
        "sort[0][direction]": "desc"
    }
    
    # Make API request using generic function
    data = airtable_request(method="GET", params=params)
    
    # Check for error
    if "error" in data:
        return {"error": data["error"], "range": range}
    
    return {
        "range": range,
        "messages": data.get("records", []),
        "count": len(data.get("records", [])),
        "sort_order": "descending",
        "sort_by": "timestamp"
    }