# orchestrator/orchestrator.py
import os, json, asyncio, aiohttp
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from sdl.sdl_fetch import fetch_sdl
from sdl.sdl_parser import extractor as parse_types
from orchestrator.mcp_client import MCPClient

# Azure Chat (fallback + LLM pro "types detection")
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import (
    AzureChatCompletion,
)
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)

import logging

log_orch = logging.getLogger("orchestrator")


@dataclass
class ChatResult:
    content: str


class Orchestrator:
    def __init__(
        self,
        builder_url="http://localhost:8001",
        runner_url="http://localhost:8002",
        table_url="http://localhost:8003",
        gql_url="http://localhost:33001/api/gql",
    ):
        # MCP
        self.client = MCPClient(builder_url, runner_url, table_url)
        self.builder_url = builder_url
        self.runner_url = runner_url
        self.gql_url = gql_url

        # Azure "primár"
        api_key = os.getenv("OPENAI_API_KEY")
        account = os.getenv("AZURE_COGNITIVE_ACCOUNT_NAME", "")
        deployment = os.getenv("AZURE_ORCHESTRATION_DEPLOYMENT_NAME", "")
        endpoint = f"https://{account}.openai.azure.com"
        self.azure = AzureChatCompletion(
            service_id="azure-orchestrator",
            api_key=api_key,
            endpoint=endpoint,
            deployment_name=deployment,
            api_version="2024-02-01",
        )
        self.exec = AzureChatPromptExecutionSettings()

        # SDL cache
        self._types_array: Optional[List[Dict[str, Any]]] = None
        self._types_json_for_prompt: Optional[str] = None

        # načti types prompt (tvůj soubor)
        here = os.path.dirname(__file__)
        with open(
            os.path.join(here, "prompts", "types_prompt.txt"), "r", encoding="utf-8"
        ) as f:
            self.types_prompt_template = f.read()

    def _load_types(self):
        # stáhni SDL a připrav JSON pole pro prompt
        if self._types_array is None:
            sdl = fetch_sdl()
            log_orch.info("SDL_LOADED")
            parsed = parse_types(
                sdl
            )  # {"types":[{name,kind,description,fields:[...]},...]}
            # typy pro prompt: {name, description}
            only = [
                {"name": t["name"], "description": t.get("description", "")}
                for t in parsed["types"]
            ]
            self._types_array = only
            self._types_json_for_prompt = json.dumps(only, ensure_ascii=False, indent=2)

    async def _detect_types_via_llm(self, user_prompt: str) -> List[str]:
        """
        Použij Azure orchestrátor k vyhodnocení typu dotazu nad 'types_prompt.txt'.
        Reakce: jediný JSON array string.
        """
        self._load_types()

        # připrav proměnný prompt = vlož do template tvůj JSON typů + user_prompt
        prompt_filled = (
            self.types_prompt_template.replace("```json", "")
            .replace("```", "")
            .replace("{{user_prompt}}", user_prompt)
            .replace("[GRAPHQLTYPES]", "[GRAPHQLTYPES]")
            .replace("    [GRAPHQLTYPES]", "[GRAPHQLTYPES]")
        )
        prompt_filled = prompt_filled.replace(
            "[GRAPHQLTYPES] \n", f"[GRAPHQLTYPES]\n{self._types_json_for_prompt}\n"
        )

        from semantic_kernel.contents import ChatHistory

        history = ChatHistory()
        history.add_system_message(prompt_filled)
        history.add_user_message(user_prompt)

        raw = await self.azure.get_chat_message_content(
            chat_history=history,
            settings=self.exec,
            kernel=None,
            arguments=None,
            result_type=str,
        )
        try:
            arr = json.loads(str(raw))
            if isinstance(arr, list) and all(isinstance(x, str) for x in arr):
                return arr
        except Exception:
            pass
        return []  # nešlo rozpoznat -> out-of-domain

    # ==== NOVÉ: volání na MCP builder/runner pro variables & filtered run ====

    async def _build_filter_vars(
        self, user_text: str, graphql_query: str
    ) -> Dict[str, Any]:
        payload = {
            "user_prompt": user_text,
            "skip_default": 0,
            "limit_default": 10,
            "limit_max": 100,
            "orderby_default": None,
            "graphql_query": graphql_query,  # důležité pro detekci InputWhereFilter
            "disallowed_fields": ["createdby", "changedby", "memberOf"],
        }
        async with aiohttp.ClientSession() as s:
            resp = await s.post(
                f"{self.builder_url}/buildFilterVariables", json=payload, timeout=30
            )
            resp.raise_for_status()
            data = await resp.json()

        variables = data.get("variables") or {}
        # očekáváme rovnou {"skip","limit","desc","where"} – nic dalšího neobaluj
        return variables

    async def _run_filter_query(
        self, graphql_query: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Zavolá MCP Runner /runFilterQuery s předanými variables.
        """
        payload = {
            "graphql_query": graphql_query,
            "graphql_variables": variables,
            "gql_url": self.gql_url,
        }
        async with aiohttp.ClientSession() as s:
            resp = await s.post(f"{self.runner_url}/runFilterQuery", json=payload)
            resp.raise_for_status()
            data = await resp.json()
        log_orch.info("runner.ok", extra={"count": len(data.get("entities", []))})
        return data

    # ========================================================================

    async def chat_once(self, user_prompt: str) -> ChatResult:
        """
        Hlavní vstup: rozhodni in-domain/out-of-domain.
        - In-domain: postavíme & spustíme query přes MCP servery (včetně LLM → JSON variables).
        - Out-of-domain: fallback do Azure LLM.
        Vrací JSON string {Response, Query, Variables}.
        """
        # 1) detekce typů
        types = await self._detect_types_via_llm(user_prompt)
        if types:
            log_orch.info("IN_DOMAIN", extra={"types": types})
        else:
            log_orch.info("FALLBACK_TRIGGERED", extra={"reason": "no types detected"})

        # 2) in-domain ?
        if types:
            try:
                is_scalar = " id " in f" {user_prompt.lower()} "
                if is_scalar:
                    built = await self.client.build_scalar(types)
                    query = built["query"]
                    return ChatResult(
                        json.dumps(
                            {
                                "Response": "K vyhledání konkrétní entity potřebuji ID. Pošlete mi ho prosím.",
                                "Query": query,
                                "Variables": {},
                            },
                            ensure_ascii=False,
                        )
                    )
                else:
                    built = await self.client.build_vector(types)
                    query = built["query"]

                    variables = await self._build_filter_vars(user_prompt, query)

                    ran = await self._run_filter_query(query, variables)
                    rows = ran.get("entities", []) or []
                    natural = f"Našel jsem {len(rows)} záznamů pro {' → '.join(types)}."
                    return ChatResult(
                        json.dumps(
                            {
                                "Response": natural,
                                "Query": query,
                                "Variables": variables,
                            },
                            ensure_ascii=False,
                        )
                    )
            except Exception as e:
                log_orch.exception("IN_DOMAIN_FAILED", extra={"err": str(e)})

        # 3) fallback (out-of-domain)
        from semantic_kernel.contents import ChatHistory

        history = ChatHistory()
        history.add_system_message(
            "You are a helpful assistant. Respond briefly and clearly."
        )
        history.add_user_message(user_prompt)
        raw = await self.azure.get_chat_message_content(
            chat_history=history,
            settings=self.exec,
            kernel=None,
            arguments=None,
            result_type=str,
        )
        return ChatResult(
            json.dumps(
                {"Response": str(raw), "Query": "", "Variables": {}}, ensure_ascii=False
            )
        )


# --- veřejná API pro UI ---
async def open_chat():
    log_orch.info("OPEN_CHAT_FACTORY_READY")
    orch = Orchestrator()

    async def hook(user_input: str):
        return await orch.chat_once(user_input)

    return hook
