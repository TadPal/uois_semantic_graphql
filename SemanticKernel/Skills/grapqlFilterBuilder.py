from semantic_kernel.functions import kernel_function, KernelArguments
from semantic_kernel.prompt_template import PromptTemplateConfig
from semantic_kernel.kernel import Kernel
from pathlib import Path
import json
import graphql
import os

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
account = os.getenv("AZURE_COGNITIVE_ACCOUNT_NAME", "")
model_name = os.getenv("AZURE_CHAT_DEPLOYMENT_NAME", "") or "summarization-deployment"
endpoint = f"https://{account}.openai.azure.com"

from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import (
    AzureChatCompletion,
)

from semantic_kernel.contents.chat_history import ChatHistory

azure_chat = AzureChatCompletion(
    service_id="azure-gpt4",
    api_key=OPENAI_API_KEY,
    endpoint=endpoint,
    deployment_name=model_name,
    # api_version="2024-02-15-preview"  # nebo verze, co máš v Azure portálu
    api_version="2024-02-01",
)

kernel = Kernel(
    services=[
        # azure_orchestrator,
        azure_chat,
    ],
)

from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)

from semantic_kernel.connectors.ai.function_choice_behavior import (
    FunctionChoiceBehavior,
)

execution_settings = AzureChatPromptExecutionSettings()
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()


class GraphQLBuilderPlugin:
    @kernel_function(
        name="build_filter_variable",
    )
    async def build_filter_variable(
        self,
        user_prompt: str,
        arguments: KernelArguments = None,
    ) -> str:
        """

        Args:
          user_prompt: full string representation of users prompt
          kernel: own Kernel instance
          arguments.sdl_doc: AST of the GraphQL sdl (DocumentNode)

        Returns:
          An ordered list of GQL types names
        """

        # sdl = fetch_sdl()
        # ast = graphql.parse(sdl)

        # result = {}
        # for node in ast.definitions:
        #     if isinstance(node, graphql.language.ast.ObjectTypeDefinitionNode):
        #         name = node.name.value
        #         if "Error" in name:
        #             continue
        #         description = node.description.value if node.description else None
        #         result[name] = {"name": name, "description": description}

        # result = list(result.values())

        prompt = f"""
        You are given a user's natural-language request and a GraphQL schema (as JSON below).
        Your task: build a **GraphQL `where` filter JSON object** that matches the user's intent.

        Return **only** a valid JSON object representing the `where` filter — **no extra text, no code fences**.
        Do **not** include pagination, order, selection sets, or fields not present in the schema.

        Rules:

        1. **Fields & Types**

        * Use only fields that exist on the inferred root type (based on the user's domain words and the schema).
        * Prefer exact field-name matches; otherwise map common synonyms using field descriptions.
        * If a field is unknown, omit it.

        2. **Operators (map from user phrasing)**

        _eq: String – operation for select.filter() method
        _le: String – operation for select.filter() method
        _lt: String – operation for select.filter() method
        _ge: String – operation for select.filter() method
        _gt: String – operation for select.filter() method
        _like: String – operation for select.filter() method
        _ilike: String – operation for select.filter() method
        _startswith: String – operation for select.filter() method
        _endswith: String – operation for select.filter() method

        3. **Values**

        * Trim whitespace; keep user’s diacritics.
        * For partial-text operators (`_like`, `_ilike`, `_nlike`, `_nilike`), always add `%` wildcards as shown above.
        * For numeric and boolean fields, coerce literals when unambiguous.
        * For dates, prefer ISO strings (`YYYY-MM-DD`) if a concrete date is given.

        \[EXAMPLE]
        prompt:
        "Najdi mi x uživatelů, obsahující Zde"
        output:
        {"name": {"_like": "%Zde%"}}
        \[END EXAMPLE]
        """

        history = ChatHistory()

        history.add_system_message(prompt)
        history.add_user_message(user_prompt)
        result = await azure_chat.get_chat_message_content(
            chat_history=history,
            settings=execution_settings,
            kernel=kernel,
            arguments=KernelArguments(),
        )

        print(result)
        return result
