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


def fetch_field_options(token: str, table_id: str, field_name: str) -> List[str]:
    """
    Fetch the available select/multi-select options for a field from the schema API.
    Returns a list of option names, or an empty list if fetching fails.
    """
    base_id = os.environ.get("AIRTABLE_BASE_ID")
    if not token or not base_id or not table_id:
        return []
    
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        for table in data.get("tables", []):
            if table.get("id") == table_id:
                for field in table.get("fields", []):
                    if field.get("name", "").lower() == field_name.lower():
                        options = field.get("options", {}).get("choices", [])
                        return [opt.get("name") for opt in options]
        return []
    except Exception:
        return []


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
    ] = None,
    place_id: Annotated[
        Optional[str],
        "Filter by a saved place's record ID (from get_places). Returns only log entries linked to that place — useful for checking when the user was last at a specific place."
    ] = None,
    status: Annotated[
        Optional[Literal["ok", "warning"]],
        "Filter by log status — 'ok' for normal entries, 'warning' for entries that need attention. Use 'warning' to quickly find problematic check-ins."
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
    
    filters = []
    if place_id:
        filters.append(f"FIND('{place_id}', ARRAYJOIN({{place}}, ','))")
    if status:
        filters.append(f"{{status}} = '{status}'")
    
    if filters:
        params["filterByFormula"] = "AND(" + ", ".join(filters) + ")" if len(filters) > 1 else filters[0]
    
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
    place_id: Annotated[
        Optional[str],
        "The record ID of the saved place to link to this log entry (from get_places). Leave empty if marking as transit."
    ] = None,
    transit: Annotated[
        Optional[bool],
        "Set to true to mark this log entry as in-transit (e.g. commuting, traveling between places). Only mark as transit if you are sure — if unsure, ask the user first. When marking as transit, leave place_id empty."
    ] = None
) -> dict:
    """Update a location log entry. Link it to a saved place, or mark it as transit. Provide at least one of place_id or transit."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    table_id = os.environ.get("AIRTABLE_LOCATION_LOGS_TABLE_ID")
    if not table_id:
        return {"error": "Location log is not configured."}
    
    fields = {}
    if place_id is not None:
        fields["place"] = [place_id]
    if transit is not None:
        fields["transit"] = transit
    
    if not fields:
        return {"error": "No fields provided to update. Provide at least place_id or transit."}
    
    data = airtable_request(
        token=token,
        table_id=table_id,
        method="PATCH",
        endpoint=f"/{log_id}",
        json_data={"fields": fields}
    )
    
    if "error" in data:
        return {"error": data["error"]}
    
    return {
        "log": data,
        "message": "Location log updated successfully."
    }


def create_place(
    ctx: Context,
    name: Annotated[str, "Name of the place (e.g. 'Blue Bottle Coffee', 'WeWork Shibuya')"],
    address: Annotated[str, "Full address of the place"],
    type: Annotated[List[str], "One or more categories for the place (e.g. ['cafe'], ['cafe', 'coworking']). Call get_parameter_options(source='place', parameter='type') to see available values."],
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
        "type": [t.lower() for t in type],
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
    
    available_types = fetch_field_options(token, table_id, "type")
    
    return {
        "place": data,
        "message": f"Saved '{name}' successfully.",
        "available_types": available_types,
    }


def update_place(
    ctx: Context,
    place_id: Annotated[str, "The record ID of the place to update"],
    name: Annotated[Optional[str], "Updated name of the place"] = None,
    address: Annotated[Optional[str], "Updated full address of the place"] = None,
    type: Annotated[Optional[List[str]], "Updated categories for the place (e.g. ['cafe', 'coworking']). Call get_parameter_options(source='place', parameter='type') to see available values."] = None,
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
    if name is not None:
        fields["name"] = name
    if address is not None:
        fields["address"] = address
    if type is not None:
        fields["type"] = [t.lower() for t in type]
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
    
    available_types = fetch_field_options(token, table_id, "type")
    
    return {
        "place": data,
        "message": "Place updated successfully.",
        "available_types": available_types,
    }


def get_places(
    ctx: Context,
    name: Annotated[
        Optional[str],
        "Search by place name (partial match). For example 'Blue Bottle' will match 'Blue Bottle Coffee Shibuya'."
    ] = None,
    type: Annotated[
        Optional[List[str]],
        "Filter by one or more place categories (e.g. ['cafe'] or ['cafe', 'coworking']). Call get_parameter_options(source='place', parameter='type') to see available values. Leave empty for all types."
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
    """Search saved places, optionally filtered by name, type(s), minimum rating, and/or address."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    table_id = os.environ.get("AIRTABLE_PLACES_TABLE_ID")
    if not table_id:
        return {"error": "Places table is not configured."}
    
    params = {}
    
    # Build filter formula
    filters = []
    if name:
        filters.append(f"FIND(LOWER('{name}'), LOWER({{name}}))")
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
    available_types = fetch_field_options(token, table_id, "type")
    
    return {
        "places": records,
        "count": len(records),
        "available_types": available_types,
    }


