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


from src.Components.likeDislikeButton import add_feedback_row
from src.Components.footer import build_chat_footer

from src.Pages.LogView import build_logs_ui
from src.Pages.GraphQLView import build_graphql_ui
from src.Utils.graphQLdata import GraphQLData

import logging, uuid, contextvars
from starlette.middleware.base import BaseHTTPMiddleware
from pathlib import Path
import tempfile
import time
from Database.Embedding.find_simillar import find_similar_question

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
    import uuid

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
import nicegui


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
log_chat = logging.getLogger("chat")
log_gql = logging.getLogger("graphql")
log_auth = logging.getLogger("auth")

from nicegui import ui, app as nicegui_app, storage, core
from starlette.middleware.sessions import SessionMiddleware

from Database.ChatHistory.add_to_db import add_chat_history

nicegui_app.add_middleware(storage.RequestTrackingMiddleware)
nicegui_app.add_middleware(SessionMiddleware, secret_key="SUPER-SECRET")
nicegui_app.add_static_files("/assets", "./assets")


#######################################################
# * Main tab
######################################################


@ui.page("/")
async def index_page(request: Request):
    ui.add_css(
        """
            #chat-scroll .q-message-name--sent {
                text-align: left !important;   /* text vlevo */
                display: block;                /* aby se text-align chytlo */
                margin-left: 0 !important;
                margin-right: auto !important; /* odlepit od pravého okraje */
            }

            /* 1) Jednotná šířka zobáčku */
            :root { --chat-tail: 6px; } /* klidně doladíš 10–14px podle Quasaru/tematu */

            /* 2) Chat kontejner má rezervu na obou stranách,
                takže špička může „zajet“ do paddingu bez overflow */
            #chat-scroll {
            padding-left: var(--chat-tail);
            padding-right: var(--chat-tail);
            overflow-x: hidden;        /* jistota bez horizontálního scrollu */
            }

            /* Ať mohou bubliny využít celou šířku kontejneru */
            #chat-scroll .q-message-text {
            width: 100% !important;
            max-width: 100% !important;   /* přepíše quasar ~70% */
            min-width: 0 !important;
            }

            /* Text se láme normálně až na konci řádku, ne uprostřed slov */
            #chat-scroll .q-message-text .q-message-text-content,
            #chat-scroll .q-message-text .nicegui-markdown {
            white-space: normal !important;
            word-break: normal !important;
            overflow-wrap: anywhere; /* jen velmi dlouhá slova/URL se mohou zlomit */
            }

            /* Zarovnání bublin podle směru zprávy (pravá/levá) */
            #chat-scroll .q-message.q-message-sent     { justify-content: flex-end; }
            #chat-scroll .q-message.q-message-received { justify-content: flex-start; }

            /* „ocásek“ neřeže okraj a nepřidává horizontální scroll */
            :root { --chat-tail: 6px; }
            #chat-scroll { padding-left: var(--chat-tail); padding-right: var(--chat-tail); overflow-x: hidden; }
            #chat-scroll .q-message-text--received::before,
            #chat-scroll .q-message-text--received::after { left: calc(-1 * var(--chat-tail)) !important; right: auto !important; }
            #chat-scroll .q-message-text--sent::before,
            #chat-scroll .q-message-text--sent::after { right: calc(-1 * var(--chat-tail)) !important; left: auto !important; }

            #chat-scroll .q-message-text--sent::before,
            #chat-scroll .q-message-text--sent::after {
            right: calc(-1 * var(--chat-tail)) !important;   /* „do paddingu“ vpravo */
            left: auto !important;
            transform: none !important;
            }

            /* 6) Pro jistotu: dlouhé řádky nerozbíjej scroll */
            #chat-scroll .nicegui-markdown pre,
            #chat-scroll .nicegui-markdown code {
            white-space: pre-wrap;
            word-break: break-word;
            }

            /* 7) Ať flex položky bublin nediktují min-width */
            #chat-scroll .q-message { min-width: 0; }

            /* 8) */
            html, body {
                overflow: hidden !important;  /* scroll zakázán */
                height: 100% !important;
            }

            /* 9) Skrytí scroll baru v tabulce produktů (funkční scroll) */
            #product-scroll {
                scrollbar-width: none;  /* Firefox */
                -ms-overflow-style: none;  /* IE 10+ */
            }

            #product-scroll::-webkit-scrollbar {
                width: 0px;  /* Chrome, Safari, Edge */
                background: transparent;
            }
            
        """
    )

    user_id = authorize_user(request)
    _ = current_user.set(user_id)
    log_auth.info("User authorized", extra={"user_id": user_id})

    chat_hook = await get_user_chat_hook(user_id)
    history = get_user_history(user_id)
    feedback_row = None
    history_container = None

    async def send() -> None:
        nonlocal feedback_row
        question = text.value.strip()
        current_req.set(uuid.uuid4().hex[:8])

        if not question:
            return

        log_chat.info("User question received", extra={"len": len(question)})

        ui.run_javascript(
            "document.getElementById('chat-scroll')?.scrollTo({top: 1e9, behavior: 'smooth'});"
        )

        text.value = ""
        with chat_stream:  # <<< sem
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

        #######################################################
        # * AI stuff
        #######################################################
        try:
            result = await chat_hook(question)
            log_chat.info("Chat hook answered", extra={"answer_len": len(str(result))})
        except Exception:
            log_chat.exception("Chat hook failed")
            raise

        query = None
        variables = None

        try:
            data = json.loads(result.content)

            query = data["Query"]
            variables = data["Variables"]
            response = data["Response"]
            response = [{"type": "md", "content": f'{data["Response"]}'}]

        except json.JSONDecodeError as e:
            print(f"Chyba při parsování JSONu: {e}")
            data = result.content
            response = [{"type": "md", "content": f"{data}"}]

        #######################################################
        # * Datová pumpa do embeddingu
        #######################################################
        # from Database.Embedding.data_pump import ask_questions
        # await ask_questions(chat_hook)

        animation_task.cancel()
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
            feedback_row = add_feedback_row(chat_stream, query, question)

        if query:
            with chat_stream:
                GraphQLData(
                    gqlclient=gql_client,
                    query=query,
                    variables=variables,
                )

        # 🔹 Uložení do historie
        # zkus získat čistý text z JSONu
        try:
            answer_text = json.loads(result.content)["Response"]
        except Exception:
            answer_text = str(result)

        # ulož do historie v paměti
        history.add_entry(question=question, answer=answer_text)

        # ulož do DB jen čistý text
        add_chat_history(
            message=question,
            answer=data,
            user_id=user_id,
            session_id=history.get_history_id(),
        )

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

    chat_stream = ui.column().classes("w-full gap-2")

    @ui.refreshable
    def sessions_panel():
        # clear container a vykresli všechny sessions
        render_sessions_list(user_id, chat_stream, gql_client)

    # tlačítko New chat
    def on_new_chat():
        # vytvoří novou session a hned aktualizuje chat_stream i seznam vlevo
        create_new_session(
            user_id,
            gql_client,
            chat_stream,
            sessions_container,
        )

        # vymaž chat_stream a vlož uvítací zprávu
        chat_stream.clear()
        with chat_stream:
            ui.chat_message(
                text="Noo, co potřebuješ?",
                name="Tadeáš",
                sent=False,
                avatar="/assets/img/Tadeas.png",
            ).props("bg-color=grey-2 text-color=dark")

        # aktualizuj seznam sessions vlevo
        render_sessions_list(user_id, chat_stream, gql_client)

    with ui.header().classes("light:bg-white dark:bg-neutral-950 shadow-md"):
        with ui.row().classes("items-center w-full justify-between"):
            ui.label("TedGPT").classes("text-lg font-bold ml-4")
            with ui.tabs().classes("shrink-0") as tabs:
                chat_tab = ui.tab("Chat")
                logs_tab = ui.tab("Logs")
                graphql_tab = ui.tab("GraphQL")

    with ui.drawer(side="left", value=True).classes(
        "h-screen p-4 rounded-r-2xl shadow-lg"
    ) as drawer:
        ui.label("Chat history").classes("text-md font-bold mb-2")

        # tlačítko New chat
        ui.button("New chat", on_click=on_new_chat).classes("w-full mb-2")
        # vytvoříme kontejner pro sessions
        sessions_container = ui.column().classes("w-full")

        render_sessions_list(user_id, chat_stream, gql_client, sessions_container)

    with ui.tab_panels(tabs, value=chat_tab).classes(
        "fullscreen-tabs w-full h-screen max-w-none mx-0 p-0 items-stretch light:bg-white dark:bg-neutral-900"
    ):
        message_container = ui.tab_panel(chat_tab).classes("items-stretch")
        with message_container:
            with ui.card().classes(
                "w-full max-w-3xl mx-auto flex-grow items-stretch rounded-2xl shadow-lg"
            ):
                with ui.column().classes("w-full min-w-0"):
                    chat_scroll = (
                        ui.element("div")
                        .props("id=chat-scroll")
                        .classes("w-full")
                        .style("max-height: 70vh; overflow-y: auto;")
                    )
                    ui.add_css(
                        """
                                #chat-scroll {
                                    scrollbar-width: none;
                                    -ms-overflow-style: none;
                                }
                                #chat-scroll::-webkit-scrollbar {
                                    width: 0px;
                                    background: transparent;
                                }
                                """
                    )

                    with chat_scroll:
                        with chat_stream:
                            # uvítací zpráva při startu
                            ui.chat_message(
                                text="Něco, možná trošku, lepšího?",
                                name="Tadeáš",
                                sent=False,
                                avatar="/assets/img/Tadeas.png",
                            ).props("bg-color=grey-2 text-color=dark")

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

    #######################################################
    # * Footer
    #######################################################
    text = build_chat_footer(on_send=send, placeholder="Type a message...")


ui.run_with(
    app,
    title="TedGPT",
    favicon="./assets/img/tedGPT.png",
    dark=None,
    tailwind=True,
    storage_secret="SUPER-SECRET",
)
