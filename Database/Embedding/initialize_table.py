import psycopg2


def initialize_embedding_table(conn):

    embedding_dimension = 1024

    command = f"""
    CREATE EXTENSION IF NOT EXISTS vector;

    DROP TABLE IF EXISTS graphql_types;

    CREATE TABLE graphql_types (
        id SERIAL PRIMARY KEY,
        question TEXT UNIQUE,
        answer TEXT,
        embedding vector({embedding_dimension})
    );

    CREATE INDEX IF NOT EXISTS idx_graphql_types_embedding
        ON graphql_types
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """

    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(command)
            conn.commit()
            cursor.close()
            print(f"Table initialized with {embedding_dimension} dimensions")

        except psycopg2.Error as error:
            print(f"Error executing command: {error}")
            conn.rollback()
