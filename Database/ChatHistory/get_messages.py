import psycopg2
from psycopg2 import sql
from Database.connection import connect_to_postgres
import os


def get_messages_by_session_id(session_id, conn=None):
    """
    Retrieves all messages for a specific session ID from the chat_history table.

    Args:
        session_id (str): The UUID of the session.
        conn (psycopg2.connection): The database connection object.

    Returns:
        list: A list of tuples, where each tuple represents a row from the
              chat_history table, or an empty list if an error occurs.
    """
    if not conn:
        conn = connect_to_postgres(os.environ)

    messages = []

    try:
        cursor = conn.cursor()

        # Select all columns for the specified session_id.
        cursor.execute(
            sql.SQL(
                """
                SELECT * FROM chat_history
                WHERE session_id = %s
                ORDER BY created_at DESC;
                """
            ),
            (str(session_id),),
        )

        # Fetch all the rows returned by the query.
        messages = cursor.fetchall()
        print(
            f"Successfully retrieved {len(messages)} messages for session ID: {session_id}."
        )

    except psycopg2.Error as error:
        print(f"Error retrieving chat history: {error}")

    finally:
        if cursor:
            cursor.close()

    return messages
