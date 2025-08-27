import asyncio
from fastapi import FastAPI, Request, Response


from nicegui import core
import nicegui


app = FastAPI()

from nicegui import ui, app as nicegui_app, storage, core
from starlette.middleware.sessions import SessionMiddleware

nicegui_app.add_middleware(storage.RequestTrackingMiddleware)
nicegui_app.add_middleware(SessionMiddleware, secret_key="SUPER-SECRET")


@ui.page("/")
async def index_page():
    # https://github.com/zauberzeug/nicegui/blob/main/examples/chat_with_ai/main.py

    # print("Index page", type(request), type(response), type(unknown))
    # ui.label("Hello, World!")
    # ui.button("Click me", on_click=lambda: ui.notify("Clicked!"))
    async def send() -> None:
        question = text.value.strip()
        if not question:
            return
        text.value = ""
        with message_container:
            ui.chat_message(
                text=question,
                name="You",
                sent=True,
            )
            response_message = ui.chat_message(
                name="Assistant", sent=False, avatar="https://robohash.org/ui"
            )

        if question.strip() == "sdl":
            response = [
                {"type": "text", "content": f"I have responded to {question}"},
                {
                    "type": "md",
                    "content": schema.as_str().replace("\\n", "\n").replace('\\"', '"'),
                },
            ]
        elif question.strip() == "explain":
            from src.Utils.explain_query import explain_graphql_query
            from src.Utils.gql_client import createGQLClient

            client = await createGQLClient(
                username="john.newbie@world.com", password="john.newbie@world.com"
            )
            sdl_query = """query __ApolloGetServiceDefinition__ { _service { sdl } }"""
            result = await client(sdl_query, variables={})
            sdl = result["data"]["_service"]["sdl"]
            # sdl = schema.as_str()
            query = """"""
            result = explain_graphql_query(sdl, query)
            response = [
                {"type": "text", "content": f"I have responded to {question}"},
                {"type": "md", "content": f"```gql\n{result}\n```"},
            ]
        else:
            response = [
                {"type": "text", "content": f"I have responded to {question}"},
                {
                    "type": "md",
                    "content": """
                            # My response
                            ```json
                            {
                                "question": "{question}"
                            }
                            ```
                            """,
                },
            ]
        for part in response:
            await asyncio.sleep(1)
            if part["type"] == "text":
                with response_message:
                    ui.html(part["content"])
            elif part["type"] == "md":
                with message_container:
                    ui.markdown(part["content"])
        ui.run_javascript("window.scrollTo(0, document.body.scrollHeight)")

        # text.value = ''

    ui.add_css(
        r"a:link, a:visited {color: inherit !important; text-decoration: none; font-weight: 500}"
    )

    # the queries below are used to expand the contend down to the footer (content can then use flex-grow to expand)
    ui.query(".q-page").classes("flex")
    ui.query(".nicegui-content").classes("w-full")

    with ui.tabs().classes("w-full") as tabs:
        chat_tab = ui.tab("Chat")
        logs_tab = ui.tab("Logs")
    with ui.tab_panels(tabs, value=chat_tab).classes(
        "w-full max-w-3xl mx-auto flex-grow items-stretch rounded-2xl shadow-md bg-neutral-800"
    ):
        message_container = ui.tab_panel(chat_tab).classes("items-stretch")
        with message_container:
            ui.chat_message(
                text="Hi! How can I assist you today?",
                name="Assistant",
                sent=False,
                avatar="https://robohash.org/ui",
            )
        with ui.tab_panel(logs_tab):
            log = ui.log().classes("w-full h-full")

    with ui.footer().classes("bg-transparent p-4"):
        with ui.row().classes("w-full justify-center"):
            with ui.card().classes("w-full max-w-2xl rounded-2xl shadow-md bg-silver"):
                with ui.row().classes("items-center w-full no-wrap"):
                    text = (
                        ui.input(placeholder="Type a message...")
                        .props("borderless dense input-class")
                        .classes("flex-grow px-3")
                        .on("keydown.enter", send)
                    )
                    ui.button(on_click=send).props(
                        "flat round dense color=primary icon=send"
                    ).classes("ml-auto")


# app.mount("/nicegui", nicegui_app)
nicegui.ui.run_with(
    app,
    title="GQL Evolution",
    favicon="🚀",
    dark=None,
    tailwind=True,
    storage_secret="SUPER-SECRET",
)
# endregion
