import asyncio

# Auth
import jwt

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
    openChat,
)

# Store per user chat instances
user_chats = {}


async def get_user_chat_hook(user_id: str):
    """Get or create a chat hook for a specific user"""
    if user_id not in user_chats:
        # Create a new chat hook for this user
        user_chats[user_id] = await openChat()
    return user_chats[user_id]


async def startup_gql_client():
    pass


from nicegui import core
import nicegui

app = FastAPI(on_startup=[startup_gql_client])

from nicegui import ui, app as nicegui_app, storage, core
from starlette.middleware.sessions import SessionMiddleware
import base64
import json

nicegui_app.add_middleware(storage.RequestTrackingMiddleware)
nicegui_app.add_middleware(SessionMiddleware, secret_key="SUPER-SECRET")


@ui.page("/")
async def index_page(request: Request):

    # Get or create a unique user ID for this session
    user_id = None
    authorization_cookie = request.cookies.get("authorization")
    print(authorization_cookie)

    # Get user Id for his context history
    if authorization_cookie:
        try:
            decoded_token = json.loads(
                base64.b64decode(authorization_cookie.split(".")[1]).decode("utf-8")
            )
            user_id = decoded_token["user_id"]
            print(user_id)
        except:
            print("Cannot decode token")

    if not user_id:
        import uuid

        user_id = request.session.get("user_id")

        if not user_id:
            user_id = str(uuid.uuid4())
            request.session["user_id"] = user_id

    # Get the chat hook for this specific user
    print("user id", user_id)
    chat_hook = await get_user_chat_hook(user_id)

    # 🔹 Historie otázek a odpovědí
    history = []  # list of tuples (q, a)
    feedback_row = None


    # 🔹 Přidáme CSS a JS pro light/dark mód
    # ui.add_head_html(
    #     """
    # <style>
    #     body.light-mode .nicegui-content { background-color: #e5e7eb !important; }
    #     body.light-mode .chat-message .name { color: white !important; }
    #     body.dark-mode .nicegui-content { background-color: #1f2937 !important; }
    #     body.dark-mode .chat-message .name { color: black !important; }
    # </style>
    # <script>
    #     const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    #     document.body.classList.add(isDark ? 'dark-mode' : 'light-mode');
    # </script>
    # """
    # )

    async def send() -> None:
        nonlocal feedback_row
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

            thinking_message = ui.chat_message(
                text="…",
                name="Assistant",
                sent=False,
                avatar="https://robohash.org/ui",
            ).props("bg-color=grey-2 text-color=dark")

        async def animate_thinking(msg):
            dots = [".", "..", "..."]
            i = 0
            while True:
                msg.clear()
                with msg:
                    ui.html(dots[i % len(dots)])
                await asyncio.sleep(0.5)
                i += 1

        animation_task = asyncio.create_task(animate_thinking(thinking_message))

        # AI stuff
        result = await chat_hook(question)

        animation_task.cancel()
        try:
            await animation_task
        except asyncio.CancelledError:
            pass

        response = [{"type": "md", "content": f"{result}"}]

        for part in response:
            await asyncio.sleep(1)
            thinking_message.clear()
            with thinking_message:
                if part["type"] == "text":
                    ui.html(part["content"])
                elif part["type"] == "md":
                    ui.markdown(part["content"])
        

        # 🔹 Uložení do historie
        history_list.append((question, result))

        # 🔹 Aktualizace log panelu
        history_container.clear()
        with history_container:
            for q, a in history_list:
                with ui.column().classes("mb-4 p-2 border-b border-gray-300"):
                    ui.markdown(f"**Q:** {q}")
                    ui.markdown(f"**A:** {a}")
        
        with message_container:  # NEW
            if feedback_row:
                feedback_row.delete()   
            with ui.row().classes("ml-12 gap-2") as feedback_row:  # NEW
                ui.button("Like",
                        on_click=lambda: ui.run_javascript("console.log('Like clicked')")) \
                .props("flat dense color=positive").classes("text-xs italic")
                ui.button("Dislike",
                        on_click=lambda: ui.run_javascript("console.log('Dislike clicked')")) \
                .props("flat dense color=negative").classes("text-xs italic")

        ui.run_javascript("window.scrollTo(0, document.body.scrollHeight)")

    ui.add_css(
        """
        a:link, a:visited { color: inherit !important; text-decoration: none; font-weight: 500; }
        ::-webkit-scrollbar { display: none; }
        * { scrollbar-width: none; }
    """
    )

    # the queries below are used to expand the content down to the footer (content can then use flex-grow to expand)
    ui.query(".q-page").classes("flex")
    ui.query(".nicegui-content").classes("w-full")

    with ui.tabs().classes("w-full") as tabs:
        chat_tab = ui.tab("Chat")
        logs_tab = ui.tab("Logs")
        history_tab = ui.tab("History")

    with ui.tab_panels(tabs, value=chat_tab).classes(
    "w-full max-w-3xl mx-auto flex-grow items-stretch rounded-2xl shadow-lg light:bg-white dark:bg-neutral-800"
):
        message_container = ui.tab_panel(chat_tab).classes("items-stretch")
        with message_container:
            ui.chat_message(
                text="Hi! How can I assist you today?",
                name="Assistant",
                sent=False,
                avatar="https://robohash.org/ui",
            ).props("bg-color=grey-2 text-color=dark")

        with ui.tab_panel(logs_tab) as logs_container:
            ui.label("Conversation Log").classes("font-bold mb-2")

        with ui.tab_panel(history_tab) as history_container:
            ui.label("Conversation history").classes("font-bold mb-2")

    with ui.footer().classes("bg-transparent p-4"):
        with ui.row().classes("w-full justify-center"):
            with ui.card().classes(
                "w-full max-w-2xl rounded-2xl shadow-2xl light:bg-white dark:bg-neutral-900"
            ):
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


ui.run_with(
    app,
    title="GQL Evolution",
    favicon="🚀",
    dark=None,
    tailwind=True,
    storage_secret="SUPER-SECRET",
)
