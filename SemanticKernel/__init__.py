import asyncio
from pathlib import Path

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from semantic_kernel.connectors.ai.function_choice_behavior import (
    FunctionChoiceBehavior,
)
from semantic_kernel.contents.chat_history import ChatHistory

from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)

from dotenv import load_dotenv

load_dotenv()

from semantic_kernel.functions import KernelPlugin
from semantic_kernel import Kernel
from semantic_kernel.exceptions import PluginInitializationError
from pathlib import Path

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


from semantic_kernel import Kernel
from semantic_kernel.prompt_template.prompt_template_config import PromptTemplateConfig
from semantic_kernel.functions.kernel_function_from_prompt import (
    KernelFunctionFromPrompt,
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
from semantic_kernel.processes.kernel_process import (
    KernelProcessStep,
    KernelProcessStepContext,
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


from semantic_kernel.contents.chat_message_content import ChatMessageContent

# from semantic_kernel import KernelArguments
from semantic_kernel.functions import KernelArguments
from semantic_kernel.filters import FilterTypes, AutoFunctionInvocationContext


async def openChat():
    gqlClient = None
    gqlClient = await createGQLClient(
        username="john.newbie@world.com", password="john.newbie@world.com"
    )

    skills = []
    for plugin in kernel.plugins.values():
        skills.extend(plugin.functions.keys())
        print(skills)

    history = ChatHistory()

    system_prompt = f"""
    You are an assistant and your primary task is to help query databases using graphql.
    
    Rules:
    1. Build a new query before running it against the API.
    2. You build the graphql queries only using available kernel_functions. 
    3. Every time the query returns with an Error you provide the used query in your response.
    4. Never use graphqlFilterBuilder with id.
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

    def trim_history(history: "ChatHistory", max_msgs: int = 20):
        from src.Utils.extract_history import extract_prompts_from_chat_xml

        prompts = {}
        try:
            prompts = extract_prompts_from_chat_xml(f"{history}")
            preserved = [
                {"role": "system", "items": [{"content_type": "text", "text": p}]}
                for p in prompts["system_prompts"]
            ]
            users_prompts = [
                {"role": "user", "items": [{"content_type": "text", "text": p}]}
                for p in prompts["user_prompts"]
            ]
            assistant_prompts = [
                {"role": "assistant", "items": [{"content_type": "text", "text": p}]}
                for p in prompts["assistant_prompts"]
            ]
            queries = [
                {"role": "assistant", "items": [{"content_type": "text", "text": p}]}
                for p in prompts["tool_prompts"]
            ]
            others = [
                item for pair in zip(users_prompts, assistant_prompts) for item in pair
            ]

            # Keep the last (max_msgs - len(preserved)) non-system messages
            to_keep = (
                preserved + others[-max(0, max_msgs - len(preserved)) :] + queries[-1:]
            )

            # Reset the history and add back the trimmed messages
            history.clear()
            for msg in to_keep:
                history.add_message(msg)
        except Exception as e:
            print(f"History couldn't be trimmed! {e}")

    # user_input = yield "Chat session initialized. Zadejte dotaz nebo 'exit'."
    async def hook(user_input):
        history.add_user_message(user_input)
        result = await azure_chat.get_chat_message_content(
            chat_history=history,
            settings=execution_settings,
            kernel=kernel,
            arguments=KernelArguments(),
        )
        history.add_assistant_message(f"{result}")
        trim_history(history)
        return result

    return hook


async def main():
    import openai

    gqlClient = None
    gqlClient = await createGQLClient(
        username="john.newbie@world.com", password="john.newbie@world.com"
    )

    skills = []
    for plugin in kernel.plugins.values():
        skills.extend(plugin.functions.keys())
        print(skills)

    # for pname, plugin in kernel.plugins.items():
    #     print(f"Plugin: {pname}")
    #     print("  Functions:", list(plugin.functions))

    history = ChatHistory()
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

    def trim_history(history: "ChatHistory", max_msgs: int = 20):
        from src.Utils.extract_history import extract_prompts_from_chat_xml

        prompts = {}
        try:
            prompts = extract_prompts_from_chat_xml(f"{history}")
            preserved = [
                {"role": "system", "items": [{"content_type": "text", "text": p}]}
                for p in prompts["system_prompts"]
            ]
            users_prompts = [
                {"role": "user", "items": [{"content_type": "text", "text": p}]}
                for p in prompts["user_prompts"]
            ]
            assistant_prompts = [
                {"role": "assistant", "items": [{"content_type": "text", "text": p}]}
                for p in prompts["assistant_prompts"]
            ]
            queries = [
                {"role": "tool", "items": [{"content_type": "text", "text": p}]}
                for p in prompts["tool_prompts"]
            ]

            others = [
                item for pair in zip(users_prompts, assistant_prompts) for item in pair
            ]

            # Keep the last (max_msgs - len(preserved)) non-system messages
            to_keep = (
                preserved + others[-max(0, max_msgs - len(preserved)) :] + queries[-1:]
            )

            # Reset the history and add back the trimmed messages
            history.clear()
            for msg in to_keep:
                history.add_message(msg)
        except Exception as e:
            print(f"History couldn't be trimmed! {e}")

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
        trim_history(history)

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


def create_graphql_detection_skill(kernel: Kernel):

    import json
    import graphql
    from sdl.sdl_fetch import fetch_sdl

    sdl = fetch_sdl()
    ast = graphql.parse(sdl)

    result = {}
    for node in ast.definitions:
        if isinstance(node, graphql.language.ast.ObjectTypeDefinitionNode):
            name = node.name.value
            if "Error" in name:
                continue
            description = node.description.value if node.description else None
            result[name] = {"name": name, "description": description}

    result = list(result.values())
    prompt = f"""
<message role="system">
    You have to pair objects mentioned by the user with GraphQL types described in the JSON below.
    Analyze the user prompt and return only valid JSON: an array of strings exactly matching the types' `name`.
    Respond with a single JSON array—no additional text, no code fences.

    Rules:
    1. Exclude any types whose names end with `"Error"`, unless explicitly requested.
    2. Match on type name or on keywords found in the description.
    3. Detect 1:N (one-to-many) or N:1 relationships between the matched types, and order the array so that each parent type appears immediately before its child types.
    4. If there any type is provided with an id it must be the root (first) type.

    [EXAMPLE]
    prompt:
        "Give me a list of study programs and their students"
    output:
        ["ProgramGQLModel", "StudentGQLModel"]
    [END EXAMPLE]

    [GRAPHQLTYPES] 
```json
    {json.dumps(result, indent=2)}
```
    [END GRAPHQLTYPES] 


</message>
<message role="user">{{{{user_prompt}}}}</message>
"""
    prompt_path = Path(__file__).parent / "./types_prompt.txt"
    prompt_path = prompt_path.resolve()
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)

    # graphql_detection_skill = KernelFunctionFromPrompt.from_prompt(
    #     function_name="graphql_detection_skill",
    #     plugin_name="graphql",
    #     prompt=prompt
    # )

    # kernel.add_function(
    #     plugin_name="graphql",
    #     # function=graphql_detection_skill,
    #     prompt=prompt,
    #     description=""
    # )

    ptc = PromptTemplateConfig(
        template=prompt,
        name="graphql_detection",
        template_format="handlebars",
        # execution_settings=req
    )

    # print("=== RENDERED PROMPT ===")
    # print(prompt.replace("user_prompt", "najdi členy skupiny"))
    # print("=======================")

    graphql_fn = kernel.add_function(
        function_name="detectTypes",
        plugin_name="graphql",
        prompt_template_config=ptc,
        description="Detect GraphQL types from a user query, it is usefull when user want to query for data.",
    )
    return graphql_fn


def explain_graphql_query(schema_ast, query):
    from graphql import parse, build_ast_schema, print_ast, GraphQLSchema
    from graphql.language.ast import (
        DocumentNode,
        FieldNode,
        SelectionSetNode,
        OperationDefinitionNode,
        FragmentDefinitionNode,
        FragmentSpreadNode,
        InlineFragmentNode,
        ArgumentNode,
        VariableNode,
        ObjectValueNode,
        ObjectFieldNode,
        ListValueNode,
    )
    from graphql.type import (
        GraphQLObjectType,
        GraphQLInterfaceType,
        GraphQLUnionType,
        GraphQLNonNull,
        GraphQLList,
        GraphQLInputObjectType,
        GraphQLEnumType,
        GraphQLScalarType,
        GraphQLInputType,
        GraphQLNamedType,
    )

    schema: GraphQLSchema = build_ast_schema(schema_ast, assume_valid=True)

    # ---- popisy polí pro Object i Interface (výstup)
    field_meta: dict[tuple[str, str], str | None] = {}
    from graphql.language.ast import (
        ObjectTypeDefinitionNode,
        InterfaceTypeDefinitionNode,
    )

    for defn in schema_ast.definitions:
        if isinstance(defn, (ObjectTypeDefinitionNode, InterfaceTypeDefinitionNode)):
            parent = defn.name.value
            for fld in defn.fields or []:
                desc = fld.description.value if fld.description else None
                field_meta[(parent, fld.name.value)] = desc

    query_ast: DocumentNode = parse(query)

    # ---- definice fragmentů (vstup i výstup)
    fragments: dict[str, FragmentDefinitionNode] = {
        d.name.value: d
        for d in query_ast.definitions
        if isinstance(d, FragmentDefinitionNode)
    }

    # ---------- UTILS ----------

    def unwrap(gtype: GraphQLInputType | GraphQLNamedType):
        while isinstance(gtype, (GraphQLNonNull, GraphQLList)):
            gtype = gtype.of_type
        return gtype

    def type_to_str(gtype) -> str:
        if isinstance(gtype, GraphQLNonNull):
            return f"{type_to_str(gtype.of_type)}!"
        if isinstance(gtype, GraphQLList):
            return f"[{type_to_str(gtype.of_type)}]"
        return getattr(gtype, "name", str(gtype))

    def type_node_to_str(type_node) -> str:
        k = getattr(type_node, "kind", None) or type_node.kind
        if k in ("NamedType", "named_type"):
            return type_node.name.value
        if k in ("NonNullType", "non_null_type"):
            return f"{type_node_to_str(type_node.type)}!"
        if k in ("ListType", "list_type"):
            return f"[{type_node_to_str(type_node.type)}]"
        raise ValueError(f"Unknown kind {k}")

    # ---------- 1) @param: popisy proměnných + (nově) mapování proměnná → skutečný input typ ----------

    # Proměnná může být použita kdekoli (i uvnitř objektů). Najdeme všechny použití a určíme typ.
    var_to_input_type: dict[str, GraphQLInputType] = {}

    def map_variable_usage_in_args(sel: FieldNode, parent_type):
        """Promapuje VariableNode ve všech argumentech fieldů (vč. vnořených objektů)."""
        if not isinstance(parent_type, (GraphQLObjectType, GraphQLInterfaceType)):
            return
        fdef = parent_type.fields.get(sel.name.value)
        if not fdef:
            return
        # Pro každý argument v AST porovnej s typem z fdef.args a rekurzivně projdi hodnoty:
        for arg in sel.arguments or []:
            arg_name = arg.name.value
            arg_def = fdef.args.get(arg_name)
            if not arg_def:
                continue

            def walk_value(value_node, expected_type: GraphQLInputType):
                if isinstance(value_node, VariableNode):
                    var_to_input_type[value_node.name.value] = expected_type
                    return
                unwrapped = unwrap(expected_type)
                if isinstance(value_node, ObjectValueNode) and isinstance(
                    unwrapped, GraphQLInputObjectType
                ):
                    # projdi pole objektu
                    for of in value_node.fields or []:
                        f: ObjectFieldNode = of
                        if f.name.value in unwrapped.fields:
                            walk_value(f.value, unwrapped.fields[f.name.value].type)
                elif isinstance(value_node, ListValueNode) and isinstance(
                    expected_type, GraphQLList
                ):
                    # každý prvek seznamu má typ .of_type
                    for v in value_node.values or []:
                        walk_value(v, expected_type.of_type)
                # skalár/enum: nic dalšího

            walk_value(arg.value, arg_def.type)

    # Projdi celý selection strom a hledej použití proměnných u argumentů
    def walk_for_var_types(sel_set: SelectionSetNode, parent_type):
        if not sel_set:
            return
        for sel in sel_set.selections:
            if isinstance(sel, FieldNode):
                map_variable_usage_in_args(sel, parent_type)
                # rekurze do dítěte
                if isinstance(parent_type, (GraphQLObjectType, GraphQLInterfaceType)):
                    fdef = parent_type.fields.get(sel.name.value)
                    if fdef and sel.selection_set:
                        walk_for_var_types(sel.selection_set, unwrap(fdef.type))
            elif isinstance(sel, FragmentSpreadNode):
                frag = fragments.get(sel.name.value)
                if frag:
                    new_parent = parent_type
                    if frag.type_condition:
                        tname = frag.type_condition.name.value
                        new_parent = schema.get_type(tname) or parent_type
                    walk_for_var_types(frag.selection_set, new_parent)
            elif isinstance(sel, InlineFragmentNode):
                new_parent = parent_type
                if sel.type_condition:
                    tname = sel.type_condition.name.value
                    new_parent = schema.get_type(tname) or parent_type
                walk_for_var_types(sel.selection_set, new_parent)

    for defn in query_ast.definitions:
        if isinstance(defn, OperationDefinitionNode):
            op = getattr(defn.operation, "value", defn.operation)
            root = {
                "query": schema.query_type,
                "mutation": schema.mutation_type,
                "subscription": schema.subscription_type,
            }.get(op)
            if root:
                walk_for_var_types(defn.selection_set, root)

    # @param řádky (původní + přesnější typy)
    var_lines: list[str] = []
    for defn in query_ast.definitions:
        if isinstance(defn, OperationDefinitionNode) and defn.variable_definitions:
            for vdef in defn.variable_definitions:
                name = vdef.variable.name.value
                # preferuj typ podle skutečného použití:
                gtype = var_to_input_type.get(name)
                type_str = type_to_str(gtype) if gtype else type_node_to_str(vdef.type)

                base_named = unwrap(gtype) if gtype is not None else None
                desc = (
                    getattr(base_named, "description", None)
                    if base_named
                    else "missing description"
                )
                desc = desc.replace("\n", "\n#\t")
                # desc = "\n#\t ".join(desc.split()) if desc else "missing description"

                # desc = field_meta.get((parent_type.name, fname))
                # zkus popis z odpovídajícího InputObjectField, pokud máme typ i shodu jména pole
                # (nelze spolehlivě – proměnná nemusí odpovídat názvu input fieldu)
                var_lines.append(f"# @param {{{type_str}}} {name} - {desc}")

    # ---------- 2) @input: struktura proměnných (včetně vnoření a rekurze) ----------

    input_lines: list[str] = []

    def append_input_line(path: str, gtype: GraphQLInputType, descr: str | None = None):
        d = (" - " + " ".join(descr.split())) if descr else ""
        input_lines.append(f"# @input {{{type_to_str(gtype)}}} {path}{d}")

    def describe_input_type(
        path: str,
        gtype: GraphQLInputType,
        visiting: set[str] | None = None,
        depth: int = 0,
        max_depth: int = 1,
    ):
        """Vypíše strukturu input typu; chrání se proti rekurzi."""
        if depth > max_depth:
            input_lines.append(f"# @input {{...}} {path} - (truncated)")
            return
        visiting = visiting or set()

        if isinstance(gtype, GraphQLNonNull) or isinstance(gtype, GraphQLList):
            # vypiš wrapper typ a pokračuj do vnitřku
            append_input_line(path, gtype)
            inner = gtype.of_type
            # pro seznam můžeme označit subpath jako path[] (jen esteticky)
            child_path = path + "[]" if isinstance(gtype, GraphQLList) else path
            describe_input_type(child_path, inner, visiting, depth + 1, max_depth)
            return

        base = unwrap(gtype)

        # Enum: vypiš s výčtem hodnot
        if isinstance(base, GraphQLEnumType):
            vals = "|".join(v.name for v in base.values.values())
            append_input_line(path, gtype, f"enum: {vals}")
            return

        # Scalar: jen řádka
        if isinstance(base, GraphQLScalarType):
            append_input_line(path, gtype)
            return

        # Input objekt
        if isinstance(base, GraphQLInputObjectType):
            if base.name in visiting:
                append_input_line(path, gtype, f"(recursive {base.name})")
                return
            visiting.add(base.name)

            # nejdřív řádek pro samotný uzel
            append_input_line(path, gtype, base.description)

            # potom pole
            for fname, fdef in base.fields.items():
                fpath = f"{path}.{fname}"
                append_input_line(fpath, fdef.type, fdef.description)
                # rekurze jen pokud je to zase objekt
                if isinstance(unwrap(fdef.type), GraphQLInputObjectType) or isinstance(
                    unwrap(fdef.type), GraphQLList
                ):
                    describe_input_type(
                        fpath, fdef.type, visiting, depth + 1, max_depth
                    )

            visiting.remove(base.name)
            return

        # Fallback
        append_input_line(path, gtype)

    # spusť popis pro každou proměnnou, kterou jsme našli v dotazu
    # for var_name, gtype in var_to_input_type.items():
    #     describe_input_type(var_name, gtype)

    # ---------- 3) @property výstup (s fragmenty) ----------

    out_lines: list[str] = []
    seen: set[tuple[str, str]] = set()

    def print_field(parent_type, fname: str, path: str):
        if isinstance(parent_type, (GraphQLObjectType, GraphQLInterfaceType)):
            fld_def = parent_type.fields.get(fname)
        else:
            fld_def = None
        if not fld_def:
            return
        base_type = unwrap(fld_def.type)
        base_name = getattr(base_type, "name", "Object")
        desc = field_meta.get((parent_type.name, fname)) or ""
        desc = " ".join(desc.split()) if desc else ""
        key = (path, base_name)
        if key in seen:
            return
        seen.add(key)
        out_lines.append(
            f"# @property {{{base_name}}} {path}" + (f" - {desc}" if desc else "")
        )

    def walk_out(sel_set: SelectionSetNode, parent_type, prefix: str):
        if not sel_set:
            return
        for sel in sel_set.selections:
            if isinstance(sel, FieldNode):
                fname = sel.name.value
                path = f"{prefix}.{fname}" if prefix else fname
                if isinstance(parent_type, GraphQLUnionType):
                    continue
                print_field(parent_type, fname, path)
                if sel.selection_set and isinstance(
                    parent_type, (GraphQLObjectType, GraphQLInterfaceType)
                ):
                    fdef = parent_type.fields.get(fname)
                    if fdef:
                        walk_out(sel.selection_set, unwrap(fdef.type), path)
            elif isinstance(sel, FragmentSpreadNode):
                frag = fragments.get(sel.name.value)
                if frag:
                    new_parent = parent_type
                    if frag.type_condition:
                        tname = frag.type_condition.name.value
                        new_parent = schema.get_type(tname) or parent_type
                    walk_out(frag.selection_set, new_parent, prefix)
            elif isinstance(sel, InlineFragmentNode):
                new_parent = parent_type
                if sel.type_condition:
                    tname = sel.type_condition.name.value
                    new_parent = schema.get_type(tname) or parent_type
                walk_out(sel.selection_set, new_parent, prefix)

    for defn in query_ast.definitions:
        if isinstance(defn, OperationDefinitionNode):
            op = getattr(defn.operation, "value", defn.operation)
            root = {
                "query": schema.query_type,
                "mutation": schema.mutation_type,
                "subscription": schema.subscription_type,
            }.get(op)
            if root:
                walk_out(defn.selection_set, root, "")

    # ---------- 4) Sestavení hlavičky + dotaz ----------

    header = []
    if var_lines:
        header.append("# ")
        header.extend(var_lines)
    if input_lines:
        header.append("# ")
        header.append("# @input structure")
        header.extend(input_lines)
    header.append("# @returns {Object}")
    if out_lines:
        header.append("# ")
        header.extend(out_lines)

    return "\n".join(header + ["", print_ast(query_ast)])


# explain_graphql_query()
# create_graphql_detection_skill(kernel=kernel)

# asyncio.run(main())
