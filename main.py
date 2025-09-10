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
from Database.Embedding.add_to_db import add_embedding_row
from src.Utils.tab_history import (
    get_user_sorted_sessions,
    get_unique_sessions_by_user_id,
    load_and_display_session,
)

from src.Utils.on_button_press import (
    FeedbackState,
    render_buttons,
    on_like_click,
    on_dislike_click,
)
from src.Utils.graphQLdata import GraphQLData

import logging, uuid, contextvars
from src.Utils.log_bus import LOG_BUS, LEVEL_COLORS, setup_logging
from starlette.middleware.base import BaseHTTPMiddleware
from pathlib import Path
import tempfile
import time

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


def add_feedback_row(parent, query, question):
    # --- tvoje SVGčka ---
    like_default = """<svg class="w-6 h-6 text-blue-700 dark:text-gray-200" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M7 11c.889-.086 1.416-.543 2.156-1.057a22.323 22.323 0 0 0 3.958-5.084 1.6 1.6 0 0 1 .582-.628 1.549 1.549 0 0 1 1.466-.087c.205.095.388.233.537.406a1.64 1.64 0 0 1 .384 1.279l-1.388 4.114M7 11H4v6.5A1.5 1.5 0 0 0 5.5 19v0A1.5 1.5 0 0 0 7 17.5V11Zm6.5-1h4.915c.286 0 .372.014.626.15.254.135.472.332.637.572a1.874 1.874 0 0 1 .215 1.673l-2.098 6.4C17.538 19.52 17.368 20 16.12 20c-2.303 0-4.79-.943-6.67-1.475"/></svg>"""
    like_selected = """<svg class="w-6 h-6 text-blue-700 dark:text-gray-200" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path fill-rule="evenodd" d="M15.03 9.684h3.965c.322 0 .64.08.925.232.286.153.532.374.717.645a2.109 2.109 0 0 1 .242 1.883l-2.36 7.201c-.288.814-.48 1.355-1.884 1.355-2.072 0-4.276-.677-6.157-1.256-.472-.145-.924-.284-1.348-.404h-.115V9.478a25.485 25.485 0 0 0 4.238-5.514 1.8 1.8 0 0 1 .901-.83 1.74 1.74 0 0 1 1.21-.048c.396.13.736.397.96.757.225.36.32.788.269 1.211l-1.562 4.63ZM4.177 10H7v8a2 2 0 1 1-4 0v-6.823C3 10.527 3.527 10 4.176 10Z" clip-rule="evenodd"/></svg>"""
    dislike_default = """<svg class="w-6 h-6 text-blue-500 dark:text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M17 13c-.889.086-1.416.543-2.156 1.057a22.322 22.322 0 0 0-3.958 5.084 1.6 1.6 0 0 1-.582.628 1.549 1.549 0 0 1-1.466.087 1.587 1.587 0 0 1-.537-.406 1.666 1.666 0 0 1-.384-1.279l1.389-4.114M17 13h3V6.5A1.5 1.5 0 0 0 18.5 5v0A1.5 1.5 0 0 0 17 6.5V13Zm-6.5 1H5.585c-.286 0-.372-.014-.626-.15a1.797 1.797 0 0 1-.637-.572 1.873 1.873 0 0 1-.215-1.673l2.098-6.4C6.462 4.48 6.632 4 7.88 4c2.302 0 4.79.943 6.67 1.475"/></svg>"""
    dislike_selected = """<svg class="w-6 h-6 text-blue-500 dark:text-gray-400" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path fill-rule="evenodd" d="M8.97 14.316H5.004c-.322 0-.64-.08-.925-.232a2.022 2.022 0 0 1-.717-.645 2.108 2.108 0 0 1-.242-1.883l2.36-7.201C5.769 3.54 5.96 3 7.365 3c2.072 0 4.276.678 6.156 1.256.473.145.925.284 1.35.404h.114v9.862a25.485 25.485 0 0 0-4.238 5.514c-.197.376-.516.67-.901.83a1.74 1.74 0 0 1-1.21.048 1.79 1.79 0 0 1-.96-.757 1.867 1.867 0 0 1-.269-1.211l1.562-4.63ZM19.822 14H17V6a2 2 0 1 1 4 0v6.823c0 .65-.527 1.177-1.177 1.177Z" clip-rule="evenodd"/></svg>"""

    SVGS = {
        "like_default": like_default,
        "like_selected": like_selected,
        "dislike_default": dislike_default,
        "dislike_selected": dislike_selected,
    }

    state = FeedbackState()
    # samotný řádek – je to sourozenec chatových zpráv uvnitř chat_stream
    with parent:
        row = ui.row().classes("feedback-row ml-12 gap-1 -mt-2 mb-2")
        with row:
            like_html, dislike_html = render_buttons(state, SVGS)
            like_btn = ui.html(like_html)
            dislike_btn = ui.html(dislike_html)

            like_btn.on(
                "click",
                lambda e: on_like_click(
                    like_btn,
                    dislike_btn,
                    state,
                    SVGS,
                    on_commit=(query, question),
                ),
            )
            dislike_btn.on(
                "click",
                lambda e: on_dislike_click(
                    like_btn,
                    dislike_btn,
                    state,
                    SVGS,
                    "dislike",
                ),
            )
    return row


