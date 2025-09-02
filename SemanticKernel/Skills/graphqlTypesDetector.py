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
        name="detectGraphQLTypes",
    )
    async def create_types_list_skill(
        self,
        user_prompt: str,
        arguments: KernelArguments = None,
    ) -> str:
        """
        Build an ordered list of GQL types names based on GQL schema definition and provided user prompt.

        Args:
          user_prompt: full string representation of users prompt
          kernel: own Kernel instance
          arguments.sdl_doc: AST of the GraphQL sdl (DocumentNode)

        Returns:
          An ordered list of GQL types names
        """
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
        You have to pair objects mentioned by the user with GraphQL types described in the JSON below.
        Analyze the user prompt and return only valid JSON: an array of strings exactly matching the types' `name`.
        Respond with a single JSON array—no additional text, no code fences.

        Rules:
        1. Exclude any types whose names end with `"Error"`, unless explicitly requested.
        2. Match on type name or on keywords found in the description.
        3. Detect 1:N (one-to-many) or N:1 relationships between the matched types, and order the array so that each parent type appears immediately before its child types.
        4. If there is any type is provided with an id it must be the root type.

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
