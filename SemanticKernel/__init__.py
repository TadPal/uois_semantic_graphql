import asyncio
from pathlib import Path


from dotenv import load_dotenv

load_dotenv()

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# from semantic_kernel.contents.chat_history import ChatHistory
from semantic_kernel import Kernel
from SemanticKernel.HistoryReducer import CustomChatHistory
from semantic_kernel.functions import KernelArguments, KernelPlugin
from semantic_kernel.filters import FilterTypes, AutoFunctionInvocationContext
from semantic_kernel.exceptions import PluginInitializationError
from semantic_kernel.contents.utils.author_role import AuthorRole

from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)

from semantic_kernel.connectors.ai.function_choice_behavior import (
    FunctionChoiceBehavior,
)

skills_dir = Path(__file__).parent / "Skills"
plugins = {}

# Pro každý .py soubor načti plugin
for skill_path in skills_dir.glob("*.py"):
    if skill_path.name.startswith("_"):
        continue
    plugin_name = skill_path.stem  # např. programPage
    try:
        plugin = KernelPlugin.from_python_file(plugin_name, str(skill_path))
        plugins[plugin_name] = plugin
    except PluginInitializationError as e:
        pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
account = os.getenv("AZURE_COGNITIVE_ACCOUNT_NAME", "")
model_name = os.getenv("AZURE_CHAT_DEPLOYMENT_NAME", "") or "summarization-deployment"
endpoint = f"https://{account}.openai.azure.com"

from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import (
    AzureChatCompletion,
)

azure_chat = AzureChatCompletion(
    service_id="azure-gpt4",
    api_key=OPENAI_API_KEY,
    endpoint=endpoint,
    deployment_name=model_name,
    # api_version="2024-02-15-preview"  # nebo verze, co máš v Azure portálu
    api_version="2024-02-01",
)


AZURE_ORCHESTRATION_DEPLOYMENT_NAME = os.getenv("AZURE_ORCHESTRATION_DEPLOYMENT_NAME")
azure_orchestrator = AzureChatCompletion(
    service_id="azure-orchestrator",
    api_key=OPENAI_API_KEY,
    endpoint=endpoint,
    deployment_name=AZURE_ORCHESTRATION_DEPLOYMENT_NAME,
    # api_version="2024-02-15-preview"  # nebo verze, co máš v Azure portálu
    # api_version="2025-04-14"
)

kernel = Kernel()

# Kernel s načtenými pluginy
kernel = Kernel(
    services=[
        # azure_orchestrator,
        azure_chat,
    ],
    plugins=plugins,
    # ai_service_selector=
)


async def createGQLClient(
    *, url: str = "http://localhost:33001/api/gql", username: str, password: str
):
    import aiohttp

    async def getToken():
        authurl = url.replace("/api/gql", "/oauth/login3")
        async with aiohttp.ClientSession() as session:
            # print(headers, cookies)
            async with session.get(authurl) as resp:
                json = await resp.json()

            payload = {**json, "username": username, "password": password}
            async with session.post(authurl, json=payload) as resp:
                json = await resp.json()
            # print(f"createGQLClient: {json}")
            token = json["token"]
        return token

    token = await getToken()
    total_attempts = 10

    async def client(query, variables, cookies={"authorization": token}):
        # gqlurl = "http://host.docker.internal:33001/api/gql"
        # gqlurl = "http://localhost:33001/api/gql"
        nonlocal total_attempts
        if total_attempts < 1:
            raise Exception(
                msg="Max attempts to reauthenticate to graphql endpoint has been reached"
            )
        attempts = 2
        while attempts > 0:

            payload = {"query": query, "variables": variables}
            # print("Query payload", payload, flush=True)
            try:
                async with aiohttp.ClientSession() as session:
                    # print(headers, cookies)
                    async with session.post(url, json=payload, cookies=cookies) as resp:
                        # print(resp.status)
                        if resp.status != 200:
                            text = await resp.text()
                            # print(text, flush=True)
                            raise Exception(f"Unexpected GQL response", text)
                        else:
                            text = await resp.text()
                            # print(text, flush=True)
                            response = await resp.json()
                            # print(response, flush=True)
                            return response
            except aiohttp.ContentTypeError as e:
                attempts = attempts - 1
                total_attempts = total_attempts - 1
                print(f"attempts {attempts}-{total_attempts}", flush=True)
                nonlocal token
                token = await getToken()

    return client


async def openChat():
    gqlClient = None
    gqlClient = await createGQLClient(
        username="john.newbie@world.com", password="john.newbie@world.com"
    )

    skills = []
    for plugin in kernel.plugins.values():
        skills.extend(plugin.functions.keys())
    print(skills)

    history = CustomChatHistory(target_count=20)

    system_prompt = f"""
    You are an assistant who's primary task is to help the user query a GraphQL endpoint using available functions.
    
    RULES:
        1. You respond in valid JSON object containing response, query and variables used to call GraphQL API.
            You always respond in valid JSON format which follows this strucutre: 
            [STRUCTURE]
                {{"Response": String, "Query": String, "Variables": String}}
            [END_STRUCTURE]

            [EXPLANATION]
                Response: Your natural language summary of the result
                Query: Full built GQL query (give empty string if no query was used)
                Varaibles: Variables to be used when calling the Query (give empty string if no query was used)
            [END_EXPLANATION]

            [EXAMPLE 1]
                1: {{"Response": "I have fetched the users for you!", "Query": "query userPage($skip: Int, $limit: Int, $where: UserInputWhereFilter) {{userPage(skip: $skip, limit: $limit, where: $where) {{id name memberships {{id group {{ id name }}}}}}}}", "Variables": {{{{"where": {{"name": {{"_startswith": "Z"}}}},"skip": 0,"limit": 100}}}}}}
            [END_EXAMPLE_1]
            [EXAMPLE 2]
                2: {{"Response": "PC is short for personal computer.", "Query": "", "Variables": ""}}
            [END_EXAMPLE_2]

        2. Before creating a query gql_types must be detected from users prompt and filter variables must be found for detected_types.
        
        3. After successfully retrieving data, your final response must be a valid JSON object. If a GraphQL query was used, the JSON must contain the retrieved data labeled as "Response" and the GraphQL query used labeled as "Query" also with . If no GraphQL query was used, the "Response" field contains your full response as a string, and the "Query" and "Variables" fields must be an empty string.
    """

    history.add_system_message(system_prompt)

    execution_settings = AzureChatPromptExecutionSettings()
    execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

    async def inject_gql_client(context: AutoFunctionInvocationContext, next):
        # sem se nikdy nedostane do JSONu pro LLM,
        # naváže se těsně před voláním Python‐funkce
        context.arguments["gqlclient"] = gqlClient
        await next(context)

    kernel.add_filter(FilterTypes.AUTO_FUNCTION_INVOCATION, inject_gql_client)
    import json

    async def hook(user_input):
        history.add_user_message(user_input)
        result = await azure_chat.get_chat_message_content(
            chat_history=history,
            settings=execution_settings,
            kernel=kernel,
            arguments=KernelArguments(),
            result_type=str,
        )
        history.add_assistant_message(f"{result}")
        await history.reduce()
        return result

    return hook