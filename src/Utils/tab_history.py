from nicegui import ui
from Database.ChatHistory.get_sessions import get_unique_sessions_by_user_id
from Database.ChatHistory.get_from_db import load_chat_history
from src.Utils.graphQLdata import GraphQLData
import json
import typing


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
        for (
            row
        ) in (
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
