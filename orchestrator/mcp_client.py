# orchestrator/mcp_client.py
import httpx
from typing import Any, Dict, List


class MCPClient:
    def __init__(
        self,
        builder_url: str = "http://localhost:8001",  # gql_builder_server
        runner_url: str = "http://localhost:8002",  # gql_runner_server
    ):  # utils_table_server
        self.builder_url = builder_url.rstrip("/")
        self.runner_url = runner_url.rstrip("/")
        self.http = httpx.AsyncClient(timeout=60)

    # --- builder ---
    async def build_vector(self, graphql_types: List[str]) -> Dict[str, Any]:
        r = await self.http.post(
            f"{self.builder_url}/buildVectorQuery",
            json={"graphql_types": graphql_types},
        )
        r.raise_for_status()
        return r.json()

    async def build_scalar(self, graphql_types: List[str]) -> Dict[str, Any]:
        r = await self.http.post(
            f"{self.builder_url}/buildScalarQuery",
            json={"graphql_types": graphql_types},
        )
        r.raise_for_status()
        return r.json()

    # --- runner ---
    async def run_page(
        self, query: str, skip=0, limit=10, gql_url=None
    ) -> Dict[str, Any]:
        payload = {"graphql_query": query, "skip": skip, "limit": limit}
        if gql_url:
            payload["gql_url"] = gql_url
        r = await self.http.post(f"{self.runner_url}/runQueryPage", json=payload)
        r.raise_for_status()
        return r.json()

    async def run_single(self, query: str, id: str, gql_url=None) -> Dict[str, Any]:
        payload = {"graphql_query": query, "id": id}
        if gql_url:
            payload["gql_url"] = gql_url
        r = await self.http.post(f"{self.runner_url}/runQuerySingle", json=payload)
        r.raise_for_status()
        return r.json()

    async def run_filter(
        self, query: str, variables: Dict[str, Any], gql_url=None
    ) -> Dict[str, Any]:
        payload = {"graphql_query": query, "graphql_variables": variables}
        if gql_url:
            payload["gql_url"] = gql_url
        r = await self.http.post(f"{self.runner_url}/runFilterQuery", json=payload)
        r.raise_for_status()
        return r.json()

    # --- utils ---
    async def json_to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        r = await self.http.post(
            f"{self.table_url}/jsonToMarkdownTable", json={"rows": rows}
        )
        r.raise_for_status()
        return r.json()["markdown"]

    async def aclose(self):
        await self.http.aclose()
