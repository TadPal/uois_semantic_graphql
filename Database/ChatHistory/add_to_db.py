import psycopg2
from psycopg2 import sql
from Database.connection import connect_to_postgres
import os


def add_chat_history(message, user_id, conn=None):
    """
    Adds a new message to the chat_history table for a specific user ID.

    Args:
        conn (psycopg2.connection): The database connection object.
        message (str): The text message to be saved.
        user_id (str): The UUID of the user.
    """

    if not conn:
        conn = connect_to_postgres(os.environ)

    try:
        cursor = conn.cursor()

        # Insert the message into the chat_history table with the provided user ID
        cursor.execute(
            sql.SQL("INSERT INTO chat_history (user_id, messages) VALUES (%s, %s)"),
            (user_id, message),
        )
        conn.commit()
        print(f"Message successfully added to chat history for user ID: {user_id}.")

    except psycopg2.Error as error:
        print(f"Error adding chat history: {error}")
        conn.rollback()

    finally:
        if cursor:
            cursor.close()
