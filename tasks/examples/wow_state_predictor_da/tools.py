"""ServiceNow discovery tool for the WoW state predictor.

A single `snow_query` tool that lets the ReAct agent query any ServiceNow
system table to gather context before predicting state changes:
  - Business rules (sys_script) for cascade prediction
  - Current record state for UPDATE actions
  - Choice/enum values (sys_choice) for field interpretation
  - SLA definitions (contract_sla)
  - Table schema details (sys_dictionary)

Uses WoW-convention env vars: SNOW_INSTANCE_URL, SNOW_INSTANCE_UNAME, SNOW_INSTANCE_PWD
(with fallback to the v2 predictor's SNOW_INSTANCE, SNOW_USERNAME, SNOW_PASSWORD).
"""

import contextlib
import json
import logging
import os

from langchain_core.tools import tool
from pysnc import ServiceNowClient

_log = logging.getLogger(__name__)


@contextlib.contextmanager
def _suppress_pysnc_traceback():
    """Suppress PySNC's internal traceback.print_exc() during gr.query()."""
    import traceback as _tb

    original = _tb.print_exc
    _tb.print_exc = lambda *a, **kw: None
    try:
        yield
    finally:
        _tb.print_exc = original


def _get_client() -> ServiceNowClient:
    """Lazy singleton for ServiceNow PySNC client.

    Reads credentials in WoW convention first, falls back to v2-predictor convention.
    """
    if not hasattr(_get_client, "_client") or _get_client._client is None:
        # WoW convention (primary), v2 predictor convention (fallback)
        instance = os.getenv("SNOW_INSTANCE_URL") or os.getenv("SNOW_INSTANCE")
        username = os.getenv("SNOW_INSTANCE_UNAME") or os.getenv("SNOW_USERNAME")
        password = os.getenv("SNOW_INSTANCE_PWD") or os.getenv("SNOW_PASSWORD")
        if not all([instance, username, password]):
            raise ValueError(
                "Missing ServiceNow credentials. Set SNOW_INSTANCE_URL, "
                "SNOW_INSTANCE_UNAME, and SNOW_INSTANCE_PWD."
            )
        _get_client._client = ServiceNowClient(
            instance=instance, auth=(username, password)
        )
    return _get_client._client


