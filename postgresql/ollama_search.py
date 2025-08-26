import ollama
import psycopg2


def get_embeddings(query: str):

    response = ollama.embeddings(model="mxbai-embed-large", prompt=query)
    return response["embedding"]


def search_index(conn):
    query = "Show me the lessons and their types"

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
