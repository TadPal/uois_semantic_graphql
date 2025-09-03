import psycopg2
from psycopg2 import sql
from Database.connection import connect_to_postgres
import os


def load_chat_history(user_id, session_id, conn=None):
    """
    Loads chat history for a specific user and session, ordered from newest to oldest.

    Args:
        conn (psycopg2.connection): The database connection object.
        user_id (str): The UUID of the user.
        session_id (str): The UUID of the session.

    Returns:
        list of dicts: A list of chat history records, where each record is a dictionary.
    """

    if not conn:
        conn = connect_to_postgres(os.environ)

    try:
        cursor = conn.cursor()

        query = sql.SQL(
            "SELECT id, user_id, session_id, messages, answer, created_at FROM chat_history WHERE user_id = %s AND session_id = %s ORDER BY created_at DESC"
        )

        cursor.execute(
            query,
            (
                user_id,
                session_id,
            ),
        )

        column_names = [desc[0] for desc in cursor.description]

        chat_history_rows = cursor.fetchall()

        chat_history_dicts = []
        for row in chat_history_rows:
            row_dict = dict(zip(column_names, row))
            chat_history_dicts.append(row_dict)

        print(
            f"Successfully loaded chat history for user ID: {user_id} and session ID: {session_id}."
        )
        return chat_history_dicts

    except psycopg2.Error as error:
        print(f"Error loading chat history: {error}")
        return []

    finally:
        if cursor:
            cursor.close()
