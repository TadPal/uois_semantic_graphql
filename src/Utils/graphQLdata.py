import typing
from nicegui import ui
import json


def GraphQLData(
    *,
    gqlclient: typing.Callable[
        [str, typing.Dict[str, typing.Any]], typing.Awaitable[dict]
    ],
    query: str,
    variables: typing.Optional[typing.Dict[str, typing.Any]] = None,
    result: typing.Optional[typing.List[typing.Dict[str, typing.Any]]] = None,
    metadata: typing.Optional[typing.List[typing.Dict[str, typing.Any]]] = None,
    # extract_rows: typing.Optional[typing.Callable[[typing.Dict[str, typing.Any]], typing.List[typing.Dict[str, typing.Any]]]] = None,
    autoload: bool = True,
):
    """Composite NiceGUI widget to page GraphQL list results and show them in a table.

    Args:
        gqlclient: async function (query, variables) -> {"data": {...}, "errors": ...}
        query: GraphQL query string
        variables: initial variables; uses 'skip' and 'limit' for paging
        result: initial rows (optional)
        autoload: if True and no initial result, automatically loads first page
    """
    try:
        if variables:
            if isinstance(variables, str):
                variables = json.loads(variables)
            elif isinstance(variables, dict):
                # already a dict, do nothing
                pass
            else:
                raise TypeError(f"Unsupported type for variables: {type(variables)}")
        else:
            variables = {}

        if result is None:
            result = []
        if isinstance(result, dict):
            result = next(iter(result.values()), None)
        if metadata is None:
            metadata = {}

        state = {
            "variables": {
                "where": variables.get("where", None),
                "orderby": variables.get("orderby", None),
                "desc": variables.get("desc", None),
                "skip": variables.get("skip", 0),
                "limit": variables.get("limit", 10),
            },
            "errors": [],
            "result": list(result),
            "ids": {
                r.get("id")
                for r in result
                if isinstance(r, dict) and "id" in r and r["id"] is not None
            },
            "loading": False,
            "done": False,
        }
    except Exception as e:
        print(f"Error occured: {e}")
    # def default_extract_rows(data: typing.Dict[str, typing.Any]) -> typing.List[typing.Dict[str, typing.Any]]:
    #     if not data:
    #         return []

    #     for v in data.values():
    #         if isinstance(v, list):
    #             return [x for x in v if isinstance(x, dict)]
    #     return []

    # extractor = extract_rows or default_extract_rows

    def compute_done(new_count: int) -> None:
        # If server returned fewer rows than limit → jsme na konci.
        limit = state["variables"].get("limit", 10)
        state["done"] = (limit == 0) or (new_count < limit)

    compute_done(new_count=len(result))

    async def reload_all():
        state["result"].clear()
        state["ids"].clear()
        state["variables"]["skip"] = 0
        state["done"] = False
        await load_page(skip=0)

    async def load_page(skip: typing.Optional[int] = None):
        if state["loading"]:
            return
        state["loading"] = True
        view.refresh()
        try:
            vars_now = dict(state["variables"])
            if skip is not None:
                vars_now["skip"] = skip
            else:
                vars_now["skip"] = vars_now.get("skip", 0) + vars_now.get("limit", 10)
            print(f"load_page.variables={vars_now}")
            response = await gqlclient(query, vars_now)
            errors = response.get("errors")
            if errors:
                state["errors"] = errors if isinstance(errors, list) else [errors]
                return
            data = response.get("data") or {}
            # rows = extractor(data)
            rows = next((value for value in data.values()), [])
            if not isinstance(rows, list):
                state["errors"] = ["response has nonlist key, this is not expected"]
                rows = []
            # append unique
            # new_added = 0
            for row in rows:
                rid = row.get("id")
                if rid is not None and rid not in state["ids"]:
                    state["result"].append(row)
                    if rid is not None:
                        state["ids"].add(rid)
                    # new_added += 1

            state["variables"] = {**vars_now}
            compute_done(len(rows))
        except Exception as e:
            state["errors"] = [f"{type(e).__name__}: {e}"]
        finally:
            state["loading"] = False
            view.refresh()

    async def load_more():
        print(f"load_more")
        await load_page()

    def getcolumns():
        rows = state["result"]
        if len(rows) == 0:
            return []
        return [
            {
                "name": key,
                "label": key,
                "field": key,
                "sortable": True,
                "style": "white-space: nowrap; min-width: 160px;",  # ⬅️ důležité
            }
            for key, value in rows[0].items()
            if not isinstance(value, (dict, list))
        ]

    @ui.refreshable
    def view():
        # fullscreen = ui.fullscreen()
        # ui.button('Toggle Fullscreen', on_click=fullscreen.toggle)
        with ui.tabs() as tabs:
            queryTab = ui.tab("query")
            varTab = ui.tab("variables")
            rawresultTab = ui.tab("rawresult")
            resultTab = ui.tab("result")
        with ui.tab_panels(tabs, value=resultTab).classes("w-full"):
            with ui.tab_panel(queryTab):
                # ui.label('queryTab tab')
                ui.markdown(("```graphql\n" f"{query}" "\n```"))
            with ui.tab_panel(varTab):
                # ui.label('varTab tab')
                ui.markdown(
                    ("```json\n" f'{json.dumps(state["variables"], indent=2)}' "\n```")
                )
            with ui.tab_panel(rawresultTab):
                ui.markdown(
                    (
                        "## Raw Result\n\n"
                        "```json\n"
                        f"{json.dumps(state['result'], indent=2)}"
                        "\n```\n"
                        "## Metadata\n\n"
                        "```json\n"
                        f"{json.dumps(metadata, indent=2)}"
                        "\n```"
                    )
                )
            with ui.tab_panel(resultTab).classes("w-full"):
                # ui.markdown((
                #     "```json\n"
                #     f"{json.dumps(state['result'], indent=2)}"
                #     "\n```"
                # ))
                # ui.table(
                #     columns=getcolumns(),
                #     rows=state["result"],
                #     row_key="id"
                # )
                cols = getcolumns()
                with ui.element("div").classes("w-full overflow-x-auto").style(
                    "max-width: 100%;"
                ):
                    # spočítáme celkovou minimální šířku tabulky
                    per_col = 180  # px na sloupec
                    min_width_px = max(640, per_col * len(cols))

                    t = ui.table(
                        columns=cols,
                        rows=state["result"],
                        row_key="id",
                    )

                    t.props(f'table-style="min-width: {min_width_px}px"')

        if state["errors"]:
            ui.markdown("```text\n" + "\n".join(map(str, state["errors"])) + "\n```")

        with ui.row().classes("gap-2 mt-2"):

            ui.button(
                "Reload",
                on_click=reload_all,
                # ena=state["loading"],
            )
            ui.button(
                "Load more",
                on_click=load_more,
                # disable=state["loading"] or state["done"],
            )
            if state["loading"]:
                ui.spinner(size="md")

            if state["done"]:
                ui.label("No more data").classes("text-xs text-gray-500")

        pass

    view()
    # optional first fetch
    if autoload and not state["result"]:
        ui.timer(0, load_more, once=True)

    return view
