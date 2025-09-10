from nicegui import ui
from Database.ChatHistory.get_sessions import get_unique_sessions_by_user_id
from Database.ChatHistory.get_from_db import load_chat_history
import json


def get_user_sorted_sessions(user_id, conn=None):
    """
    Vrátí seznam session_id pro uživatele seřazený od nejnovějšího (index 0).
    """
    sessions = get_unique_sessions_by_user_id(user_id, conn)
    return [s[0] for s in sessions]  # vezmi jen session_id


def load_session_chat(user_id, session_id, conn=None):
    """
    Načte historii konkrétní session pro daného uživatele.
    """
    return load_chat_history(user_id, session_id, conn)


def load_and_display_session(session_id, chat_stream, user_id):
    """
    Vymaže hlavní chat a načte do něj všechny zprávy z konkrétní session,
    od nejnovější po nejstarší.
    """
    chat_stream.clear()  # smaže předchozí chat

    # načti historii přes hotovou funkci
    chat_history = load_chat_history(user_id, session_id)

    with chat_stream:
        for row in chat_history:  # řazeno DESC = nejnovější nahoře
            messages = row["messages"]

            # answer je JSON string -> převedeme na čistý text
            answer_json = row["answer"]
            try:
                answer_dict = json.loads(answer_json)
                answer_text = answer_dict.get("Response", answer_json)
            except Exception:
                answer_text = answer_json  # fallback pokud není JSON

            # přidej zprávy do hlavního chatu
            ui.chat_message(messages, name="You", sent=True)
            ui.chat_message(
                answer_text, name="Tadeáš", sent=False, avatar="/assets/img/Tadeas.png"
            )
