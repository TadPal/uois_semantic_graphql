import asyncio
import json

# Auth
from Auth.auth import authorize_user

# FastAPI part
import asyncio
from fastapi import FastAPI, Request, Response
from SemanticKernel import (
    openChat,
)
from History.chatHistory import UserChatHistory


from src.Utils.on_button_press import FeedbackState, render_buttons, on_like_click, on_dislike_click
from src.Utils.graphQLdata import GraphQLData

# Store per user chat instances
user_chats = {}
history = {}


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
    gql_client = await createGQLClient(
        username="john.newbie@world.com",
        password="john.newbie@world.com"
    )


app = FastAPI(on_startup=[startup_gql_client])

from nicegui import ui, app as nicegui_app, storage, core
from starlette.middleware.sessions import SessionMiddleware

nicegui_app.add_middleware(storage.RequestTrackingMiddleware)
nicegui_app.add_middleware(SessionMiddleware, secret_key="SUPER-SECRET")

nicegui_app.add_static_files("/assets", "./assets")


@ui.page("/")
async def index_page(request: Request):

    user_id = authorize_user(request)

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

    async def send() -> None:
        nonlocal feedback_row, prompt_count
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
        history.add_entry(question=question, answer=result)
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

        with message_container:  # NEW
            # if feedback_row:
            #     feedback_row.delete()
            # with ui.row().classes("ml-12 gap-1 -mt-4") as feedback_row:
                # --- SVG ikony ---
                like_default = """
                <svg class="w-6 h-6 text-blue-700 dark:text-gray-200" xmlns="http://www.w3.org/2000/svg" 
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" 
                        d="M7 11c.889-.086 1.416-.543 2.156-1.057a22.323 22.323 0 0 0 
                            3.958-5.084 1.6 1.6 0 0 1 .582-.628 1.549 1.549 0 0 1 
                            1.466-.087c.205.095.388.233.537.406a1.64 1.64 0 0 1 
                            .384 1.279l-1.388 4.114M7 11H4v6.5A1.5 1.5 0 0 0 
                            5.5 19v0A1.5 1.5 0 0 0 7 17.5V11Zm6.5-1h4.915c.286 0 
                            .372.014.626.15.254.135.472.332.637.572a1.874 1.874 
                            0 0 1 .215 1.673l-2.098 6.4C17.538 19.52 17.368 20 
                            16.12 20c-2.303 0-4.79-.943-6.67-1.475"/>
                </svg>
                """

                like_selected = """
                <svg class="w-6 h-6 text-blue-700 dark:text-gray-200" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" 
                    width="24" height="24" fill="currentColor" viewBox="0 0 24 24">
                <path fill-rule="evenodd" d="M15.03 9.684h3.965c.322 0 .64.08.925.232.286.153.532.374.717.645a2.109 2.109 0 0 1 .242 1.883l-2.36 7.201c-.288.814-.48 1.355-1.884 1.355-2.072 0-4.276-.677-6.157-1.256-.472-.145-.924-.284-1.348-.404h-.115V9.478a25.485 25.485 0 0 0 4.238-5.514 1.8 1.8 0 0 1 .901-.83 1.74 1.74 0 0 1 1.21-.048c.396.13.736.397.96.757.225.36.32.788.269 1.211l-1.562 4.63ZM4.177 10H7v8a2 2 0 1 1-4 0v-6.823C3 10.527 3.527 10 4.176 10Z" clip-rule="evenodd"/>
                </svg>
                """

                dislike_default = """
                <svg class="w-6 h-6 text-blue-500 dark:text-gray-400" xmlns="http://www.w3.org/2000/svg" 
                    fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" 
                        d="M17 13c-.889.086-1.416.543-2.156 1.057a22.322 
                            22.322 0 0 0-3.958 5.084 1.6 1.6 0 0 1-.582.628 
                            1.549 1.549 0 0 1-1.466.087 1.587 1.587 0 0 1 
                            -.537-.406 1.666 1.666 0 0 1-.384-1.279l1.389-4.114
                            M17 13h3V6.5A1.5 1.5 0 0 0 18.5 5v0A1.5 1.5 0 0 0 
                            17 6.5V13Zm-6.5 1H5.585c-.286 0-.372-.014-.626-.15
                            a1.797 1.797 0 0 1-.637-.572 1.873 1.873 0 0 1 
                            -.215-1.673l2.098-6.4C6.462 4.48 6.632 4 7.88 4c2.302 
                            0 4.79.943 6.67 1.475"/>
                </svg>
                """

                dislike_selected = """
                <svg class="w-6 h-6 text-blue-500 dark:text-gray-400" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" 
                    width="24" height="24" fill="currentColor" viewBox="0 0 24 24">
                <path fill-rule="evenodd" d="M8.97 14.316H5.004c-.322 0-.64-.08-.925-.232a2.022 2.022 0 0 1-.717-.645 2.108 2.108 0 0 1-.242-1.883l2.36-7.201C5.769 3.54 5.96 3 7.365 3c2.072 0 4.276.678 6.156 1.256.473.145.925.284 1.35.404h.114v9.862a25.485 25.485 0 0 0-4.238 5.514c-.197.376-.516.67-.901.83a1.74 1.74 0 0 1-1.21.048 1.79 1.79 0 0 1-.96-.757 1.867 1.867 0 0 1-.269-1.211l1.562-4.63ZM19.822 14H17V6a2 2 0 1 1 4 0v6.823c0 .65-.527 1.177-1.177 1.177Z" clip-rule="evenodd"/>
                </svg>
                """

                SVGS = {
                    "like_default": like_default,
                    "like_selected": like_selected,
                    "dislike_default": dislike_default,
                    "dislike_selected": dislike_selected,
                }

                state = FeedbackState()

                with ui.row().classes("ml-12 gap-1 -mt-4") as feedback_row:
                    # Inicialní render tlačítek
                    like_html, dislike_html = render_buttons(state, SVGS)

                    like_btn = ui.html(like_html)
                    dislike_btn = ui.html(dislike_html)

                    # Handlery – logika je v odděleném souboru
                    like_btn.on('click', lambda e: on_like_click(like_btn, dislike_btn, state, SVGS, "like"))
                    dislike_btn.on('click', lambda e: on_dislike_click(like_btn, dislike_btn, state, SVGS, "dislike"))


        ui.run_javascript("window.scrollTo(0, document.body.scrollHeight)")

    ui.add_css(
        """
        a:link, a:visited { color: inherit !important; text-decoration: none; font-weight: 500; }
        # ::-webkit-scrollbar { display: none; }
        # * { scrollbar-width: none; }
        /* Wrapper vpravo dole */
        .tooltip-item{
        position: fixed;
        bottom: 16px;
        right: 16px;
        display: flex;
        flex-direction: column;
        align-items: center;
        z-index: 9999;
        }

        /* Klikatelný avatar */
        .avatar-cta{ pointer-events: auto; z-index: 10000; }

        /* Bublina (jedna řádka) – posun doleva přes --x */
        .tooltip-card{
        --x: -90%;                       /* dolaď: -70%…-95% = více doleva */
        position: absolute;
        bottom: calc(100% + 8px);
        left: 50%;
        transform: translateX(var(--x)) scale(.95);
        white-space: nowrap;
        width: max-content;
        pointer-events: auto;
        z-index: 10001;
        }

        /* Viditelný stav – zachovej stejný posun */
        .tooltip-card.opacity-100{
        opacity: 1 !important;
        visibility: visible !important;
        transform: translateX(var(--x)) scale(1) !important;
        }

        /* Ocásek (dědí barvu pozadí bubliny) */
        .tooltip-card .tooltip-arrow{
        position: absolute;
        bottom: -6px;
        left: 90%;                        /* posun ocásku – klidně uprav */
        transform: translateX(-50%) rotate(45deg);
        width: 12px; height: 12px;
        background: inherit;
        border-radius: 2px;
        }
    """
    )

    # the queries below are used to expand the content down to the footer (content can then use flex-grow to expand)
    ui.query(".q-page").classes("flex")
    ui.query(".nicegui-content").classes("w-full")

    with ui.tabs().classes("w-full") as tabs:
        chat_tab = ui.tab("Chat")
        logs_tab = ui.tab("Logs")
        history_tab = ui.tab("History")
        graphql_tab = ui.tab("GraphQL")

    with ui.tab_panels(tabs, value=chat_tab).classes(
        "w-full max-w-3xl mx-auto flex-grow items-stretch rounded-2xl shadow-lg light:bg-white dark:bg-neutral-800"
    ):
        message_container = ui.tab_panel(chat_tab).classes("items-stretch")
        with message_container:
            ui.chat_message(
                text="Noo, co potřebuješ?",
                name="Tadeáš",
                sent=False,
                avatar="/assets/img/Tadeas.png",
            ).props("bg-color=grey-2 text-color=dark")

        #######################################################
        #* Logs tab
        #######################################################
        with ui.tab_panel(logs_tab) as logs_container:
            ui.label("Conversation Log").classes("font-bold mb-2")

        #######################################################
        #* History tab
        #######################################################
        with ui.tab_panel(history_tab) as history_container:
            ui.label("Conversation history").classes("font-bold mb-2")
            with history_container:
                for q, a in history.get_all_history():
                    with ui.column().classes("mb-4 p-2 border-b border-gray-300"):
                        ui.markdown(f"**Q:** {q}")
                        ui.markdown(f"**A:** {a}")

        #######################################################
        #* GraphQL tab
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
            query_input = ui.textarea(label="GraphQL query", value=default_query).props("rows=10")
            variables_input = ui.textarea(
                label='Variables (JSON, např. {"skip": 0, "limit": 10})',
                value='{"skip": 0, "limit": 10}'
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
                try:
                    variables = json.loads(variables_input.value) if variables_input.value else {}
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

            ui.button("Run query", on_click=run_graphql).props("color=primary").classes("mt-2")


    
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
