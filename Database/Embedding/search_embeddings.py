import ollama
import psycopg2
import os

from Database.connection import connect_to_postgres


def get_embeddings(query: str):

    response = ollama.embeddings(model="mxbai-embed-large", prompt=query)
    return response["embedding"]


def search_index(conn=None):
    if not conn:
        conn = connect_to_postgres(os.environ)

    query = "Show me all planned lessons for this semester"

    embedding = get_embeddings(query=query)

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT name, description
            FROM graphql_types
            ORDER BY embedding <-> %s::vector
            LIMIT 5;
            """,
            (embedding,),
        )
        matches = cur.fetchall()
        print(matches)

    except psycopg2.Error as error:
        print(f"Error executing command: {error}")
    finally:
        cur.close()
        conn.close()
