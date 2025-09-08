### OLD ####

from fastapi import FastAPI
from pydantic import BaseModel
from mcp_servers.graphql_tools_server import (
    buildVectorQuery,
    buildScalarQuery,
    runQueryPage,
    runQuerySingle,
    findFilterVariables,
)

# ? MCP běžně jede přes stdio (a klient se připojuje jako host), přidáme si HTTP mirror těch samých operací, aby orchestrátor nemusel řešit transport.
# ? (Ofiko doporučení pro stdio + info o HTTP logování viz docs.)

# ? MCP klient (Claude, Cursor…) může mluvit se graphql-tools přes stdio;
# ? tvůj orchestrátor naopak volá jednoduše HTTP bridge

app = FastAPI(title="MCP-HTTP Bridge")


class TypesIn(BaseModel):
    graphql_types: list[str]


class QueryIn(BaseModel):
    graphql_query: str
    skip: int = 0
    limit: int = 10


class QueryIdIn(BaseModel):
    graphql_query: str
    id: str


@app.post("/mcp/buildVectorQuery")
def http_build_vector(body: TypesIn):
    return {"query": buildVectorQuery(body.graphql_types)}


@app.post("/mcp/buildScalarQuery")
def http_build_scalar(body: TypesIn):
    return {"query": buildScalarQuery(body.graphql_types)}


@app.post("/mcp/runQueryPage")
async def http_run_page(body: QueryIn):
    return {"data": await runQueryPage(body.graphql_query, body.skip, body.limit)}


@app.post("/mcp/runQuerySingle")
async def http_run_single(body: QueryIdIn):
    return {"data": await runQuerySingle(body.graphql_query, body.id)}


@app.post("/mcp/findFilterVariables")
def http_find_filter(body: TypesIn):
    return {"filters": findFilterVariables(body.graphql_types)}
