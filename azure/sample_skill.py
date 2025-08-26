from semantic_kernel.functions import kernel_function
from semantic_kernel.functions import KernelArguments
from typing import Annotated, List


class GraphQLBuilderPlugin:
    @kernel_function(
        name="buildVectorQuery",
        # description="Automaticaly generated skill for acces to graphql endpoint from sdl for Query.programPage."
    )
    # 2️⃣ Define the native skill function
    def graphql_vetor_query_builder_skill(
        self,
        graphql_types: Annotated[
            List[str],
            "List of GraphQL output type names, e.g. ['ProgramGQLModel','StudentGQLModel']",
        ],
        arguments: KernelArguments = None,
    ) -> str:
        """
        Build a GraphQL query to fetch multiple entities (vector) based on the supplied types.

        Args:
          graphql_types: ordered list of type names, where the first element is the root field
          arguments.sdl_doc: AST of the GraphQL SDL (DocumentNode)

        Returns:
          A nested GraphQL query string selecting each type in turn.
        """
        # types = json.loads(graphgql_types)
        # types = payload["types"]
        # sdl = payload["sdl"]
        print(f"graphql_vetor_query_builder_skill(graphgql_types={graphql_types})")
        builder = GraphQLQueryBuilder(disabled_fields=["createdby", "changedby"])
        return builder.build_query_vector(graphql_types)
