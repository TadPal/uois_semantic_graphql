# mcp_servers/gql_builder_server.py
# mcp_servers/gql_builder_server.py
from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from contextlib import asynccontextmanager

# SDL / builder utils
from sdl.sdl_fetch import (
    fetch_sdl,
)  # (zatím nepoužito, ale nechávám pro budoucí rozšíření)
from SemanticKernel.Skills.graphqlQueryBuilder import GraphQLQueryBuilder

# Azure LLM (přímo přes Semantic Kernel)
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import (
    AzureChatCompletion,
)
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)
from semantic_kernel.contents import ChatHistory

# stdlib / externí
from datetime import datetime, timezone
import os, json, re, aiohttp

# remote log sink
from mcp_servers.http_log import setup_remote_logging

azure_llm = None
azure_exec = None
log_b = logging.getLogger("mcp.builder")

# ---- tvoje SDL utilitky (builder) ----
# ? Lze využít naše utils, pro složitější dotazy...
# from sdl.sdl_fetch import fetch_sdl
# from SemanticKernel.Skills.utils_sdl_2 import (
#     build_large_fragment,
#     build_medium_fragment,
#     get_read_vector_values,
#     get_read_scalar_values,
#     select_ast_by_path,
# )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    setup_remote_logging()
    global azure_llm, azure_exec
    account = os.getenv("AZURE_COGNITIVE_ACCOUNT_NAME", "")
    endpoint = f"https://{account}.openai.azure.com"
    azure_llm = AzureChatCompletion(
        service_id="builder-llm",
        api_key=os.getenv("OPENAI_API_KEY"),
        endpoint=endpoint,
        deployment_name=os.getenv("AZURE_ORCHESTRATION_DEPLOYMENT_NAME", ""),
        api_version="2024-02-01",
    )
    azure_exec = AzureChatPromptExecutionSettings()

    log_b.info("builder.startup", extra={"note": "MCP Builder is up"})
    try:
        yield
    finally:
        log_b.info("builder.shutdown")


app = FastAPI(lifespan=lifespan, title="MCP GraphQL Builder Server")


# ===== Models =================================================================


class BuildFilterVarsIn(BaseModel):
    user_prompt: str
    skip_default: int = 0
    limit_default: int = 10
    limit_max: int = 100
    # POZOR: u tebe se používá 'desc' (Boolean) – 'orderby' proto v JSONu už neposíláme
    orderby_default: Optional[str] = None
    now_iso: Optional[str] = None
    graphql_query: Optional[str] = None  # poskytni LLM kontext dotazu (root typ/paramy)


class DetectTypesIn(BaseModel):
    user_prompt: str
    types_json: Optional[dict] = None


class BuildVectorIn(BaseModel):
    graphql_types: List[str]


class BuildScalarIn(BaseModel):
    graphql_types: List[str]


# --- where normalizer helpers (bez heuristik vyhledávání) ---
_ALLOWED_AGGS = {"_and", "_or"}
_ALLOWED_OPS = {
    "_eq",
    "_in",
    "_like",
    "_startswith",
    "_endswith",
    "_ge",
    "_gt",
    "_le",
    "_lt",
}
_PREFERRED_FIELD = "name"
_SEARCHABLE_FIELDS_ORDER = [
    "name",
    "fullname",
    "surname",
    "email",
    "givenname",
    "firstname",
]


def _wrap_like(v: str) -> str:
    s = (v or "").strip()
    if not s.startswith("%"):
        s = "%" + s
    if not s.endswith("%"):
        s = s + "%"
    return s


def _iter_field_conditions(node):
    """Z libovolné where struktury (vč. _and/_or) vytáhne trojice (field, op, value)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in _ALLOWED_AGGS and isinstance(v, list):
                for sub in v:
                    yield from _iter_field_conditions(sub)
            elif isinstance(v, dict):
                for op, val in v.items():
                    if op in _ALLOWED_OPS:
                        yield (k, op, val)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_field_conditions(item)


def _to_like_value(op: str, val: str) -> str:
    sval = str(val)
    if op == "_like":
        return _wrap_like(sval)
    if op == "_startswith":
        return _wrap_like(sval + "%".rstrip("%"))
    if op == "_endswith":
        return _wrap_like("%" + sval)
    # fallback: treat anything stringy as contains
    return _wrap_like(sval)


def _canonize_where_to_name_like(where: Optional[dict]) -> Optional[dict]:
    """
    Pokud LLM vrátí textové podmínky na některém z polí (name/fullname/…),
    vrátí vždy jednoduchý tvar: {"name": {"_like": "%token%"}}.
    Jinak vrátí původní `where` beze změny.
    """
    if not isinstance(where, dict) or not where:
        return where

    # 1) má už přímo name { _like/_startswith/_endswith/_eq } ?
    name_cond = where.get("name")
    if isinstance(name_cond, dict):
        for op, val in name_cond.items():
            if op in _ALLOWED_OPS and isinstance(val, (str, int, float)):
                return {"name": {"_like": _to_like_value(op, str(val))}}

    # 2) projdi celé where a najdi první vhodnou textovou podmínku v preferovaném pořadí
    best = None
    for fld, op, val in _iter_field_conditions(where):
        if fld in _SEARCHABLE_FIELDS_ORDER and isinstance(val, (str, int, float)):
            best = _to_like_value(op, str(val))
            break

    if best:
        return {"name": {"_like": best}}

    # nic textového → ponech beze změny (žádná heuristika)
    return where


async def _llm_json(system_prompt: str, user_payload: str) -> dict:
    """
    Vrátí čisté JSON (dict) z LLM. Preferuje lokální Azure klient,
    jinak použije HTTP proxy (LLM_PROXY_URL).
    """
    global azure_llm, azure_exec

    # 1) Azure přímo (stabilní cesta)
    if azure_llm is not None:
        from semantic_kernel.contents import ChatHistory

        hist = ChatHistory()
        hist.add_system_message(system_prompt)
        hist.add_user_message(user_payload)
        raw = await azure_llm.get_chat_message_content(
            chat_history=hist,
            settings=azure_exec,
            kernel=None,
            arguments=None,
            result_type=str,
        )
        data = json.loads(str(raw))
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected LLM JSON (azure): {data}")
        return data

    # 2) Fallback: externí gateway/proxy
    LLM_PROXY = os.getenv("LLM_PROXY_URL")
    if not LLM_PROXY:
        raise RuntimeError(
            "No LLM available (Azure not init and LLM_PROXY_URL missing)"
        )

    import aiohttp

    async with aiohttp.ClientSession() as s:
        resp = await s.post(
            LLM_PROXY, json={"system": system_prompt, "input": user_payload}, timeout=60
        )
        resp.raise_for_status()
        data = await resp.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected LLM JSON (proxy): {data}")
        return data


_FILTER_PROMPT = """
You are a GraphQL filter extractor.
Return ONLY a valid JSON object with keys: {"skip":Int,"limit":Int,"desc":Boolean|null,"where":Object|null}.

