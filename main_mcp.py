# app.py
import asyncio
from mcp_servers.graphql_tools_server import mcp as mcp_server
from mcp_servers.fastapi_http_bridge import app as fastapi_app
import uvicorn


async def main():
    # MCP server přes stdio spustíš typicky jako samostatný proces
    # Tady spustíme jen FastAPI bridge (HTTP).
    config = uvicorn.Config(
        "mcp_servers.fastapi_http_bridge:app", host="0.0.0.0", port=4040, reload=False
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())

"""
* příklad volání:
! from orchestration.ask_graphql_endpoint import sample_with_fallback
! prompt = [{"role":"user","content":"Seznam studijních programů a jejich studentů"}]
! result = asyncio.run(sample_with_fallback(messages=prompt))
! print(result)

Pokud detektor z types_prompt.txt vrátí např. ["AcProgramGQLModel","AcProgramStudentGQLModel"] -> in-domain: orchestrátor nevolá SK, ale přes MCP HTTP:

/mcp/buildVectorQuery (vytvoří GQL)

/mcp/runQueryPage (spustí GQL)

Pokud vrátí prázdno (např. „Řekni vtip o kočkách“) -> OutOfDomainError -> fallback: stejný Azure orchestrátor nasměrujeme na small-talk personu a odpovíme přirozeně.
"""
