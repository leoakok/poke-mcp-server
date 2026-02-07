#!/usr/bin/env python3
import os
import requests
from typing import Annotated, Optional, Literal, List, Dict, Any
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
        
        if not response.ok:
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text
            return {
                "error": f"Request failed with status {response.status_code}",
                "detail": error_detail
            }
        
        return response.json()
    
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}


def get_messages(
    ctx: Context,
    range: Annotated[
        Optional[Literal["today", "this week", "this month", "all"]],
        "Time period to filter messages — 'today', 'this week', 'this month', or 'all' for complete history"
    ] = "all"
) -> dict:
    """Retrieve messages, optionally filtered by a time range."""
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


def get_location_log(
    ctx: Context,
    limit: Annotated[
        Optional[int],
        "Number of recent log entries to return (e.g. 1 for latest, 10 for last ten). Leave empty to get all entries."
    ] = None
) -> dict:
    """Retrieve recent entries from the location log. Each entry is an automatic check-in recorded every 30 minutes."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    table_id = os.environ.get("AIRTABLE_LOCATION_LOGS_TABLE_ID")
    if not table_id:
        return {"error": "Location log is not configured."}
    
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
        "logs": records,
        "count": len(records),
    }


def update_location_log(
    ctx: Context,
    log_id: Annotated[str, "The record ID of the location log entry to update"],
    place_id: Annotated[str, "The record ID of the saved place to link to this log entry"]
) -> dict:
    """Link a location log entry to a saved place. Use this to match a location check-in with an existing place."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    table_id = os.environ.get("AIRTABLE_LOCATION_LOGS_TABLE_ID")
    if not table_id:
        return {"error": "Location log is not configured."}
    
    data = airtable_request(
        token=token,
        table_id=table_id,
        method="PATCH",
        endpoint=f"/{log_id}",
        json_data={"fields": {"place": [place_id]}}
    )
    
    if "error" in data:
        return {"error": data["error"]}
    
    return {
        "log": data,
        "message": "Location log linked to place successfully."
    }


def create_place(
    ctx: Context,
    name: Annotated[str, "Name of the place (e.g. 'Blue Bottle Coffee', 'WeWork Shibuya')"],
    address: Annotated[str, "Full address of the place"],
    type: Annotated[List[str], "One or more categories for the place (e.g. ['cafe'], ['cafe', 'coworking']). Use get_place_types to see available values."],
    rating: Annotated[Optional[int], "Rating from 1 to 5"] = None,
    notes: Annotated[Optional[str], "Personal notes about the place, e.g. 'great wifi', 'quiet area', 'good for working'"] = None
) -> dict:
    """Save a new place the user has visited or wants to remember."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    table_id = os.environ.get("AIRTABLE_PLACES_TABLE_ID")
    if not table_id:
        return {"error": "Places table is not configured."}
    
    fields = {
        "name": name,
        "address": address,
        "type": type,
    }
    
    if rating is not None:
        fields["rating"] = rating
    if notes is not None:
        fields["notes"] = notes
    
    data = airtable_request(
        token=token,
        table_id=table_id,
        method="POST",
        json_data={"fields": fields, "typecast": True}
    )
    
    if "error" in data:
        return {"error": data["error"]}
    
    return {
        "place": data,
        "message": f"Saved '{name}' successfully."
    }


def update_place(
    ctx: Context,
    place_id: Annotated[str, "The record ID of the place to update"],
    type: Annotated[Optional[List[str]], "Updated categories for the place (e.g. ['cafe', 'coworking']). Use get_place_types to see available values."] = None,
    rating: Annotated[Optional[int], "Updated rating from 1 to 5"] = None,
    notes: Annotated[Optional[str], "Updated personal notes about the place"] = None
) -> dict:
    """Update an existing saved place. Only the provided fields will be updated, the rest will remain unchanged."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    table_id = os.environ.get("AIRTABLE_PLACES_TABLE_ID")
    if not table_id:
        return {"error": "Places table is not configured."}
    
    fields = {}
    if type is not None:
        fields["type"] = type
    if rating is not None:
        fields["rating"] = rating
    if notes is not None:
        fields["notes"] = notes
    
    if not fields:
        return {"error": "No fields provided to update."}
    
    data = airtable_request(
        token=token,
        table_id=table_id,
        method="PATCH",
        endpoint=f"/{place_id}",
        json_data={"fields": fields, "typecast": True}
    )
    
    if "error" in data:
        return {"error": data["error"]}
    
    return {
        "place": data,
        "message": "Place updated successfully."
    }


def get_places(
    ctx: Context,
    type: Annotated[
        Optional[List[str]],
        "Filter by one or more place categories (e.g. ['cafe'] or ['cafe', 'coworking']). Use get_place_types to see available values. Leave empty for all types."
    ] = None,
    rating: Annotated[
        Optional[int],
        "Minimum rating to filter by (1-5). Only places with this rating or higher will be returned."
    ] = None,
    address: Annotated[
        Optional[str],
        "Search by address (partial match). For example 'Shibuya' will match any place with Shibuya in its address."
    ] = None
) -> dict:
    """Search saved places, optionally filtered by type(s), minimum rating, and/or address."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    table_id = os.environ.get("AIRTABLE_PLACES_TABLE_ID")
    if not table_id:
        return {"error": "Places table is not configured."}
    
    params = {}
    
    # Build filter formula
    filters = []
    if type:
        if len(type) == 1:
            filters.append(f"LOWER({{type}}) = LOWER('{type[0]}')")
        else:
            type_conditions = ", ".join(f"LOWER({{type}}) = LOWER('{t}')" for t in type)
            filters.append(f"OR({type_conditions})")
    if rating:
        filters.append(f"{{rating}} >= {rating}")
    if address:
        filters.append(f"FIND(LOWER('{address}'), LOWER({{address}}))")
    
    if filters:
        params["filterByFormula"] = "AND(" + ", ".join(filters) + ")" if len(filters) > 1 else filters[0]
    
    data = airtable_request(token=token, table_id=table_id, method="GET", params=params)
    
    if "error" in data:
        return {"error": data["error"]}
    
    records = data.get("records", [])
    
    return {
        "places": records,
        "count": len(records),
    }


def get_place_types(ctx: Context) -> dict:
    """Get all available place types/categories."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    base_id = os.environ.get("AIRTABLE_BASE_ID")
    places_table_id = os.environ.get("AIRTABLE_PLACES_TABLE_ID")
    
    if not base_id or not places_table_id:
        return {"error": "Server configuration is incomplete."}
    
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {
        "Authorization": f"Bearer {token}",
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Find the places table and extract the type field options
        for table in data.get("tables", []):
            if table.get("id") == places_table_id:
                for field in table.get("fields", []):
                    if field.get("name", "").lower() == "type":
                        options = field.get("options", {}).get("choices", [])
                        types = [opt.get("name") for opt in options]
                        return {"types": types, "count": len(types)}
        
        return {"error": "Could not find place types."}
    
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
