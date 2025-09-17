from nicegui import ui
from Database.ChatHistory.get_sessions import get_unique_sessions_by_user_id
from Database.ChatHistory.get_from_db import load_chat_history
from src.Utils.graphQLdata import GraphQLData
import json
import typing

import uuid
from Database.ChatHistory.add_to_db import add_chat_history


def get_user_sorted_sessions(user_id, conn=None):
    """
    Vrátí seznam session_id pro uživatele seřazený od nejnovějšího (index 0).
    """
    sessions = get_unique_sessions_by_user_id(user_id, conn)
    return [s[0] for s in sessions]


def load_session_chat(user_id, session_id, conn=None):
    """
    Načte historii konkrétní session pro daného uživatele.
    """
    return load_chat_history(user_id, session_id, conn)


def _parse_variables(vars_in) -> dict:
    """Vezme variables (dict nebo JSON string) a vrátí dict."""
    if vars_in is None:
        return {}
    if isinstance(vars_in, dict):
        return vars_in
    if isinstance(vars_in, str):
        try:
            return json.loads(vars_in)
        except Exception:
            # když to není validní JSON, vrať prázdné a neblokuj UI
            return {}
    # fallback: cokoli jiného převedeme na dict pokud to dává smysl
    return dict(vars_in) if isinstance(vars_in, typing.Mapping) else {}


def load_and_display_session(session_id, chat_stream, user_id, gql_client):
    """
    Vymaže hlavní chat a načte do něj všechny zprávy z konkrétní session,
    a pokud odpověď obsahuje GraphQL dotaz, zobrazí pod ní GraphQLData.
    """
    chat_stream.clear()

    # DB často vrací DESC (nejnovější první); zachováme pořadí z DB.
    chat_history = load_chat_history(user_id, session_id)

    with chat_stream:
        for row in reversed(
            chat_history
        ):  # pokud chceš chronologicky, dej: for row in reversed(chat_history):
            user_msg = row.get("messages", "")

            # answer je JSON string -> vytáhneme Response / Query / Variables
            answer_json = row.get("answer", "")
            query = None
            variables = {}
            try:
                answer_dict = json.loads(answer_json)
                answer_text = answer_dict.get("Response", answer_json)
                query = answer_dict.get("Query")
                variables = _parse_variables(answer_dict.get("Variables"))
            except Exception:
                answer_text = answer_json  # fallback, když answer není JSON

            # uživatel vpravo
            if user_msg:
                ui.chat_message(user_msg, name="You", sent=True).props(
                    "bg-color=primary text-color=white"
                ).classes("ml-auto justify-end")

            # asistent vlevo
            if answer_text:
                ui.chat_message(
                    answer_text,
                    name="Tadeáš",
                    sent=False,
                    avatar="/assets/img/Tadeas.png",
                ).props("bg-color=grey-2 text-color=dark")

            # pokud je k dispozici GraphQL dotaz, vlož widget
            if query:
                GraphQLData(
                    gqlclient=gql_client,
                    query=query,
                    variables=variables,
                    result=None,
                    metadata=None,
                    autoload=True,
                )


def create_new_session(
    user_id, gql_client, chat_stream=None, sessions_container=None, conn=None
):
    """
    Pokud chat_stream je None, nebude se nic vykreslovat — jen logika pro DB.
    """
    session_id = str(uuid.uuid4())

    # add_chat_history(
    #     message="",
    #     answer="New session created.",
    #     user_id=user_id,
    #     session_id=session_id,
    #     conn=conn,
    # )

    # získáme historii uživatele
    from History.chatHistory import UserChatHistory
    from main import history  # dictionary user_id -> UserChatHistory

    if user_id not in history:
        history[user_id] = UserChatHistory()
    user_history = history[user_id]

    # nastav aktuální session na novou
    user_history.set_history_id(session_id)

    # pokud je chat_stream předán (pravá karta), vyčisti a zobraz placeholder
    if chat_stream:
        chat_stream.clear()
        with chat_stream:
            ui.chat_message(
                "Noo, co potřebuješ?",
                name="Tadeáš",
                sent=False,
                avatar="/assets/img/Tadeas.png",
            ).props("bg-color=green text-color=dark")

        load_and_display_session(session_id, chat_stream, user_id, gql_client)

        # refresh seznamu vlevo
    if sessions_container:
        render_sessions_list(user_id, chat_stream, gql_client, sessions_container)

    return session_id


def render_sessions_list(
    user_id, chat_stream=None, gql_client=None, sessions_container=None
):
    if not sessions_container:
        return  # když není, nic nedělej

    sessions_container.clear()  # smaže starý obsah

    user_sessions = get_user_sorted_sessions(user_id)
    num_sessions = len(user_sessions)

    with sessions_container:  # teď už to není None, ale UI column
        ui.label(f"Sessions ({num_sessions})").classes("text-sm font-semibold mb-2")

        row_height_px = 50
        max_table_height = min(num_sessions * row_height_px, 600)

        with ui.element("div").props("id=product-scroll").style(
            f"max-height: {max_table_height}px; overflow-y: auto;"
        ):

            from main import history
            from History.chatHistory import UserChatHistory

            for sid in user_sessions:

                def on_click_session(sid=sid):
                    # 1) načti chat do pravého panelu
                    if chat_stream:
                        load_and_display_session(sid, chat_stream, user_id, gql_client)

                    # 2) aktualizuj UserChatHistory na tuto session
                    if user_id in history:
                        user_history: UserChatHistory = history[user_id]
                        user_history.set_history_id(sid)
                    else:
                        # pokud historie ještě není, vytvoř ji
                        history[user_id] = UserChatHistory()
                        history[user_id].set_history_id(sid)

                ui.button(sid, on_click=on_click_session).props("flat dense").classes(
                    "w-full text-left"
                )
