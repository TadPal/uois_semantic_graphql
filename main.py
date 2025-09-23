import asyncio
import json

# Auth
from Auth.auth import authorize_user

# FastAPI part
import asyncio
from fastapi import FastAPI, Request, Response
from SemanticKernel import (
    createGQLClient,
    openChat,
)
from History.chatHistory import UserChatHistory

from src.Utils.tab_history import (
    create_new_session,
    render_sessions_list,
)

from src.Utils.log_bus import setup_logging

from src.Components.input import build_chat_input

from src.Pages.LogView import build_logs_ui
from src.Pages.GraphQLView import build_graphql_ui
from src.Utils.graphQLdata import GraphQLData

import logging, uuid, contextvars
from starlette.middleware.base import BaseHTTPMiddleware
from pathlib import Path
import tempfile
import time
from Database.Embedding.find_simillar import find_similar_question
from src.Utils.fetch_graphQLdata import fetch_graphql_data
from src.Utils.graphQLdata import GraphQLData
from src.Components.likeDislikeButton import add_feedback_row
from Database.ChatHistory.add_to_db import add_chat_history

from src.Utils.chat_hook import run_chat_hook_flow

# Store per user chat instances
user_chats = {}
history = {}
gql_client = None


# --- log kontext ---
current_user: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "user", default=None
)
current_req: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "req", default=None
)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.user_id = current_user.get()
        record.req_id = current_req.get()
        return True


def get_user_history(user_id: str):
    if user_id not in history:
        history[user_id] = UserChatHistory()
    return history[user_id]


async def get_user_chat_hook(user_id: str):
    """Get or create a chat hook for a specific user"""
    if user_id not in user_chats:
        # Create a new chat hook for this user
        user_chats[user_id] = await openChat()
    return user_chats[user_id]


async def startup_gql_client():
    global gql_client
    # 1) inicializace loggingu a filtru
    setup_logging(level=logging.DEBUG, use_queue=False)
    logging.getLogger().addFilter(ContextFilter())

    # (volitelné) posílej uvicorn/fastapi logy do našeho root loggeru -> LogBus
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lg = logging.getLogger(name)
        lg.setLevel(logging.INFO)
        lg.propagate = True

    # 2) self-test záznam, ať vidíš v Logs tabu, že LogBus běží
    logging.getLogger("selftest").info("LogBus OK - startup reached")

    # 3) inicializace GQL klienta
    gql_client = await createGQLClient(
        username="john.newbie@world.com", password="john.newbie@world.com"
    )
    logging.getLogger("app.startup").info("GraphQL client ready")


from nicegui import core
from dotenv import load_dotenv

load_dotenv()

import os


class LogContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid_token = current_req.set(uuid.uuid4().hex[:8])
        try:
            response = await call_next(request)
            return response
        finally:
            current_req.reset(rid_token)


app = FastAPI(on_startup=[startup_gql_client])
app.add_middleware(LogContextMiddleware)

from Auth.easyauth import (
    EntraEasyAuthMiddleware,
    EntraIDClient,
    require,
    create_entra_router,
)

AZURE_TENANT_ID = os.getenv("AZURE_ENTRA_TENANT_ID")
AZURE_CLIENT_ID = os.getenv("AZURE_ENTRA_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_ENTRA_CLIENT_SECRET")

entra_router = create_entra_router(
    tenant_id=AZURE_TENANT_ID,
    client_id=AZURE_CLIENT_ID,
    client_secret=AZURE_CLIENT_SECRET,
    login_path="/login",
    callback_path="/auth",
)

entra_client = EntraIDClient(tenant_id=AZURE_TENANT_ID, audience=None)

app.add_middleware(
    EntraEasyAuthMiddleware,
    entra_client=entra_client,
    pass_through=("/public", "/health", "/login", "/auth", "/login/", "/auth/"),
    login_path="/login",  # nebo jméno route, pokud používáš url_for("entra_login")
    # external_base_url="https://app.example.com",  # za reverse proxy
    redirect_on_unauth=True,
)

app.include_router(entra_router)

log_chat = logging.getLogger("chat")
log_gql = logging.getLogger("graphql")
log_auth = logging.getLogger("auth")

from nicegui import ui, app as nicegui_app, storage, core
from starlette.middleware.sessions import SessionMiddleware

nicegui_app.add_middleware(storage.RequestTrackingMiddleware)
nicegui_app.add_middleware(SessionMiddleware, secret_key="SUPER-SECRET")
nicegui_app.add_static_files("/assets", "./assets")


#######################################################
# * Main tab
######################################################