def get_parameter_options(
    ctx: Context,
    source: Annotated[
        Literal["place", "contact"],
        "Which data source the parameter belongs to — 'place' for saved places, 'contact' for contacts"
    ],
    parameter: Annotated[
        str,
        "Which parameter to get available options for — e.g. 'type' for place categories, 'relationship' for contact relationship types, 'city' for contact cities"
    ]
) -> dict:
    """Get available options for a given parameter. Use this to see valid values before creating or filtering places and contacts."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    source_map = {
        "place": "AIRTABLE_PLACES_TABLE_ID",
        "contact": "AIRTABLE_CONTACTS_TABLE_ID",
    }
    
    env_key = source_map.get(source)
    if not env_key:
        return {"error": f"Unknown source '{source}'. Use 'place' or 'contact'."}
    
    table_id = os.environ.get(env_key)
    if not table_id:
        return {"error": f"Table for '{source}' is not configured."}
    
    options = fetch_field_options(token, table_id, parameter)
    
    return {
        "source": source,
        "parameter": parameter,
        "options": options,
        "count": len(options),
    }


# ---- Contacts ----

def get_contacts(
    ctx: Context,
    name: Annotated[
        Optional[str],
        "Search by name (partial match). For example 'John' will match 'John Doe' and 'Johnny'."
    ] = None,
    nickname: Annotated[
        Optional[str],
        "Search by nickname (partial match). For example 'Jay' will match anyone with 'Jay' in their nickname."
    ] = None,
    city: Annotated[
        Optional[str],
        "Filter by city (partial match). For example 'Tokyo' will match any contact in Tokyo. Call get_parameter_options(source='contact', parameter='city') to see available values."
    ] = None,
    sex: Annotated[
        Optional[Literal["man", "women", "other"]],
        "Filter by gender — 'man', 'women', or 'other'."
    ] = None,
    relationship: Annotated[
        Optional[List[str]],
        "Filter by one or more relationship types (e.g. ['friend'], ['friend', 'colleague']). Call get_parameter_options(source='contact', parameter='relationship') to see available values."
    ] = None,
    company: Annotated[
        Optional[str],
        "Search by company or workplace (partial match). For example 'Google' will match any contact at Google."
    ] = None
) -> dict:
    """Search contacts, optionally filtered by name, nickname, city, sex, relationship type, or company."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    table_id = os.environ.get("AIRTABLE_CONTACTS_TABLE_ID")
    if not table_id:
        return {"error": "Contacts table is not configured."}
    
    params = {}
    
    filters = []
    if name:
        filters.append(f"FIND(LOWER('{name}'), LOWER({{name}}))")
    if nickname:
        filters.append(f"FIND(LOWER('{nickname}'), LOWER({{nickname}}))")
    if city:
        filters.append(f"FIND(LOWER('{city}'), LOWER({{city}}))")
    if sex:
        filters.append(f"LOWER({{sex}}) = '{sex.lower()}'")
    if company:
        filters.append(f"FIND(LOWER('{company}'), LOWER({{company}}))")
    if relationship:
        if len(relationship) == 1:
            filters.append(f"FIND('{relationship[0]}', ARRAYJOIN({{relationship}}, ','))")
        else:
            rel_conditions = ", ".join(f"FIND('{r}', ARRAYJOIN({{relationship}}, ','))" for r in relationship)
            filters.append(f"OR({rel_conditions})")
    
    if filters:
        params["filterByFormula"] = "AND(" + ", ".join(filters) + ")" if len(filters) > 1 else filters[0]
    
    data = airtable_request(token=token, table_id=table_id, method="GET", params=params)
    
    if "error" in data:
        return {"error": data["error"]}
    
    records = data.get("records", [])
    available_relationships = fetch_field_options(token, table_id, "relationship")
    available_cities = fetch_field_options(token, table_id, "city")
    
    return {
        "contacts": records,
        "count": len(records),
        "available_relationships": available_relationships,
        "available_cities": available_cities,
    }


