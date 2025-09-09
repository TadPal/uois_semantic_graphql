# mcp_servers/gql_builder_server.py

from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from contextlib import asynccontextmanager
import graphql

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
    orderby_default: Optional[str] = None
    now_iso: Optional[str] = None
    graphql_query: Optional[str] = None
    disallowed_fields: Optional[List[str]] = []  # ← volitelný blacklist


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

_SEARCHABLE_FIELDS_ORDER = [
    "name",
    "fullname",
    "surname",
    "email",
    "givenname",
    "firstname",
]


def _unwrap_type_node(t) -> Optional[str]:
    while hasattr(t, "type"):
        t = t.type
    return getattr(getattr(t, "name", None), "value", None)


def _get_where_input_name_from_query(query: Optional[str]) -> Optional[str]:
    if not query:
        return None
    try:
        ast = graphql.parse(query)
        for defn in ast.definitions:
            if defn.kind == "operation_definition":
                for v in defn.variable_definitions or []:
                    if v.variable.name.value == "where":
                        return _unwrap_type_node(v.type)
    except Exception:
        pass
    return None


def _collect_filter_ops(sdl_ast) -> Dict[str, List[str]]:
    """Mapuje název input filtru (např. StrFilter) → povolené operátory."""
    out: Dict[str, List[str]] = {}
    for d in sdl_ast.definitions:
        if d.kind == "input_object_type_definition":
            name = d.name.value
            if name.endswith("Filter") or name.endswith("filter"):
                out[name] = [f.name.value for f in (d.fields or [])]
    return out


def _collect_allowed_where_fields(
    sdl_ast, where_input_name: Optional[str]
) -> Dict[str, str]:
    """
    Vrátí mapu { field_name -> filter_input_type }, např. {"name":"StrFilter","id":"UuidFilter"}.
    """
    if not where_input_name:
        return {}
    for d in sdl_ast.definitions:
        if (
            d.kind == "input_object_type_definition"
            and d.name.value == where_input_name
        ):
            allowed: Dict[str, str] = {}
            for f in d.fields or []:
                ft = _unwrap_type_node(f.type)
                if ft:
                    allowed[f.name.value] = ft
            return allowed
    return {}


def _sanitize_where(
    where: Any,
    allowed_fields: Dict[str, str],
    filter_ops: Dict[str, List[str]],
    disallowed: set[str],
) -> Optional[dict]:
    """Vyhodí pole mimo SDL a operátory mimo definici konkrétního *Filter* input typu."""
    if not isinstance(where, dict):
        return None
    cleaned: Dict[str, Any] = {}
    for key, val in where.items():
        if key in ("_and", "_or"):
            if isinstance(val, list):
                branch = []
                for sub in val:
                    sv = _sanitize_where(sub, allowed_fields, filter_ops, disallowed)
                    if sv:
                        branch.append(sv)
                if branch:
                    cleaned[key] = branch
            continue

        if key in disallowed:
            continue
        filter_input = allowed_fields.get(key)
        if not filter_input:
            continue  # field mimo SDL

        allowed_ops = set(filter_ops.get(filter_input, []))
        if isinstance(val, dict):
            ops_ok = {op: v for op, v in val.items() if op in allowed_ops}
            if ops_ok:
                cleaned[key] = ops_ok
    return cleaned or None


def _make_filter_prompt(
    *,
    skip_default: int,
    limit_default: int,
    limit_max: int,
    now_iso: str,
    allowed_fields: Dict[str, str],
    filter_ops: Dict[str, List[str]],
) -> str:
    allowed_fields_json = json.dumps(
        [
            {"field": f, "filter": t, "ops": filter_ops.get(t, [])}
            for f, t in sorted(allowed_fields.items())
        ],
        ensure_ascii=False,
        indent=2,
    )
    return f"""
You are a GraphQL filter extractor for a known schema. 
Return ONLY a valid JSON object with keys: {{"skip":Int,"limit":Int,"desc":Boolean|null,"where":Object|null}}.

Use ONLY fields and operators listed below. Do not invent fields or operators.

ALLOWED_FIELDS (from InputWhereFilter):
{allowed_fields_json}

Rules:
- The "where" object must use nested operators under fields, e.g. {{"name":{{"_like":"%Zde%"}}}}; NEVER `"name_like"`.
- Operators per field are restricted by its filter type (see ALLOWED_FIELDS).
- Compose conditions only with `"_and"` and `"_or"` (arrays). When nesting, alternate blocks (an `"_or"` contains a list of `"_and"` blocks and vice versa).
- For “contains” semantics use `_like` and include `%` wildcards in the value (e.g., "%text%").
- Prefer the most semantically appropriate single field when the user intent is clear (avoid spreading the same token to many fields unless explicitly asked).
- Bounds: skip default {skip_default}; limit default {limit_default}, clamp to [1, {limit_max}].
- "desc" may be null if unspecified.

Output JSON ONLY:
{{"skip":int,"limit":int,"desc":true|false|null,"where":<object|null>}}
""".strip()


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


