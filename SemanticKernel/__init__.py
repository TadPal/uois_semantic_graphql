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
from semantic_kernel.contents import ChatHistoryTruncationReducer
from semantic_kernel.functions import KernelArguments, KernelPlugin
from semantic_kernel.filters import FilterTypes, AutoFunctionInvocationContext
from semantic_kernel.exceptions import PluginInitializationError

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


async def BasicChaStreamImplementation(context: dict):
    inQueue: asyncio.Queue = context["inQueue"]
    outQueue: asyncio.Queue = context["outQueue"]
    user: dict = context["User"]
    userFullName: str = user["fullname"]
    welcomeMessage = {
        "__typename": "MessageGQLModel",
        "prompt": f"Hello {userFullName}",
    }
    systemMessages = [
        {
            "role": "system",
            "content": f"You are assistant for employee at university. Logged user's name is {userFullName}",
        },
    ]
    await outQueue.put(welcomeMessage)

    response = await inQueue.get()
    stop = response["__typename"] == "StopGQLModel"
    dialogMessages = []
    while not stop:
        dialogMessages.append({"role": "user", "content": response["message"]})

        prompt = "\n".join(systemMessages)
        prompt += "\n".join(dialogMessages)
        result = await kernel.invoke_prompt(prompt=prompt.strip())
        result_str = f"{result}"
        dialogMessages.append({"role": "system", "content": result_str})
        await outQueue.put(
            {"__typename": "MessageGQLModel", "systemResponse": result_str}
        )
        response = await inQueue.get()


async def openChat():
    gqlClient = None
    gqlClient = await createGQLClient(
        username="john.newbie@world.com", password="john.newbie@world.com"
    )

    skills = []
    for plugin in kernel.plugins.values():
        skills.extend(plugin.functions.keys())
    print(skills)

    history = ChatHistoryTruncationReducer(target_count=12)

    system_prompt = f"""
    You are an assistant and your primary task is to help query databases using graphql.

    You always response with JSON valid format, follow exactly this strucutre : {{"Response": "...", "Query": "...", "Variables": "..."}}

    Response: str -> Your natural language summary of the result
    Query: str -> Full built GQL query (give empty string if no query was used)
    Varaibles: str -> Variables to be used when calling the Query (give empty string if no query was used)
    
    Rules:
        1. You respond in valid JSON object containing response, query and variables used to call GraphQL API. 
            Example 1: {{"Response": "I have fetched the users for you!", "Query": "query userPage($skip: Int, $limit: Int, $where: UserInputWhereFilter) {{userPage(skip: $skip, limit: $limit, where: $where) {{id name memberships {{id group {{ id name }}}}}}}}", "Variables": {{{{"where": {{"name": {{"_startswith": "Z"}}}},"skip": 0,"limit": 100}}}}}}
            Example 2: {{"Response": "PC is short for personal computer.", "Query": "", "Variables": ""}}
        2. Build a new query before running it against the API.
        3. You build the graphql queries only using available kernel_functions.
        4. Always use detectGraphQLTypes function to get the graphql_types variable. This ensures the correct types are identified for the query.
        5. After successfully retrieving data, your final response must be a valid JSON object. If a GraphQL query was used, the JSON must contain the retrieved data labeled as "Response" and the GraphQL query used labeled as "Query" also with . If no GraphQL query was used, the "Response" field contains your full response as a string, and the "Query" field must be an empty string.
        6. Check for correct brackets in JSON response before replying.
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
        history.add_system_message(system_prompt)

        return result

    return hook


async def main():
    gqlClient = None
    gqlClient = await createGQLClient(
        username="john.newbie@world.com", password="john.newbie@world.com"
    )

    skills = []
    for plugin in kernel.plugins.values():
        skills.extend(plugin.functions.keys())

    print(f"Loaded skills: {skills}")

    # for pname, plugin in kernel.plugins.items():
    #     print(f"Plugin: {pname}")
    #     print("  Functions:", list(plugin.functions))

    history = ChatHistoryTruncationReducer(target_count=12)
    execution_settings = AzureChatPromptExecutionSettings()
    execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()

    async def inject_gql_client(context: AutoFunctionInvocationContext, next):
        context.arguments["gqlclient"] = gqlClient
        await next(context)

    kernel.add_filter(FilterTypes.AUTO_FUNCTION_INVOCATION, inject_gql_client)

    # kernel.add_filter(
    #     filter_type=FilterTypes.AUTO_FUNCTION_INVOCATION,
    #     filter=add_user_context_filter
    # )
    # extra_context = {"foo": "bar", "chat_history": "chat_history", "gqlclient": gqlClient}

    # from semantic_kernel.agents import ChatCompletionAgent
    # agent = ChatCompletionAgent(
    #     kernel=kernel,
    #     service=azure_chat,
    #     name="OrchestratorAgent",
    #     # instructions="You may call programPage(limit:int,skip:int) when needed.",
    #     instructions="",
    #     arguments=KernelArguments(extraContext=extra_context),

    # )
    # extra_context = KernelArguments({"foo": "bar", "chat_history": history})

    # fn = kernel.get_function(
    #     plugin_name="graphql",
    #     function_name="detectTypes"
    # )
    # print(f"fn: {fn}")
    # try:
    #     result = await kernel.invoke(fn, user_prompt="najdi členy skupiny")
    #     print(f"result: {result}")
    # except Exception as e:
    #     print(e)
    while True:
        user_input = input("Uživatel: ")
        if user_input == "exit":
            break
        history.add_user_message(user_input)
        # print(f"history: {history.serialize()}")
        # https://learn.microsoft.com/en-us/semantic-kernel/concepts/ai-services/chat-completion/function-calling/?pivots=programming-language-python
        result = await azure_chat.get_chat_message_content(
            chat_history=history,
            settings=execution_settings,
            kernel=kernel,
            # context_variables={"extraContext": extra_context}
            arguments=KernelArguments(),
        )
        history.add_assistant_message(f"{result}")
        history.reduce()

        # vrat mi 5 studijnich programu
        #
        # result = await agent.get_response(

        #     user_input,
        #     kernel=kernel,
        #     arguments=KernelArguments(extraContext=extra_context)
        #     # history=history,
        #     # settings=execution_settings
        # )

        # result = await kernel.invoke_prompt(
        #     prompt=user_input,                      # text od uživatele
        #     history=history,                        # vaše ChatHistory
        #     settings=execution_settings,            # AzureChatPromptExecutionSettings s Auto()
        #     arguments=KernelArguments(
        #         extraContext=extra_context          # sem napochytíte user_id, extraContext, …
        #     )
        # )
        # azure_chat.
        # result = await kernel.invoke_prompt(
        #     prompt=user_input
        #     # function_name=None,
        #     # plugin_name=None,
        #     # arguments={"user_input": user_input}
        # )

        # def display(value: ChatMessageContent):
        #     print("="*30)
        #     print(value)
        #     print("="*30)
        #     # print(value.content)
        #     # value.content.
        #     print("="*30)
        #     print(f'usage: {value.metadata.get("usage")}')

        # if hasattr(result, "value"):
        #     if isinstance(result.value, list):
        #         for value in result.value:
        #             display(value)
        #     else:
        #         display(value)

        print(f"Assistant: {result}")


# asyncio.run(main())
