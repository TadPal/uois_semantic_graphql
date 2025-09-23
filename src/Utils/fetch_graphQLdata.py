import typing
import json


async def fetch_graphql_data(
    gqlclient: typing.Callable[
        [str, typing.Dict[str, typing.Any]], typing.Awaitable[dict]
    ],
    query: str,
    variables: typing.Optional[typing.Dict[str, typing.Any]] = None,
) -> str:
    """
    Simple function to fetch data from a GraphQL endpoint and return it as a JSON string.

    Args:
        gqlclient: async function (query, variables) -> {"data": {...}, "errors": ...}
        query: GraphQL query string
        variables: dictionary of variables for the query

    Returns:
        JSON string containing the "data" part of the GraphQL response
    """
    try:
        if variables is None:
            variables = {}
        elif isinstance(variables, str):
            variables = json.loads(variables)
        elif not isinstance(variables, dict):
            raise TypeError(f"Unsupported type for variables: {type(variables)}")

        response = await gqlclient(query, variables)
        if "errors" in response and response["errors"]:
            raise Exception(f"GraphQL errors: {response['errors']}")

        data = response.get("data", {})
        return data

    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
