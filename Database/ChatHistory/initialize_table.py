import psycopg2

def initialize_chathistory_table(conn):
    """
    Checks if the 'chat_history' table exists and creates it if it does not.

    The table will contain columns for 'id', 'user_id', and 'messages'.

    Args:
        conn: A psycopg2 connection object.
    """
    command = """
        -- Create the 'chat_history' table only if it does not already exist.
        CREATE TABLE IF NOT EXISTS chat_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            messages TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP

        );
        """
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(command)
            conn.commit()
            cursor.close()
            print("Chat history table 'chat_history' checked and created if needed.")
        except psycopg2.Error as error:
            print(f"Error executing command: {error}")
            conn.rollback()
