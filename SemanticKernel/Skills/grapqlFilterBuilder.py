from typing import List, Tuple, Dict, Annotated, Any
import json
import os
import sys
from graphql.language.ast import (
    TypeNode,
    DocumentNode,
    NamedTypeNode,
    NonNullTypeNode,
    ListTypeNode,
    ObjectTypeDefinitionNode,
    ScalarTypeDefinitionNode,
    UnionTypeDefinitionNode,
)

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
top_level = os.path.dirname(parent_dir)
sys.path.insert(0, top_level)

from semantic_kernel.functions import kernel_function
from semantic_kernel.functions import KernelArguments
from SemanticKernel.Skills.graphqlQueryBuilder import GraphQLQueryBuilder


class GraphQLFilterQueryPlugin:
    """
    Plugin for generating and running GraphQL queries with filter conditions.
    """

    @kernel_function(
        name="findFilterVariables",
    )
    def find_filter_variables(
        self,
        graphql_types: Annotated[
            List[str],
            "The list of GraphQL types to be searched for available variables, e.g., ['UserGQLModel', 'RoleGQLModel']",
        ],
        disabled_fields=["createdby", "changedby", "memberOf"],
        arguments: KernelArguments = None,
    ) -> str:
        """
        Finds filterable variables for desired GraphQL types and their filter options which can be used to build a 'where' variable.

        Args:
          graphql_types: The list of GraphQL types to be searched for available variables, e.g., ['UserGQLModel', 'RoleGQLModel']

        Returns:
          A json structure with filtrable variables and their filter options.
        """

        def unwrap_type(t):
            # Unwrap AST type nodes (NonNull, List) to get NamedTypeNode
            while isinstance(t, (NonNullTypeNode, ListTypeNode)):
                t = t.type
            if isinstance(t, NamedTypeNode):
                return t.name.value
            raise TypeError(f"Unexpected type node: {t}")

        def build_adjacency(
            ast, disabled_fields: list[str]
        ) -> Dict[str, List[Tuple[str, str]]]:
            edges: Dict[str, List[Tuple[str, str]]] = {}
            for defn in ast.definitions:
                if hasattr(defn, "fields"):
                    from_type = defn.name.value
                    for field in defn.fields:
                        if field.name.value in disabled_fields:
                            continue
                        to_type = unwrap_type(field.type)
                        edges.setdefault(from_type, []).append(
                            (field.name.value, to_type)
                        )
            return edges

        def extract_filter_inputs(ast) -> dict[str, list[str]]:
            """
            Extract available filter input types (e.g. StrFilter) and their operators
            from the SDL AST.
            Example:
            {
                "StrFilter": ["_eq", "_le", "_lt", "_ge", "_gt", "_like", "_ilike", "_startswith", "_endswith"]
            }
            """
            filters: dict[str, list[str]] = {}
            for defn in ast.definitions:
                if defn.kind == "input_object_type_definition":
                    input_name = defn.name.value
                    if "Filter" in input_name or "filter" in input_name:
                        operators = [field.name.value for field in defn.fields]
                        filters[input_name] = operators
            return filters

        def get_filterable_fields_with_ops(
            ast, adjacency
        ) -> dict[str, dict[str, list[str]]]:
            """
            Return fields and their supported filter operators, using SDL filter inputs.
            """
            filter_inputs = extract_filter_inputs(ast)

            SCALAR_TO_FILTER = {
                "String": "StrFilter",
                "UUID": "UuidFilter",
                "Int": "IntFilter",
                "DateTime": "DateTimeFilter",
                "Boolean": "BoolFilter",
            }

            result: dict[str, dict[str, list[str]]] = {}

            for type_name, fields in adjacency.items():
                if type_name not in graphql_types:  # only process requested types
                    continue

                for field_name, field_type in fields:
                    if field_type in SCALAR_TO_FILTER:
                        filter_type = SCALAR_TO_FILTER[field_type]
                        if filter_type in filter_inputs:
                            result.setdefault(type_name, {})[field_name] = (
                                filter_inputs[filter_type]
                            )

            return result

        print(f"find_filter_variables(graphql_types={graphql_types})")
        from sdl.sdl_fetch import fetch_sdl
        from graphql import parse, build_ast_schema

        sdl = fetch_sdl()
        ast = parse(sdl)
        adjacency = build_adjacency(ast=ast, disabled_fields=disabled_fields)

        result = get_filterable_fields_with_ops(ast, adjacency)
        print(result)
        return result

    @kernel_function(
        name="runFilterQuery",
        description="Runs a GraphQL query with a 'where' filter and optional pagination.",
    )
    async def run_graphql_filter_query(
        self,
        graphql_query: Annotated[
            str,
            "The full GraphQL query string with a '$where' variable and optional '$skip' and '$limit' variables.",
        ],
        graphql_variables: Annotated[
            str,
            "A JSON string containing the variables for the query, including the 'where' filter.",
        ],
        arguments: KernelArguments = None,
    ) -> str:
        """
        Runs a GraphQL query with a 'where' filter and optional pagination.

        This skill takes a pre-built GraphQL query and a set of variables, allowing
        for flexible filtering of data.

        Args:
          graphql_query: The complete GraphQL query string.
          graphql_variables: A JSON string of variables, e.g., '{"where":{"name":{"_ilike":"Zdeňka%"}},"limit":1}'.


        Returns:
          The list of filtered entities as a JSON string.
        """
        print(f"run_graphql_filter_query graphql_variables: {graphql_variables}")
        try:
            variables = json.loads(graphql_variables)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON variables: {e}")
            return f"Error: Invalid JSON variables provided. {e}"

        # Ensure that `gqlclient` is available in the arguments from the kernel context.
        gqlclient = arguments.get("gqlclient")
        if not gqlclient:
            return "Error: gqlclient not found in arguments. This skill requires a GraphQL client."

        # The GraphQL client is expected to handle the query and variables.
        rows = await gqlclient(query=graphql_query, variables=variables)

        assert "data" in rows, f"the response does not contain the data key {rows}"
        data = rows["data"]

        # The result should be a list of entities, so we just return the value of the first key.
        # This assumes the query returns a single root field that is a list.
        _, entities = next(iter(data.items()))

        return json.dumps(entities, indent=2, ensure_ascii=False)
