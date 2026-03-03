"""
JARVIS-OS Plugin: Contact CRM
Simple contact store with relationship tracking and interaction history.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.plugin.contacts")

PLUGIN_INFO = {
    "name": "Contact CRM",
    "version": "1.0.0",
    "description": "Store contacts with relationship info and interaction history",
    "author": "JARVIS-OS",
    "capabilities": ["contacts", "crm", "relationships"],
}

_contacts: list[dict] = []
_data_file: Optional[Path] = None


def _load():
    global _contacts
    if _data_file and _data_file.exists():
        try:
            _contacts = json.loads(_data_file.read_text())
        except Exception:
            _contacts = []


def _save():
    if _data_file:
        _data_file.write_text(json.dumps(_contacts, indent=2, default=str))


def get_tools():
    return [
        {
            "name": "add_contact",
            "description": "Add a new contact with name, relationship, and optional details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Contact's name"},
                    "relationship": {"type": "string", "description": "Relationship (friend, colleague, family, etc.)"},
                    "email": {"type": "string", "description": "Email address"},
                    "phone": {"type": "string", "description": "Phone number"},
                    "notes": {"type": "string", "description": "Additional notes about this contact"},
                    "company": {"type": "string", "description": "Company or organization"},
                },
                "required": ["name"],
            },
        },
        {
            "name": "search_contacts",
            "description": "Search contacts by name, relationship, or notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "update_contact",
            "description": "Update a contact's information or add an interaction note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "updates": {"type": "object", "description": "Fields to update"},
                    "interaction": {"type": "string", "description": "Log an interaction (e.g., 'Had lunch, discussed project X')"},
                },
                "required": ["contact_id"],
            },
        },
        {
            "name": "list_contacts",
            "description": "List all contacts, optionally filtered by relationship.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relationship": {"type": "string", "description": "Filter by relationship type"},
                },
            },
        },
    ]


async def execute(tool_name: str, arguments: dict, context: dict) -> dict:
    if tool_name == "add_contact":
        return _add_contact(arguments)
    elif tool_name == "search_contacts":
        return _search_contacts(arguments.get("query", ""))
    elif tool_name == "update_contact":
        return _update_contact(arguments.get("contact_id", ""),
                               arguments.get("updates", {}),
                               arguments.get("interaction", ""))
    elif tool_name == "list_contacts":
        return _list_contacts(arguments.get("relationship", ""))
    return {"error": f"Unknown tool: {tool_name}"}


def _add_contact(data: dict) -> dict:
    contact = {
        "id": f"contact_{int(datetime.now().timestamp() * 1000)}",
        "name": data.get("name", "Unknown"),
        "relationship": data.get("relationship", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "company": data.get("company", ""),
        "notes": data.get("notes", ""),
        "interactions": [],
        "created_at": datetime.now().isoformat(),
        "last_interaction": None,
    }
    _contacts.append(contact)
    _save()
    return {"status": "success", "contact": contact}


def _search_contacts(query: str) -> dict:
    query_lower = query.lower()
    matches = []
    for c in _contacts:
        searchable = f"{c['name']} {c.get('relationship', '')} {c.get('notes', '')} {c.get('company', '')}".lower()
        if query_lower in searchable:
            matches.append(c)
    return {"status": "success", "results": matches, "count": len(matches)}


def _update_contact(contact_id: str, updates: dict, interaction: str) -> dict:
    for c in _contacts:
        if c["id"] == contact_id:
            for key, value in updates.items():
                if key in ("name", "relationship", "email", "phone", "company", "notes"):
                    c[key] = value
            if interaction:
                c["interactions"].append({
                    "note": interaction,
                    "timestamp": datetime.now().isoformat(),
                })
                c["last_interaction"] = datetime.now().isoformat()
            _save()
            return {"status": "success", "contact": c}
    return {"status": "error", "message": f"Contact not found: {contact_id}"}


def _list_contacts(relationship: str = "") -> dict:
    if relationship:
        filtered = [c for c in _contacts if c.get("relationship", "").lower() == relationship.lower()]
    else:
        filtered = _contacts
    return {
        "status": "success",
        "contacts": filtered,
        "count": len(filtered),
    }


async def on_load(kernel):
    global _data_file
    data_dir = Path(kernel.config.get("system", {}).get("data_dir", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    _data_file = data_dir / "contacts.json"
    _load()
    logger.info(f"Contact CRM plugin loaded — {len(_contacts)} contacts")


async def on_unload():
    _save()
    logger.info("Contact CRM plugin unloaded")
