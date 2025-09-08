# mcp_servers/gql_runner_server.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, Any
import aiohttp
import asyncio
from sdl.sdl_fetch import getToken
from contextlib import asynccontextmanager
from mcp_servers.http_log import setup_remote_logging
import logging

log_r = logging.getLogger("mcp.runner")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_remote_logging()
    log_r.info("runner.startup", extra={"note": "MCP Runner is up"})
    try:
        yield
    finally:
        log_r.info("runner.shutdown")


app = FastAPI(lifespan=lifespan, title="MCP GraphQL Runner Server")


class RunPageIn(BaseModel):
    graphql_query: str
    skip: int = 0
    limit: int = 10
    gql_url: str = "http://localhost:33001/api/gql"
    username: Optional[str] = "john.newbie@world.com"
    password: Optional[str] = "john.newbie@world.com"


class RunSingleIn(BaseModel):
    graphql_query: str
    id: str
    gql_url: str = "http://localhost:33001/api/gql"
    username: Optional[str] = "john.newbie@world.com"
    password: Optional[str] = "john.newbie@world.com"


class RunFilterIn(BaseModel):
    graphql_query: str
    graphql_variables: Dict[str, Any]
    gql_url: str = "http://localhost:33001/api/gql"
    username: Optional[str] = "john.newbie@world.com"
    password: Optional[str] = "john.newbie@world.com"


async def _post_gql(url: str, query: str, variables: dict, token: str):
    payload = {"query": query, "variables": variables}
    cookie = {"authorization": token}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, cookies=cookie) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"GQL HTTP {resp.status}: {text}")
            return await resp.json()


@app.post("/runQueryPage")
async def run_query_page(payload: RunPageIn):
    log_r.info(
        "runQueryPage.received", extra={"skip": payload.skip, "limit": payload.limit}
    )
    token = getToken(
        url=payload.gql_url, username=payload.username, password=payload.password
    )
    vars = {"skip": payload.skip, "limit": payload.limit}
    rows = await _post_gql(payload.gql_url, payload.graphql_query, vars, token)
    data = rows.get("data", {})
    _, entities = next(iter(data.items())) if data else (None, [])
    log_r.info("runQueryPage.ok", extra={"count": len(entities)})
    return {"entities": entities, "raw": rows}


@app.post("/runQuerySingle")
async def run_query_single(payload: RunSingleIn):
    log_r.info("runQuerySingle.received", extra={"id": payload.id})
    token = getToken(
        url=payload.gql_url, username=payload.username, password=payload.password
    )
    rows = await _post_gql(
        payload.gql_url, payload.graphql_query, {"id": payload.id}, token
    )
    data = rows.get("data", {})
    _, entity = next(iter(data.items())) if data else (None, None)
    log_r.info("runQuerySingle.ok", extra={"has_entity": entity is not None})
    return {"entity": entity, "raw": rows}


@app.post("/runFilterQuery")
async def run_filter_query(payload: RunFilterIn):
    log_r.info(
        "runFilterQuery.received",
        extra={"vars": list(payload.graphql_variables.keys())},
    )
    token = getToken(
        url=payload.gql_url, username=payload.username, password=payload.password
    )
    rows = await _post_gql(
        payload.gql_url, payload.graphql_query, payload.graphql_variables, token
    )
    data = rows.get("data", {})
    _, entities = next(iter(data.items())) if data else (None, [])
    log_r.info("runFilterQuery.ok", extra={"count": len(entities)})
    return {"entities": entities, "raw": rows}
