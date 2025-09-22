import psycopg2
from psycopg2 import sql
from Database.connection import connect_to_postgres
import os


def get_session_title(session_id, conn=None):
    """
    Retrieves the first 10 characters of the first message
    in a given session to use as a title.

    Args:
        session_id (str): The UUID of the session.
        conn (psycopg2.connection): The database connection object.

    Returns:
        str: The first 10 characters of the initial message,
             or an empty string if an error occurs or no message is found.
    """
    if not conn:
        conn = connect_to_postgres(os.environ)

    title = ""

    try:
        cursor = conn.cursor()

        # Find the oldest message in the session based on the created_at timestamp.
        # Then, get the first 10 characters of its content.
        cursor.execute(
            sql.SQL(
                """
                SELECT SUBSTRING(messages, 1, 10)
                FROM chat_history
                WHERE session_id = %s
                ORDER BY created_at ASC
                LIMIT 1;
                """
            ),
            (str(session_id),),
        )

        result = cursor.fetchone()

        if result:
            title = result[0]
            print(f"Successfully retrieved title for session ID: {session_id}.")
        else:
            print(f"No messages found for session ID: {session_id}.")

    except psycopg2.Error as error:
        print(f"Error retrieving session title: {error}")

    finally:
        if cursor:
            cursor.close()
    return title
