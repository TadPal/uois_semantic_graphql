import psycopg2
from psycopg2 import sql


def connect_to_postgres():
    """
    Connect to PostgreSQL database
    """
    try:
        # Connection parameters
        connection = psycopg2.connect(
            host="localhost",  # Your PostgreSQL host
            database="data",  # Your database name
            user="postgres",  # Your username
            password="example",  # Your password
            port="5434",  # PostgreSQL port (default is 5432)
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


def create_empty_table(connection):
    """
    Create an empty table with basic structure
    """
    create_table_query = """
    CREATE TABLE IF NOT EXISTS empty_table (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100),
        email VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    execute_command(connection, create_table_query)


# Main execution
if __name__ == "__main__":
    # Connect to database
    conn = connect_to_postgres()

    command = """
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS graphql_types (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL,
        embedding VECTOR(1536) NOT NULL
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
