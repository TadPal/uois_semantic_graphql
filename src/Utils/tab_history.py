from nicegui import ui
from Database.ChatHistory.get_sessions import get_unique_sessions_by_user_id
from Database.ChatHistory.get_from_db import load_chat_history


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