def create_contact(
    ctx: Context,
    name: Annotated[str, "Full name of the contact"],
    nickname: Annotated[Optional[str], "Casual name or how you refer to them"] = None,
    birthday: Annotated[Optional[str], "Date of birth in YYYY-MM-DD format"] = None,
    city: Annotated[Optional[str], "City where they live. Call get_parameter_options(source='contact', parameter='city') to see available values."] = None,
    sex: Annotated[Optional[Literal["man", "women", "other"]], "Gender of the contact"] = None,
    relationship: Annotated[Optional[List[str]], "One or more relationship types (e.g. ['friend'], ['friend', 'colleague']). Call get_parameter_options(source='contact', parameter='relationship') to see available values."] = None,
    phone: Annotated[Optional[str], "Phone number"] = None,
    email: Annotated[Optional[str], "Email address"] = None,
    company: Annotated[Optional[str], "Company or workplace"] = None,
    notes: Annotated[Optional[str], "Free-form personal notes (e.g. 'met at Tokyo conference', 'loves hiking')"] = None,
    met_date: Annotated[Optional[str], "When you first met them, in YYYY-MM-DD format"] = None
) -> dict:
    """Save a new contact."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    table_id = os.environ.get("AIRTABLE_CONTACTS_TABLE_ID")
    if not table_id:
        return {"error": "Contacts table is not configured."}
    
    fields = {"name": name}
    
    if nickname is not None:
        fields["nickname"] = nickname
    if birthday is not None:
        fields["birthday"] = birthday
    if city is not None:
        fields["city"] = city.lower()
    if sex is not None:
        fields["sex"] = sex.lower()
    if relationship is not None:
        fields["relationship"] = [r.lower() for r in relationship]
    if phone is not None:
        fields["phone"] = phone
    if email is not None:
        fields["email"] = email
    if company is not None:
        fields["company"] = company
    if notes is not None:
        fields["notes"] = notes
    if met_date is not None:
        fields["met_date"] = met_date
    
    data = airtable_request(
        token=token,
        table_id=table_id,
        method="POST",
        json_data={"fields": fields, "typecast": True}
    )
    
    if "error" in data:
        return {"error": data["error"]}
    
    available_relationships = fetch_field_options(token, table_id, "relationship")
    available_cities = fetch_field_options(token, table_id, "city")
    
    return {
        "contact": data,
        "message": f"Contact '{name}' saved successfully.",
        "available_relationships": available_relationships,
        "available_cities": available_cities,
    }


def update_contact(
    ctx: Context,
    contact_id: Annotated[str, "The record ID of the contact to update"],
    name: Annotated[Optional[str], "Updated full name"] = None,
    nickname: Annotated[Optional[str], "Updated casual name"] = None,
    birthday: Annotated[Optional[str], "Updated date of birth in YYYY-MM-DD format"] = None,
    city: Annotated[Optional[str], "Updated city. Call get_parameter_options(source='contact', parameter='city') to see available values."] = None,
    sex: Annotated[Optional[Literal["man", "women", "other"]], "Updated gender"] = None,
    relationship: Annotated[Optional[List[str]], "Updated relationship types (e.g. ['friend', 'colleague']). Call get_parameter_options(source='contact', parameter='relationship') to see available values."] = None,
    phone: Annotated[Optional[str], "Updated phone number"] = None,
    email: Annotated[Optional[str], "Updated email address"] = None,
    company: Annotated[Optional[str], "Updated company or workplace"] = None,
    notes: Annotated[Optional[str], "Updated personal notes"] = None,
    met_date: Annotated[Optional[str], "Updated met date in YYYY-MM-DD format"] = None
) -> dict:
    """Update an existing contact. Only the provided fields will be updated, the rest will remain unchanged."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    table_id = os.environ.get("AIRTABLE_CONTACTS_TABLE_ID")
    if not table_id:
        return {"error": "Contacts table is not configured."}
    
    fields = {}
    if name is not None:
        fields["name"] = name
    if nickname is not None:
        fields["nickname"] = nickname
    if birthday is not None:
        fields["birthday"] = birthday
    if city is not None:
        fields["city"] = city.lower()
    if sex is not None:
        fields["sex"] = sex.lower()
    if relationship is not None:
        fields["relationship"] = [r.lower() for r in relationship]
    if phone is not None:
        fields["phone"] = phone
    if email is not None:
        fields["email"] = email
    if company is not None:
        fields["company"] = company
    if notes is not None:
        fields["notes"] = notes
    if met_date is not None:
        fields["met_date"] = met_date
    
    if not fields:
        return {"error": "No fields provided to update."}
    
    data = airtable_request(
        token=token,
        table_id=table_id,
        method="PATCH",
        endpoint=f"/{contact_id}",
        json_data={"fields": fields, "typecast": True}
    )
    
    if "error" in data:
        return {"error": data["error"]}
    
    available_relationships = fetch_field_options(token, table_id, "relationship")
    available_cities = fetch_field_options(token, table_id, "city")
    
    return {
        "contact": data,
        "message": "Contact updated successfully.",
        "available_relationships": available_relationships,
        "available_cities": available_cities,
    }