STRICT RULES for "where":
- Use nested operators under fields, e.g. {"name":{"_like":"%Zde%"}}; NEVER "name_like":"Zde".
- Allowed ops: "_eq","_in","_like","_startswith","_endswith","_ge","_gt","_le","_lt".
- Combine with {"_and":[...]} and {"_or":[...]}. When nesting, alternate: an "_or" contains a list of "_and" blocks and vice versa.
- For "contains" semantics, always wrap the value with percent wildcards: "%text%".
- When the user says “ve jménu / in the name”, prefer fields: name, surname, fullname, email.

Pagination:
- If the user gives a single number (e.g., "napiš mi 3 ..."), set "limit" to that value (clamped to bounds) and keep "skip" at its default unless the user explicitly says "skip / přeskoč".
- "desc" may be null if not specified.

Output:
{"skip": <int>, "limit": <int>, "desc": true|false|null, "where": <object|null>}
"""


@app.post("/buildFilterVariables")
async def build_filter_variables(payload: BuildFilterVarsIn):
    log_b.info("buildFilter.received", extra={"prompt": payload.user_prompt[:160]})
    now_iso = payload.now_iso or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    user_msg = {
        "USER_QUERY": payload.user_prompt,
        "GRAPHQL_QUERY": payload.graphql_query,
        "DEFAULTS": {
            "skip": payload.skip_default,
            "limit": payload.limit_default,
            "limit_max": payload.limit_max,
            "orderby": payload.orderby_default,
            "now_iso": now_iso,
        },
    }

    # Jen LLM (bez heuristik). Pokud selže, vrať konzervativní defaulty a where=None.
    try:
        raw_vars = await _llm_json(
            _FILTER_PROMPT, json.dumps(user_msg, ensure_ascii=False)
        )
    except Exception as e:
        log_b.exception("buildFilter.llm_failed", extra={"err": str(e)})
        return {
            "variables": {
                "skip": payload.skip_default,
                "limit": payload.limit_default,
                "desc": None,
                "where": None,
                "_llm_error": str(e),
            }
        }

    # Očisti & omez hranice
    skip = int(raw_vars.get("skip", payload.skip_default) or 0)
    limit = int(raw_vars.get("limit", payload.limit_default) or payload.limit_default)
    limit = max(1, min(limit, payload.limit_max))
    desc = raw_vars.get("desc", None)
    where = raw_vars.get("where", None)

    # ✳︎ Kanonizace where → pokud jde o „jméno“ hledání, zredukuj na {"name":{"_like":"%...%"}}
    where_canon = _canonize_where_to_name_like(where)

    out = {"skip": skip, "limit": limit, "desc": desc, "where": where_canon}
    log_b.info("buildFilter.llm_ok", extra={"vars": out})
    return {"variables": out}


@app.post("/detectGraphQLTypes")
def detect_graphql_types(_: DetectTypesIn):
    return {"info": "Detection by LLM dělá orchestrátor. Server vrací 200."}


@app.post("/buildVectorQuery")
def build_vector_query(payload: BuildVectorIn):
    log_b.info("buildVectorQuery.received", extra={"types": payload.graphql_types})
    builder = GraphQLQueryBuilder(
        disabled_fields=["createdby", "changedby", "memberOf"]
    )
    query = builder.build_query_vector(payload.graphql_types)
    explained = builder.explain_graphql_query(query)
    log_b.info("buildVectorQuery.done", extra={"query_preview": query[:160]})
    return {"query": query, "explained": explained}


@app.post("/buildScalarQuery")
def build_scalar_query(payload: BuildScalarIn):
    log_b.info("buildScalarQuery.received", extra={"types": payload.graphql_types})
    builder = GraphQLQueryBuilder(
        disabled_fields=["createdby", "changedby", "memberOf"]
    )
    query = builder.build_query_scalar(payload.graphql_types)
    explained = builder.explain_graphql_query(query)
    log_b.info("buildScalarQuery.done", extra={"query_preview": query[:160]})
    return {"query": query, "explained": explained}