@ui.page("/")
async def index_page(request: Request):
    ui.add_css("src/app.css")

    user_id = authorize_user(request)
    _ = current_user.set(user_id)
    log_auth.info("User authorized", extra={"user_id": user_id})

    chat_hook = await get_user_chat_hook(user_id)
    history = get_user_history(user_id)

    feedback_row = None
    chat_stream = None

    async def send() -> None:
        nonlocal feedback_row, chat_stream
        question = text.value.strip()
        current_req.set(uuid.uuid4().hex[:8])

        if not question:
            return

        log_chat.info("User question received", extra={"len": len(question)})

        ui.run_javascript(
            "document.getElementById('chat-scroll')?.scrollTo({top: 1e9, behavior: 'smooth'});"
        )

        text.value = ""
        with chat_stream:
            ui.chat_message(
                text=question,
                name="You",
                sent=True,
            ).props(
                "bg-color=primary text-color=white"
            ).classes("ml-auto justify-end")

            thinking_message = ui.chat_message(
                text="…",
                name="Tadeáš",
                sent=False,
                avatar="/assets/img/Tadeas.png",
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

        #######################################################
        # * Compare promt embedding
        #######################################################

        found_answer = find_similar_question(user_prompt=question, threshold=0.25)

        query = None
        variables = None

        if found_answer:
            try:
                with ui.column().classes("p-2 bg-gray-100 rounded") as answer_block:

                    data = json.loads(found_answer)
                    from src.Utils.fetch_graphQLdata import fetch_graphql_data

                    query = data["Query"]
                    variables = data["Variables"]

                    data["Response"] = await fetch_graphql_data(
                        gqlclient=gql_client, query=query, variables=variables
                    )

                    try:
                        responsePreview = str(data["Response"])[:50]

                    except:
                        responsePreview = "Já sám nevím co vím"

                    # reference to msg
                    suggestion_msg = ui.chat_message(
                        text=f" I know this answer: '{responsePreview}' is it similar enough?",
                        name="Tadeáš",
                        sent=False,
                        avatar="/assets/img/Tadeas.png",
                    ).props("bg-color=grey-2 text-color=dark")

            except:
                data["Response"] = found_answer

            with ui.row().classes("gap-2 mt-2") as button_row:
                like_button = ui.button("👍 Like")
                dislike_button = ui.button("👎 Dislike")

                async def clear_suggestion():
                    """helper to delete ui element"""
                    for elem in (answer_block, suggestion_msg, button_row):
                        try:
                            elem.delete()
                        except Exception:
                            pass

                async def on_like():
                    nonlocal feedback_row
                    await clear_suggestion()
                    response = [
                        {"type": "md", "content": "Zde máš obdobně pokládáný dotaz"}
                    ]

                    animation_task.cancel()
                    print("\n Response from database", response)

                    try:
                        await animation_task
                    except asyncio.CancelledError:
                        pass

                    for part in response:
                        await asyncio.sleep(1)
                        thinking_message.clear()
                        with thinking_message:
                            if part["type"] == "text":
                                ui.html(part["content"])
                            elif part["type"] == "md":
                                ui.markdown(part["content"])

                    if feedback_row:
                        try:
                            feedback_row.delete()
                        except Exception:
                            pass
                    with chat_stream:
                        feedback_row = add_feedback_row(
                            chat_stream,
                            query=query,
                            question=question,
                            variables=variables,
                        )

                    if query:
                        with chat_stream:
                            GraphQLData(
                                gqlclient=gql_client,
                                query=query,
                                variables=variables,
                            )

                    try:
                        answer_text = data["Response"]
                    except Exception:
                        answer_text = data

                    # ulož do historie v paměti
                    history.add_entry(question=question, answer=answer_text)

                    # ulož do DB jen čistý text
                    add_chat_history(
                        message=question,
                        answer=data,
                        user_id=user_id,
                        session_id=history.get_history_id(),
                    )

                # DISLIKE klik
                async def on_dislike():
                    nonlocal feedback_row
                    await clear_suggestion()

                    await run_chat_hook_flow(
                        question=question,
                        chat_hook=chat_hook,
                        log_chat=log_chat,
                        thinking_message=thinking_message,
                        animation_task=animation_task,
                        feedback_row=feedback_row,
                        chat_stream=chat_stream,
                        gql_client=gql_client,
                        history=history,
                        user_id=user_id,
                    )

                like_button.on_click(on_like)
                dislike_button.on_click(on_dislike)
        else:
            response = await run_chat_hook_flow(
                question=question,
                chat_hook=chat_hook,
                log_chat=log_chat,
                thinking_message=thinking_message,
                animation_task=animation_task,
                feedback_row=feedback_row,
                chat_stream=chat_stream,
                gql_client=gql_client,
                history=history,
                user_id=user_id,
            )

        #######################################################
        # * AI stuff
        #######################################################

        #######################################################
        # * Datová pumpa do embeddingu
        #######################################################
        # from Database.Embedding.data_pump import ask_questions
        # await ask_questions(chat_hook)

        try:
            render_sessions_list(user_id, chat_stream, gql_client, sessions_container)
        except Exception:
            # nechceme, aby případná chyba refreshu rozbila chat flow
            log_chat.exception("Failed to refresh sessions list after message")

        # 🔹 Aktualizace log panelu
        ui.run_javascript(
            "document.getElementById('chat-scroll')?.scrollTo({top: 1e9, behavior: 'smooth'});"
        )

    # the queries below are used to expand the content down to the footer (content can then use flex-grow to expand)
    ui.query(".q-page").classes("flex")
    ui.query(".nicegui-content").classes("w-full px-4 py-4")

    # tlačítko New chat
    def on_new_chat():
        nonlocal chat_stream
        create_new_session(
            user_id,
            gql_client,
            chat_stream,
            sessions_container,
        )

        chat_stream.clear()
        with chat_stream:
            ui.chat_message(
                text="Noo, co potřebuješ?",
                name="Tadeáš",
                sent=False,
                avatar="/assets/img/Tadeas.png",
            ).props("bg-color=grey-2 text-color=dark")

        # aktualizuj seznam sessions vlevo
        render_sessions_list(user_id, chat_stream, gql_client, sessions_container)

    with ui.header().classes("light:bg-white dark:bg-neutral-950 shadow-md"):
        with ui.row().classes("items-center w-full justify-between"):
            with ui.row().classes("items-center"):
                toggle_button = ui.button(icon="menu").classes("ml-2")
                ui.label("TedGPT").classes("text-lg font-bold ml-4")
            with ui.tabs().classes("shrink-0") as tabs:
                chat_tab = ui.tab("Chat")
                logs_tab = ui.tab("Logs")
                graphql_tab = ui.tab("GraphQL")

    with ui.drawer(side="left", value=False).style(
        "overflow-y: auto; scrollbar-width: none; -ms-overflow-style: none; background: transparent; box-shadow: none"
    ) as drawer:
        ui.label("Chat history").classes("text-md font-bold mb-2")

        # tlačítko New chat
        ui.button("New chat", on_click=on_new_chat).classes("w-full mb-2")
        # vytvoříme kontejner pro sessions
        sessions_container = ui.column().classes(
            "w-full max-h-80 mt-10 p-2 rounded-2xl shadow-lg dark:bg-neutral-800 light:bg-white"
        )
    toggle_button.on("click", lambda: drawer.toggle())

    with ui.tab_panels(tabs, value=chat_tab).classes(
        "fullscreen-tabs w-full h-screen max-w-none mx-0 p-0 items-stretch light:bg-transparent dark:bg-transparent"
    ):
        with ui.tab_panel(chat_tab).classes("flex flex-col h-full"):
            message_container = (
                ui.column()
                .props("id=message-container")
                .classes("flex-grow overflow-y-auto w-full max-w-3xl mx-auto p-2")
                .style("max-height: 70vh;")
            )
            with message_container:
                with ui.card().classes(
                    "w-full max-w-3xl mx-auto flex flex-col flex-grow rounded-2xl shadow-lg"
                ):
                    chat_scroll = (
                        ui.element("div")
                        .props("id=chat-scroll")
                        .classes("w-full flex-grow overflow-y-auto")
                    )
                    ui.add_css(
                        """
                        #message-container,
                        #chat-scroll {
                            overflow-y: scroll;        /* keep scrolling enabled */
                            scrollbar-width: none;      /* Firefox */
                            -ms-overflow-style: none;   /* IE 10+ */
                        }

                        #message-container::-webkit-scrollbar,
                        #chat-scroll::-webkit-scrollbar {
                            display: none;              /* Chrome, Safari, Edge */
                        }
                        """
                    )

                    with chat_scroll:
                        chat_stream = ui.column().classes("w-full gap-2 items-start")

                        with chat_stream:
                            # uvítací zpráva při startu
                            ui.chat_message(
                                text="Ahoj, s čím Vám mohu pomoci?",
                                name="Tadeáš",
                                sent=False,
                                avatar="/assets/img/Tadeas.png",
                            ).props("bg-color=grey-2 text-color=dark")
                    render_sessions_list(
                        user_id, chat_stream, gql_client, sessions_container
                    )

            with ui.row().classes("w-full max-w-3xl mx-auto p-2 shrink-0").style(
                "position:fixed; bottom:16px; left:50%; transform:translateX(-50%); z-index:9999; background:var(--base-100); width:calc(100% - 32px); max-width:900px; border-radius:12px;"
            ):
                text = build_chat_input(on_send=send, placeholder="Type a message...")

        #######################################################
        # * Logs tab
        #######################################################

        with ui.tab_panel(logs_tab) as logs_container:
            ui.label("Conversation Log").classes("font-bold mb-2")
            build_logs_ui(logs_container)

        #######################################################
        # * GraphQL tab
        #######################################################

        with ui.tab_panel(graphql_tab).classes("items-stretch"):
            build_graphql_ui(
                parent=ui.column().classes("w-full"), gql_client=gql_client
            )


ui.run_with(
    app,
    title="TedGPT",
    favicon="./assets/img/tedGPT.png",
    dark=None,
    tailwind=True,
    storage_secret="SUPER-SECRET",
)