@tool
def snow_query(
    table: str,
    encoded_query: str,
    fields: str,
    limit: int,
    order_by: str,
) -> str:
    """Query ANY ServiceNow table using encoded query syntax.

    Use this to discover context you need before predicting state changes.
    Query system metadata tables to understand business logic and cascades.

    ## Common Discovery Patterns

    BUSINESS RULES (most useful — find cascades):
      snow_query("sys_script", "collection=incident^active=true",
                 "name,when,order,condition,script", 50, "order")
      snow_query("sys_script", "collection=change_request^active=true",
                 "name,when,order,condition,script", 50, "order")

    CHOICE / ENUM VALUES (understand numeric codes):
      snow_query("sys_choice", "name=incident^element=state^inactive=false",
                 "value,label", 50, "")
      snow_query("sys_choice", "name=incident^element=priority^inactive=false",
                 "value,label", 50, "")
      snow_query("sys_choice", "name=change_request^element=risk^inactive=false",
                 "value,label", 50, "")

    CURRENT RECORD STATE (for UPDATE actions — look up existing values):
      snow_query("incident", "number=INC0010027", "", 1, "")
      snow_query("change_request", "number=CHG0010027", "", 1, "")
      snow_query("kb_knowledge", "number=KB0010027", "", 1, "")

    TABLE SCHEMA (field types, mandatory fields, foreign keys):
      snow_query("sys_dictionary",
                 "name=incident^elementISNOTEMPTY^active=true",
                 "element,internal_type,mandatory,reference,default_value", 100, "")

    TABLE INHERITANCE (find parent tables for inherited fields):
      snow_query("sys_db_object", "name=incident", "name,label,super_class", 1, "")

    SLA DEFINITIONS (for SLA-sensitive tables):
      snow_query("contract_sla", "collection=incident^active=true",
                 "name,duration,start_condition,stop_condition", 20, "")

    REFERENCE MAP (foreign key relationships):
      snow_query("sys_dictionary",
                 "name=incident^internal_type=reference^active=true",
                 "element,reference,mandatory", 50, "")

    AUDIT TRAIL (existing record history):
      snow_query("sys_audit", "tablename=incident^documentkey=<sys_id>",
                 "fieldname,oldvalue,newvalue,sys_created_on", 50, "-sys_created_on")

    ## Efficiency Rule
    Make at most 3-5 focused queries per prediction step.
    If the static schema context already answers your question, skip the query.

    Args:
        table: ServiceNow table name (e.g., 'incident', 'sys_script',
               'sys_choice', 'sys_dictionary', 'contract_sla')
        encoded_query: ServiceNow encoded query string. Join conditions with ^.
                       Operators: =, !=, LIKE, STARTSWITH, IN,
                       ISNOTEMPTY, ISEMPTY, >, <, >=, <=, CHANGES, CHANGESTO
        fields: Comma-separated field names to return. Empty string returns all fields.
        limit: Maximum number of records to return (default 100; use 1 for single-record lookup)
        order_by: Field name to sort by. Prefix with '-' for descending order.
                  E.g., "order" (ascending), "-sys_created_on" (newest first).

    Returns:
        JSON string: {"table": "...", "count": N, "records": [...]}
        On error: {"error": "...", "hint": "Do NOT retry — use the data you already have."}
    """
    try:
        client = _get_client()
    except ValueError as exc:
        return json.dumps(
            {
                "error": str(exc),
                "table": table,
                "count": 0,
                "records": [],
                "hint": "Set SNOW_INSTANCE_URL, SNOW_INSTANCE_UNAME, SNOW_INSTANCE_PWD and retry.",
            }
        )

    gr = client.GlideRecord(table, batch_size=100)
    if encoded_query:
        gr.add_encoded_query(encoded_query)
    if fields:
        gr.fields = [f.strip() for f in fields.split(",") if f.strip()]
    gr.limit = limit if limit and limit > 0 else 100
    if order_by:
        if order_by.startswith("-"):
            gr.order_by_desc(order_by[1:])
        else:
            gr.order_by(order_by)

    _HINT = (
        "The instance may be rate-limiting, hibernating, or auth expired. "
        "Do NOT retry — use the static context you already have."
    )

    try:
        with _suppress_pysnc_traceback():
            gr.query()
    except Exception as exc:
        _log.warning("snow_query failed for table=%s query=%s: %s", table, encoded_query, exc)
        return json.dumps(
            {
                "error": f"ServiceNow query failed: {type(exc).__name__}: {exc}",
                "table": table,
                "count": 0,
                "records": [],
                "hint": _HINT,
            }
        )

    records = []
    try:
        for record in gr:
            row = {}
            for field in record.fields:
                element = record.get_element(field)
                if element is not None:
                    val = element.get_value()
                    dval = element.get_display_value()
                    # Include display_value only when it differs from raw value —
                    # gives the agent human-readable labels alongside raw codes.
                    if dval and dval != val:
                        row[field] = {"value": val, "display_value": dval}
                    else:
                        row[field] = val
                else:
                    row[field] = None
            records.append(row)
    except Exception as exc:
        # Catches JSONDecodeError from empty HTTP responses (hibernating instance)
        # and any other iteration-time errors from pysnc.
        _log.warning("snow_query iteration failed for table=%s query=%s: %s", table, encoded_query, exc)
        return json.dumps(
            {
                "error": f"ServiceNow result iteration failed: {type(exc).__name__}: {exc}",
                "table": table,
                "count": 0,
                "records": [],
                "hint": _HINT,
            }
        )

    _log.debug("snow_query table=%s count=%d", table, len(records))
    return json.dumps({"table": table, "count": len(records), "records": records}, indent=2)