def delete_entry(
    ctx: Context,
    source: Annotated[
        Literal["place", "contact"],
        "Which data source to delete from — 'place' for saved places, 'contact' for contacts"
    ],
    entry_id: Annotated[
        str,
        "The record ID of the entry to delete. Get this from the corresponding search tool (get_places or get_contacts)."
    ]
) -> dict:
    """Permanently delete a record. Pick the source ('place' or 'contact') and provide the record ID. This cannot be undone."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    source_map = {
        "place": "AIRTABLE_PLACES_TABLE_ID",
        "contact": "AIRTABLE_CONTACTS_TABLE_ID",
    }
    
    env_key = source_map.get(source)
    if not env_key:
        return {"error": f"Unknown source '{source}'. Use 'place' or 'contact'."}
    
    table_id = os.environ.get(env_key)
    if not table_id:
        return {"error": f"Table for '{source}' is not configured."}
    
    data = airtable_request(
        token=token,
        table_id=table_id,
        method="DELETE",
        endpoint=f"/{entry_id}"
    )
    
    if "error" in data:
        return {"error": data["error"]}
    
    return {
        "message": f"{source.capitalize()} deleted successfully.",
        "deleted_id": data.get("id", entry_id)
    }


def get_birthdays(
    ctx: Context,
) -> dict:
    """Get contacts with upcoming birthdays, grouped by urgency."""
    token = ctx.get_state("airtable_token")
    if not token:
        return {"error": "No authentication token provided in request header."}
    
    table_id = os.environ.get("AIRTABLE_CONTACTS_TABLE_ID")
    if not table_id:
        return {"error": "Contacts table is not configured."}
    
    # Fetch from the "birthday" view — Airtable already filters to relevant records
    params = {
        "view": "birthday"
    }
    
    data = airtable_request(token=token, table_id=table_id, method="GET", params=params)
    
    if "error" in data:
        return {"error": data["error"]}
    
    records = data.get("records", [])
    
    # Group records by the birthday_alert field
    today = []
    this_week = []
    this_month = []
    
    for record in records:
        alert = record.get("fields", {}).get("birthday_alert", "")
        if alert == "today":
            today.append(record)
        elif alert == "this_week":
            this_week.append(record)
        elif alert == "this_month":
            this_month.append(record)
    
    return {
        "today": today,
        "this_week": this_week,
        "this_month": this_month,
    }
