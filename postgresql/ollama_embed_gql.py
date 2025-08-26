import psycopg2
import json
import ollama
import os

MODEL = "mxbai-embed-large"


def generate_embedding(conn, types):
    GRAPHQL_TYPES = types

    def get_embedding(text: str):
        response = ollama.embeddings(model=MODEL, prompt=text)
        return response["embedding"]

    for gql_type in GRAPHQL_TYPES:
        text_to_embed = f"{gql_type['name']}: {gql_type['description']}"
        embedding = get_embedding(text_to_embed)

        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO graphql_types (name, description, embedding)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description, embedding = EXCLUDED.embedding
                """,
                (gql_type["name"], gql_type["description"], embedding),
            )
            conn.commit()
            cur.close()

        except psycopg2.Error as error:
            print(f"Error executing command: {error}")
            conn.rollback()

    print("GraphQL types ingested into pgvector")
