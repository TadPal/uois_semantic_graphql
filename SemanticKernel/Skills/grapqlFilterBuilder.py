from typing import List, Tuple, Dict, Annotated, Any
import json

from semantic_kernel.functions import kernel_function
from semantic_kernel.functions import KernelArguments
from SemanticKernel.Skills.graphqlQueryBuilder import GraphQLQueryBuilder


class GraphQLFilterQueryPlugin:
    """
    Plugin for generating and running GraphQL queries with filter conditions.
    """

    @kernel_function(
        name="buildFilterQuery",
        # description="Builds a GraphQL query for fetching a list of entities with a 'where' filter."
    )
    def build_graphql_filter_query(
        self,
        graphql_types: Annotated[
            List[str],
            "The list of GraphQL object types to be included in the query, e.g., ['UserGQLModel', 'RoleGQLModel']",
        ],
        arguments: KernelArguments = None,
    ) -> str:
        """
            Builds a GraphQL query with a 'where' filter.

            This skill is designed to automatically generate a GraphQL query that can fetch
            a collection of entities (e.g., users, programs) and filter them based on
            a 'where' argument. This is particularly useful for searching or listing
            items that match specific criteria.

            Pro porovnání hodnot:

            _eq: Rovná se.

            _le: Menší nebo rovno.

            _lt: Menší než.

            _ge: Větší nebo rovno.

            _gt: Větší než.

            Příklad porovnání:

            {"where": {"number": {"_ge": 50000, "_le": 100000}}}

            Pro textová pole (stringy):

                _like: Podobné jako v SQL, umožňuje použití zástupných znaků (% a _).

                _ilike: Stejné jako _like, ale ignoruje velikost písmen (case-insensitive).

                _startswith: Začíná na.

                _endswith: Končí na.

        Příklad textového filtru:

        {"where": {"email": {"_ilike": "john%.com"}, "name": {"_startswith": "Jan"}}}

            Args:
              graphql_types: A list of GraphQL type names to build the query for.

            Returns:
              A GraphQL query string that includes a 'where' variable for filtering.
        """
        print(f"build_graphql_filter_query(graphql_types={graphql_types})")
        builder = GraphQLQueryBuilder(disabled_fields=["createdby", "changedby"])
        query = builder.build_query_vector(graphql_types)
        # The generated query should already include the `where` argument
        # as part of the query vector definition. The `run_graphql_filter_query`
        # skill will handle the actual execution with the provided variables.

        # The result from build_query_vector should be suitable for use with a filter.
        # We need to ensure that the returned query has the correct structure for
        # passing variables. The builder is expected to handle this.

        return builder.explain_graphql_query(query)

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
          graphql_variables: A JSON string of variables, e.g., '{userPage(where: {email: {_like: "%.com"}}, skip:0, limit:2)'.


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