@ui.page("/")
async def index_page(request: Request):

    user_id = authorize_user(request)
    _ = current_user.set(user_id)
    log_auth.info("User authorized", extra={"user_id": user_id})

    # Help speech avatar
    speech_bubble_sticky = None
    prompt_count = 0

    def _close_bubble():
        nonlocal speech_bubble_sticky
        if speech_bubble_sticky:
            try:
                speech_bubble_sticky.delete()  # bezpečné smazání
            except Exception:
                pass
            speech_bubble_sticky = None

    def show_recommendation(
        message: str = "Skoro bych Vám doporučil, vykašlete se na to...",
        duration: float = 6.0,
    ):
        nonlocal speech_bubble_sticky
        _close_bubble()

        # VLOŽ bublinu jako dítě wrapperu tooltip_anchor (nad avatarem)
        with tooltip_anchor:  # <── DŮLEŽITÉ: použít wrapper z bodu 1
            with ui.element("div").classes(
                # POZOR: odstraněno "relative"
                "tooltip-card px-3 py-2 text-sm font-medium "
                "text-white bg-gray-900 dark:bg-gray-700 rounded-lg shadow-md "
                "opacity-0 invisible transition-all duration-200 translate-y-1 scale-95"
            ) as speech_bubble_sticky:
                ui.label(message).classes("leading-snug text-lg")
                ui.element("div").classes("tooltip-arrow")

        # zobrazit s animací (už nepotřebujeme zarovnání šipky)
        ui.run_javascript(
            """
        (function () {
        const card = document.querySelector('.tooltip-item .tooltip-card');
        if (!card) return;
        card.classList.remove('opacity-0','invisible','translate-y-1','scale-95');
        card.classList.add('opacity-100','translate-y-0','scale-100');
        })();
        """
        )

        if duration:
            ui.timer(duration, _close_bubble, once=True)

    chat_hook = await get_user_chat_hook(user_id)
    history = get_user_history(user_id)
    # 🔹 Historie otázek a odpovědí
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

    def build_logs_ui(parent):
        state = {
            "running": True,
            "tail": 500,
            "level": "ALL",  # SINGLE select: ALL / DEBUG / INFO / WARNING / ERROR / CRITICAL
            "logger_filter": "",
            "search": "",
            "autoscroll": False,
            "user_filter": "",
            "open_keys": set(),
        }

        def normalize_level(x: str | None) -> str | None:
            if not x:
                return x
            x = str(x).upper()
            # držme se standardních názvů; UI neposílá aliasy
            aliases = {"WARN": "WARNING", "FATAL": "CRITICAL", "CRIT": "CRITICAL"}
            return aliases.get(x, x)

        def make_key(r: dict) -> str:
            return f"{r.get('ts','')}|{r.get('logger','')}|{r.get('module','')}|{r.get('line','')}"

        # Filtr pro zobrazení v UI (včetně dalších polí, ať se ti pohled chová jako dřív)
        def passes_for_view(r: dict) -> bool:
            # LEVEL (single)
            if state["level"] != "ALL":
                if normalize_level(r.get("level")) != normalize_level(state["level"]):
                    return False
            # Logger/module
            if lf := state["logger_filter"].strip().lower():
                cand = (r.get("logger", "") + "." + r.get("module", "")).lower()
                if lf not in cand:
                    return False
            # User
            if uf := state["user_filter"].strip().lower():
                if uf not in (str(r.get("user_id", "")) or "").lower():
                    return False
            # Full-text
            if s := state["search"].strip().lower():
                hay = " ".join(
                    [
                        r.get("message", ""),
                        r.get("logger", ""),
                        r.get("module", ""),
                        r.get("exc_text", "") or "",
                        str(r.get("extra", "") or ""),
                    ]
                ).lower()
                if s not in hay:
                    return False
            return True

        # Export jen podle SINGLE levelu (ALL = všechno); cesta ./tmp v projektu
        def export_ndjson():
            base_dir = Path(__file__).resolve().parent / "tmp"
            base_dir.mkdir(parents=True, exist_ok=True)

            rows = LOG_BUS.get_last(state["tail"])
            if state["level"] != "ALL":
                lvl = normalize_level(state["level"])
                rows = [r for r in rows if normalize_level(r.get("level")) == lvl]

            ts = time.strftime("%Y%m%d-%H%M%S")
            suffix = (
                "ALL" if state["level"] == "ALL" else normalize_level(state["level"])
            )
            path = base_dir / f"logs-{suffix}-{ts}.ndjson"

            with open(path, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

            ui.download(str(path))

        with parent:
            with ui.row().classes("items-end gap-3"):
                # SINGLE select – žádné dicty, žádné aliasy
                level_select = ui.select(
                    options=["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                    value="ALL",
                    label="Level",
                    with_input=False,
                    clearable=False,
                )
                level_select.bind_value(state, "level")

                logger_in = ui.input("Logger/module contains")
                logger_in.on(
                    "update:model-value",
                    lambda e: (
                        state.update(logger_filter=e.args or ""),
                        paint.refresh(),
                    ),
                )

                user_in = ui.input("User ID contains")
                user_in.on(
                    "update:model-value",
                    lambda e: (state.update(user_filter=e.args or ""), paint.refresh()),
                )

                search_in = ui.input("Search in message/traceback")
                search_in.on(
                    "update:model-value",
                    lambda e: (state.update(search=e.args or ""), paint.refresh()),
                )

                ui.number("Tail", value=500, min=50, max=10000, step=50).on(
                    "change",
                    lambda e: (state.update(tail=int(e.args or 500)), paint.refresh()),
                )

                # Jedno tlačítko – export podle zvoleného levelu
                ui.button("Export NDJSON", on_click=export_ndjson)

            container = ui.column().classes("w-full gap-0")

            @ui.refreshable
            def paint():
                container.clear()
                rows = LOG_BUS.get_last(state["tail"])

                for r in (rr for rr in rows if passes_for_view(rr)):
                    row_key = make_key(r)
                    with ui.card().classes("w-full mb-1"):
                        with ui.row().classes("w-full items-start gap-2 no-wrap"):
                            ui.label(r.get("iso", "")).classes(
                                "text-xs text-gray-500"
                            ).style("min-width: 140px")
                            ui.html(
                                f"<b style='color:{LEVEL_COLORS.get(r.get('level','INFO'), '#374151')}'>{r.get('level')}</b>"
                            )
                            ui.label(
                                f"{r.get('logger','')}.{r.get('module','')}:{r.get('line','')}"
                            ).classes("text-xs text-gray-600")
                            ui.label(r.get("message", "")).classes(
                                "text-sm break-words"
                            )
                            if r.get("user_id"):
                                ui.badge(f"user:{r['user_id']}").classes("text-[10px]")
                            if r.get("req_id"):
                                ui.badge(f"req:{r['req_id']}").classes("text-[10px]")

                        if r.get("exc_text"):
                            exp = ui.expansion(
                                "Traceback", value=(row_key in state["open_keys"])
                            )

                            def on_expansion_toggle(e, k=row_key):
                                is_open = bool(e.args)
                                if is_open:
                                    state["open_keys"].add(k)
                                    state["autoscroll"] = False
                                    state["running"] = False
                                else:
                                    state["open_keys"].discard(k)
                                    if not state["open_keys"]:
                                        state["running"] = True
                                paint.refresh()

                            exp.on("update:model-value", on_expansion_toggle)

                            with exp:
                                ui.markdown(f"```\n{r['exc_text']}\n```")

                if state["autoscroll"]:
                    ui.run_javascript("window.scrollTo(0, document.body.scrollHeight);")

            paint()

            def on_timer():
                if state["running"]:
                    paint.refresh()

            ui.timer(0.5, on_timer)

        # sticky panel (beze změn)
        ui.add_css(".q-page-sticky{z-index:10000;}")
        with ui.page_sticky(position="bottom-left", x_offset=16, y_offset=16):
            with ui.column().classes("gap-2"):
                with ui.row().classes(
                    "bg-white/90 dark:bg-neutral-800/90 backdrop-blur rounded-xl shadow-lg "
                    "px-3 py-2 items-center gap-3 pointer-events-auto"
                ):
                    ui.label("Autoscroll").classes("text-xs text-gray-600")
                    ui.switch().bind_value(state, "autoscroll")
                    ui.badge().bind_text_from(
                        state, "autoscroll", backward=lambda v: "ON" if v else "OFF"
                    )

                with ui.row().classes(
                    "bg-white/90 dark:bg-neutral-800/90 backdrop-blur rounded-xl shadow-lg "
                    "px-3 py-2 items-center gap-3 pointer-events-auto"
                ):
                    ui.label("Logs feed").classes("text-xs text-gray-600")
                    ui.button("Pause", on_click=lambda: state.update(running=False))
                    ui.button("Resume", on_click=lambda: state.update(running=True))
                    ui.badge().bind_text_from(
                        state,
                        "running",
                        backward=lambda v: "RUNNING" if v else "PAUSED",
                    )

    async def send() -> None:
        nonlocal feedback_row, prompt_count
        question = text.value.strip()
        current_req.set(uuid.uuid4().hex[:8])

        if not question:
            return

        log_chat.info("User question received", extra={"len": len(question)})

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

        # AI stuff
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
            answer=answer_text,
            user_id=user_id,
            session_id=history.get_history_id(),
        )

        prompt_count += 1
        if prompt_count == 2:
            show_recommendation(
                message="Skoro bych Vám doporučil, vykašlete se na to...", duration=6.0
            )

        # 🔹 Aktualizace log panelu
        history_container.clear()
        with history_container:
            for q, a in history.get_all_history():
                with ui.column().classes("mb-4 p-2 border-b border-gray-300"):
                    ui.markdown(f"**Q:** {q}")
                    ui.markdown(f"**A:** {a}")
        ui.run_javascript(
            "document.getElementById('chat-scroll')?.scrollTo({top: 1e9, behavior: 'smooth'});"
        )

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

    # the queries below are used to expand the content down to the footer (content can then use flex-grow to expand)
    ui.query(".q-page").classes("flex")
    ui.query(".nicegui-content").classes("w-full px-4 py-4")

    with ui.tabs().classes("w-full") as tabs:
        chat_tab = ui.tab("Chat")
        logs_tab = ui.tab("Logs")
        history_tab = ui.tab("History")
        graphql_tab = ui.tab("GraphQL")

    with ui.tab_panels(tabs, value=chat_tab).classes(
        "fullscreen-tabs w-full h-screen max-w-none mx-0 p-0 items-stretch"
    ):
        message_container = ui.tab_panel(chat_tab).classes("items-stretch")
        with message_container:
            # jeden řádek = dvě kolony: vlevo TABY s tabulkou, vpravo chat
            with ui.row().classes("w-full gap-4 items-start"):
                # ========== LEVÝ TABSET (samostatné taby pro tabulku) ==========
                with ui.card().classes("w-80 shrink-0 rounded-2xl shadow-md"):
                    # vertikální tabs kvůli úzké šířce; klidně smaž .props('vertical') pokud nechceš
                    with ui.column().classes("w-full"):
                        with ui.tabs().props("vertical").classes("w-full") as left_tabs:
                            products_tab = ui.tab("Chat history")

                        with ui.tab_panels(left_tabs, value=products_tab).classes(
                            "w-full"
                        ):
                            with ui.tab_panel(products_tab):
                                user_sessions = get_user_sorted_sessions(user_id)
                                num_sessions = len(user_sessions)
                                ui.label(f"Sessions ({num_sessions})").classes(
                                    "text-sm font-semibold mb-2"
                                )

                                row_height_px = 32
                                max_table_height = min(
                                    num_sessions * row_height_px, 400
                                )

                                with ui.element("div").props("id=product-scroll").style(
                                    f"max-height: {max_table_height}px; overflow-y: auto;"
                                ):
                                    user_sessions = get_user_sorted_sessions(user_id)
                                    for sid in user_sessions:
                                        ui.button(
                                            sid,
                                            on_click=lambda sid=sid: load_and_display_session(
                                                sid, chat_stream, user_id, gql_client
                                            ),
                                        ).props("flat dense").classes(
                                            "w-full text-left"
                                        )

                # PRAVÁ KARTA: CHAT
                with ui.card().classes(
                    "flex-1 min-w-0 rounded-2xl shadow-lg light:bg-white dark:bg-green-800 overflow-x-hidden"
                ):
                    with ui.column().classes("w-full min-w-0"):
                        # scrollovací obal pro chat (zůstane uvnitř karty)
                        chat_scroll = (
                            ui.element("div")
                            .props("id=chat-scroll")
                            .classes("w-full")  # ← w-full přesunuto do class
                            .style("max-height: 70vh; overflow-y: auto;")
                        )
                        ui.add_css(
                            """
                        #chat-scroll {
                            scrollbar-width: none;  /* Firefox */
                            -ms-overflow-style: none;  /* IE 10+ */
                        }

                        #chat-scroll::-webkit-scrollbar {
                            width: 0px;  /* Chrome, Safari, Edge */
                            background: transparent;
                        }
                        """
                        )
                        with chat_scroll:
                            # >>> TADY BUDEME VŽDY PŘIDÁVAT ZPRÁVY <<<
                            chat_stream = ui.column().classes("w-full gap-2")

                            # placeholder zpráva
                            with chat_stream:
                                ui.chat_message(
                                    text="Noo, co potřebuješ?",
                                    name="Tadeáš",
                                    sent=False,
                                    avatar="/assets/img/Tadeas.png",
                                ).props("bg-color=green text-color=dark")
        # with ui.tab_panels(tabs, value=chat_tab).classes(
        #     "w-full max-w-3xl mx-auto flex-grow items-stretch rounded-2xl shadow-lg light:bg-white dark:bg-green-800"
        # ):
        #     message_container = ui.tab_panel(chat_tab).classes(
        #         "items-stretch bg-color-green"
        #     )
        #     with message_container:
        #         ui.chat_message(
        #             text="Noo, co potřebuješ?",
        #             name="Tadeáš",
        #             sent=False,
        #             avatar="/assets/img/Tadeas.png",
        #         ).props("bg-color=green text-color=dark")

        #######################################################
        # * Logs tab
        #######################################################
        with ui.tab_panel(logs_tab) as logs_container:
            ui.label("Conversation Log").classes("font-bold mb-2")
            build_logs_ui(logs_container)

        #######################################################
        # * History tab
        #######################################################
        with ui.tab_panel(history_tab) as history_container:
            ui.label("Conversation history").classes("font-bold mb-2")
            with history_container:
                for q, a in history.get_all_history():
                    with ui.column().classes("mb-4 p-2 border-b border-gray-300"):
                        ui.markdown(f"**Q:** {q}")
                        ui.markdown(f"**A:** {a}")

        #######################################################
        # * GraphQL tab
        #######################################################
        with ui.tab_panel(graphql_tab).classes("items-stretch"):
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
                # ochrana: klient musí být připraven
                if gql_client is None:
                    with gql_container:
                        ui.markdown("> ⚠️ GraphQL klient ještě není inicializován.")
                    return

                # načti dotaz a proměnné
                query = (query_input.value or "").strip()

                log_gql.info("GraphQL query run", extra={"preview": query[:100]})

                try:
                    variables = (
                        json.loads(variables_input.value)
                        if variables_input.value
                        else {}
                    )
                    if not isinstance(variables, dict):
                        raise ValueError("Variables must be a JSON object")
                except Exception as e:
                    with gql_container:
                        ui.markdown(f"> ❌ Chyba v JSON variables: `{e}`")
                    return

                # vykresli widget
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

    with ui.element("div").classes(
        "tooltip-item fixed bottom-10 right-6 z-[9999]"
    ) as tooltip_anchor:
        with ui.button(
            on_click=lambda: show_recommendation(message="Aha, tak to je blbá chyba...")
        ).props("round flat dense").classes("p-0 avatar-cta"):
            ui.image("/assets/img/profesor.png").classes(
                "w-[120px] h-[120px] rounded-full object-cover pointer-events-none"
            ).props('alt="Rounded avatar"')


ui.run_with(
    app,
    title="TedGPT",
    favicon="./assets/img/tedGPT.png",
    dark=None,
    tailwind=True,
    storage_secret="SUPER-SECRET",
)
