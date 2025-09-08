import psycopg2
from psycopg2 import sql
from Database.connection import connect_to_postgres
import os


def count_unique_sessions(user_id, conn=None):
    """
    Counts the number of unique session_ids for a specific user ID.

    Args:
        user_id (str): The UUID of the user.
        conn (psycopg2.connection): The database connection object.

    Returns:
        int: The number of unique sessions, or -1 if an error occurs.
    """
    if not conn:
        conn = connect_to_postgres(os.environ)

    count = -1

    try:
        cursor = conn.cursor()

        # Use COUNT(DISTINCT...) to count only unique session_ids.
        cursor.execute(
            sql.SQL(
                """
                SELECT COUNT(DISTINCT session_id)
                FROM chat_history
                WHERE user_id = %s;
                """
            ),
            (str(user_id),),
        )

        # Fetch the single result from the query.
        count = cursor.fetchone()[0]
        print(f"User ID {user_id} has {count} unique sessions.")

    except psycopg2.Error as error:
        print(f"Error counting unique sessions: {error}")

    finally:
        if cursor:
            cursor.close()

    return count
