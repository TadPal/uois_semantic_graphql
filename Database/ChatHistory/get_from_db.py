import psycopg2
from psycopg2 import sql

def load_chat_history(conn, user_id):
    """
    Loads chat history for a specific user, ordered from newest to oldest.

    Args:
        conn (psycopg2.connection): The database connection object.
        user_id (str): The UUID of the user.

    Returns:
        list of tuples: A list of chat history records, where each record is a tuple
                        containing (id, user_id, messages, created_at).
    """
    if not conn:
        print("Database connection is not available. Cannot load chat history.")
        return []

    try:
        cursor = conn.cursor()

        # The query selects all columns for a given user_id and orders by created_at descending.
        query = sql.SQL("SELECT id, user_id, messages, created_at FROM chat_history WHERE user_id = %s ORDER BY created_at DESC")
        
        cursor.execute(query, (user_id,))

        # Get column names from the cursor description
        column_names = [desc[0] for desc in cursor.description]
        
        # Fetch all matching rows
        chat_history_rows = cursor.fetchall()

        # Convert list of tuples to list of dictionaries
        chat_history_dicts = []
        for row in chat_history_rows:
            row_dict = dict(zip(column_names, row))
            chat_history_dicts.append(row_dict)
        
        print(f"Successfully loaded chat history for user ID: {user_id}.")
        return chat_history_dicts

    except psycopg2.Error as error:
        print(f"Error loading chat history: {error}")
        return []

    finally:
        if cursor:
            cursor.close()
