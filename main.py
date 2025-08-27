import asyncio

# FastAPI part

import asyncio
from fastapi import FastAPI, Request, Response

from SemanticKernel import (
    kernel,
    azure_chat,
    KernelArguments,
    createGQLClient,
    ChatHistory,
    AzureChatPromptExecutionSettings,
    FunctionChoiceBehavior,
    AutoFunctionInvocationContext,
    FilterTypes,
)

gqlClient = None


async def startup_gql_client():
    global gqlClient
    gqlClient = await createGQLClient(
        username="john.newbie@world.com", password="john.newbie@world.com"
    )


skills = []
for plugin in kernel.plugins.values():
    skills.extend(plugin.functions.keys())
    print(skills)

# for pname, plugin in kernel.plugins.items():
#     print(f"Plugin: {pname}")
#     print("  Functions:", list(plugin.functions))

history = ChatHistory()
execution_settings = AzureChatPromptExecutionSettings()
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()


async def inject_gql_client(context: AutoFunctionInvocationContext, next):
    context.arguments["gqlclient"] = gqlClient
    await next(context)


kernel.add_filter(FilterTypes.AUTO_FUNCTION_INVOCATION, inject_gql_client)

from nicegui import core
import nicegui

app = FastAPI(on_startup=[startup_gql_client])

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
            ).props("bg-color=primary text-color=white")
            response_message = ui.chat_message(
                name="Assistant", sent=False, avatar="https://robohash.org/ui"
            ).props("bg-color=grey-2 text-color=dark")

        # AI stuff
        history.add_user_message(question)
        # print(f"history: {history.serialize()}")
        # https://learn.microsoft.com/en-us/semantic-kernel/concepts/ai-services/chat-completion/function-calling/?pivots=programming-language-python
        result = await azure_chat.get_chat_message_content(
            chat_history=history,
            settings=execution_settings,
            kernel=kernel,
            # context_variables={"extraContext": extra_context}
            arguments=KernelArguments(),
        )

        response = [{"type": "md", "content": f"{result}"}]

        # for part in response:
        #     await asyncio.sleep(1)
        #     if part["type"] == "text":
        #         with response_message:
        #             ui.html(part["content"])
        #     elif part["type"] == "md":
        #         with message_container:
        #             ui.markdown(part["content"])
        # ui.run_javascript("window.scrollTo(0, document.body.scrollHeight)")

        # Make the UI better
        for part in response:
            await asyncio.sleep(1)
            if part["type"] == "text":
                with response_message:
                    ui.html(part["content"])
            elif part["type"] == "md":
                with response_message:
                    ui.markdown(part["content"])
        ui.run_javascript("window.scrollTo(0, document.body.scrollHeight)")

    ui.add_css(
        """
        a:link
        a:visited {color: inherit !important; text-decoration: none; font-weight: 500},
        /* Hide scrollbar for Chrome, Safari and Edge */
        ::-webkit-scrollbar {
            display: none;
        }
        /* Hide scrollbar for Firefox */
        *{
            scrollbar-width: none;
        }"""
    )

    # the queries below are used to expand the contend down to the footer (content can then use flex-grow to expand)
    ui.query(".q-page").classes("flex")
    ui.query(".nicegui-content").classes("w-full")

    with ui.tabs().classes("w-full") as tabs:
        chat_tab = ui.tab("Chat")
        # Use log tab
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
            ).props("bg-color=grey-2 text-color=dark")

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
