from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, AzureChatPromptExecutionSettings
from semantic_kernel.connectors.ai import FunctionChoiceBehavior
from semantic_kernel.contents import ChatHistory
from semantic_kernel.functions import KernelArguments

from typing import Annotated, List, Optional, Dict

CHAIN = ["EventGQLModel","UserGQLModel","PresenceGQLModel","PresenceTypeGQLModel"]

#! Simulace modelů
FIELD_MAP = {
    "EventGQLModel": ["id", "name"],
    "PresenceGQLModel": ["id"],
    "UserGQLModel": ["id", "name", "surname"],
    "PresenceTypeGQLModel": ["id", "name"],
}

#! Simulace vazeb mezi modely
LINK_MAP = {
    "EventGQLModel": [("presences", "PresenceGQLModel")],
    "PresenceGQLModel": [("user","UserGQLModel"), ("presenceType","PresenceTypeGQLModel")],
}

class QueryBuilder:
    def _block(name: str, inner_lines: List[str], indent: int = 2) -> str:
        pad = " " * indent
        inner = ("\n" + " " * (indent + 2)).join(inner_lines)
        return f"""{name} {{
    {pad}  {inner}
    {pad}}}"""

    #? nahradit funkcí, přistupující do DB
    def _selection_for_type(type_name: str) -> List[str]:
        return FIELD_MAP.get(type_name, ["id"])

    def _build_nested(parent_type: str, requested: set[str], seen: set[tuple]) -> List[str]:
        out: List[str] = []
        for field_name, child_type in LINK_MAP.get(parent_type, []):
            if child_type not in requested:
                continue
            if (parent_type, child_type) in seen:
                continue
            seen.add((parent_type, child_type))

            child_scalars = QueryBuilder._selection_for_type(child_type)
            child_blocks = QueryBuilder._build_nested(child_type, requested, seen)
            lines = child_scalars + child_blocks
            out.append(QueryBuilder._block(field_name, lines, indent=4))
        return out

class GraphQLQueryPlugin:
    """Return queries"""

    @kernel_function(
        name="buildVectorQuery",
        description="Vrátí GraphQL dotaz podle CHAIN (Event→User→Presence→PresenceType)."
    )
    async def build_vector_query(
        self,
        graphql_types: Annotated[List[str], "Seznam GraphQL typů. První je kořen."]
    ) -> str:
        if not graphql_types:
            raise ValueError("graphql_types must not be empty")
        if graphql_types != CHAIN:
            print(f"[WARN] Neočekávaný chain: {graphql_types}")

        root_type = graphql_types[0]
        requested = set(graphql_types)

        root_scalars = QueryBuilder._selection_for_type(root_type)
        nested_blocks = QueryBuilder._build_nested(root_type, requested, seen=set())

        event_inner = root_scalars + nested_blocks
        root_block = QueryBuilder._block("eventPage", event_inner, indent=2)

        query = f"""query Test {{
          {root_block}
        }}"""
        return query
    

if __name__ == "__main__":
    import asyncio

    plugin = GraphQLQueryPlugin()
    q = asyncio.run(
        plugin.build_vector_query(["EventGQLModel","UserGQLModel","PresenceGQLModel","PresenceTypeGQLModel"])
    )
    print("\n[RETURNED]:\n", q)