async def _llm_json(system_prompt: str, user_payload: str) -> dict:
    """
    Vrátí čisté JSON (dict) z LLM. Preferuje lokální Azure klient,
    jinak použije HTTP proxy (LLM_PROXY_URL).
    """
    global azure_llm, azure_exec

    # 1) Azure přímo (stabilní cesta)
    if azure_llm is not None:
        from semantic_kernel.contents import ChatHistoryTruncationReducer
        from semantic_kernel.contents.utils.author_role import AuthorRole

        hist = ChatHistoryTruncationReducer(target_count=12)
        # hist = ChatHistory()
        hist.add_system_message(system_prompt)
        hist.add_user_message(user_payload)
        raw = await azure_llm.get_chat_message_content(
            chat_history=hist,
            settings=azure_exec,
            kernel=None,
            arguments=None,
            result_type=str,
        )

        await hist.reduce()
        if not any(m.role == AuthorRole.SYSTEM for m in hist.messages):
            hist.add_system_message(system_prompt)

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


@app.post("/buildFilterVariables")
async def build_filter_variables(payload: BuildFilterVarsIn):
    log_b.info("buildFilter.received", extra={"prompt": payload.user_prompt[:160]})
    now_iso = payload.now_iso or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    # --- SDL → whitelist/ops pro konkrétní $where typ ---
    try:
        sdl = fetch_sdl()
        sdl_ast = graphql.parse(sdl)
        where_input = _get_where_input_name_from_query(payload.graphql_query)
        filter_ops = _collect_filter_ops(sdl_ast)
        allowed_fields = _collect_allowed_where_fields(sdl_ast, where_input)
    except Exception as e:
        log_b.exception("buildFilter.sdl_failed", extra={"err": str(e)})
        filter_ops, allowed_fields = {}, {}

    # volitelný blacklist z klienta
    disallowed = set(payload.disallowed_fields or [])

    # --- Prompt založený na SDL ---
    system_prompt = _make_filter_prompt(
        skip_default=payload.skip_default,
        limit_default=payload.limit_default,
        limit_max=payload.limit_max,
        now_iso=now_iso,
        allowed_fields=allowed_fields,
        filter_ops=filter_ops,
    )
    user_msg = {
        "USER_QUERY": payload.user_prompt,
        "GRAPHQL_QUERY": payload.graphql_query,  # jen kontext; model z něj nic neparsuje
        "DEFAULTS": {
            "skip": payload.skip_default,
            "limit": payload.limit_default,
            "limit_max": payload.limit_max,
            "orderby": payload.orderby_default,  # držím pro kompatibilitu
            "now_iso": now_iso,
        },
    }

    # --- LLM → JSON ---
    try:
        raw_vars = await _llm_json(
            system_prompt, json.dumps(user_msg, ensure_ascii=False)
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

    # --- Normalizace a sanitizace vůči SDL ---
    skip = int(raw_vars.get("skip", payload.skip_default) or 0)
    limit = int(raw_vars.get("limit", payload.limit_default) or payload.limit_default)
    limit = max(1, min(limit, payload.limit_max))
    desc = raw_vars.get("desc", None)
    where = raw_vars.get("where", None)

    where = _sanitize_where(where, allowed_fields, filter_ops, disallowed)

    out = {"skip": skip, "limit": limit, "desc": desc, "where": where}
    log_b.info("buildFilter.ok", extra={"vars": out})
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
