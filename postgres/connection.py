import psycopg2
from psycopg2 import sql
import os
from dotenv import load_dotenv, dotenv_values

load_dotenv()


def connect_to_postgres():
    """
    Connect to PostgreSQL database
    """
    try:
        # Connection parameters
        connection = psycopg2.connect(
            host=os.getenv("DBHOSTNAME"),
            database=os.getenv("DBNAME"),
            user=os.getenv("DBUSERNAME"),
            password=os.getenv("DBPASS"),
            port=os.getenv("DBPORT"),
        )

        print("Successfully connected to PostgreSQL")
        return connection

    except psycopg2.Error as error:
        print(f"Error connecting to PostgreSQL: {error}")
        return None


def execute_command(connection, command):
    """
    Execute a SQL command
    """
    try:
        cursor = connection.cursor()
        cursor.execute(command)
        connection.commit()
        print("Command executed successfully")
        cursor.close()

    except psycopg2.Error as error:
        print(f"Error executing command: {error}")
        connection.rollback()


# Main execution
if __name__ == "__main__":
    # Connect to database
    conn = connect_to_postgres()

    command = """
    CREATE EXTENSION IF NOT EXISTS vector;

    DROP TABLE IF EXISTS graphql_types;

    CREATE TABLE graphql_types (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE,
        description TEXT,
        embedding vector(1024)
    );

    CREATE INDEX IF NOT EXISTS idx_graphql_types_embedding
        ON graphql_types
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """

    if conn:
        execute_command(conn, command)

        # You can execute other commands here
        # execute_command(conn, "INSERT INTO empty_table (name, email) VALUES ('John', 'john@example.com');")
        # execute_command(conn, "SELECT * FROM empty_table;")

        # Close connection
        conn.close()
        print("Connection closed")
