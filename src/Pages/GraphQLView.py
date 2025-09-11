import json
import logging
from nicegui import ui
from src.Utils.graphQLdata import GraphQLData


def build_graphql_ui(parent, gql_client):
    """Vykreslí GraphQL browser panel do daného parent kontejneru.
    Očekává inicializovaný gql_client (nebo None – zobrazí varování).
    """
    log_gql = logging.getLogger("graphql")

    with parent:
        ui.label("GraphQL browser").classes("font-bold mb-2")

        default_query = """
            query ListItems($skip: Int, $limit: Int) {
              items(skip: $skip, limit: $limit) {
                id
                name
                createdAt
              }
            }
        """.strip()

        query_input = ui.textarea(label="GraphQL query", value=default_query).props(
            "rows=10"
        )
        variables_input = ui.textarea(
            label='Variables (JSON, např. {"skip": 0, "limit": 10})',
            value='{"skip": 0, "limit": 10}',
        ).props("rows=4")

        gql_container = ui.column().classes("mt-2")

        async def run_graphql():
            gql_container.clear()

            if gql_client is None:
                with gql_container:
                    ui.markdown("> ⚠️ GraphQL klient ještě není inicializován.")
                return

            query = (query_input.value or "").strip()
            log_gql.info("GraphQL query run", extra={"preview": query[:100]})

            try:
                variables = (
                    json.loads(variables_input.value) if variables_input.value else {}
                )
                if not isinstance(variables, dict):
                    raise ValueError("Variables must be a JSON object")
            except Exception as e:
                with gql_container:
                    ui.markdown(f"> ❌ Chyba v JSON variables: `{e}`")
                return

            with gql_container:
                GraphQLData(
                    gqlclient=gql_client,
                    query=query,
                    variables=variables,
                    result=None,
                    metadata=None,
                    autoload=True,
                )

        ui.button("Run query", on_click=run_graphql).props("color=primary").classes(
            "mt-2"
        )
