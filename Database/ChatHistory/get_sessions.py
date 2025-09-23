import psycopg2
from psycopg2 import sql
from Database.connection import connect_to_postgres
import os


def get_unique_sessions_by_user_id(user_id, conn=None):
    """
    Retrieves a list of unique session IDs for a specific user ID,
    sorted from newest to oldest by their most recent message timestamp.

    Args:
        user_id (str): The UUID of the user.
        conn (psycopg2.connection): The database connection object.

    Returns:
        list: A list of tuples, where each tuple contains (session_id, created_at),
              or an empty list if an error occurs.
    """
    if not conn:
        conn = connect_to_postgres(os.environ)

    sessions = []

    try:
        cursor = conn.cursor()

        # Select unique session_ids and the latest created_at timestamp for each,
        # then order the results from newest to oldest.
        cursor.execute(
            sql.SQL(
                """
                SELECT session_id, created_at, messages
                FROM (
                    SELECT DISTINCT ON (session_id) session_id, created_at, messages
                    FROM chat_history
                    WHERE user_id = %s
                    ORDER BY session_id, created_at ASC   -- pick earliest per session
                ) sub
                ORDER BY created_at DESC;
                """
            ),
            (str(user_id),),
        )

        # Fetch all the rows returned by the query.
        sessions = cursor.fetchall()

    except psycopg2.Error as error:
        print(f"Error retrieving unique sessions: {error}")

    finally:
        if cursor:
            cursor.close()

    return sessions
