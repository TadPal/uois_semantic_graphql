import psycopg2
from Database.Embedding.embeding import get_ollama_embedding
from Database.connection import connect_to_postgres
import os


def add_embedding_row(GQLquery, user_prompt, conn=None):

    if not conn:
        conn = connect_to_postgres(os.environ)

    """
    Inserts a new row into the graphql_types table.
    """
    command = """
    INSERT INTO graphql_types (question, answer, embedding)
    VALUES (%s, %s, %s);
    """

    # get embedding in float type
    embedding = get_ollama_embedding(user_prompt)
    print("deje se ")
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(command, (user_prompt, GQLquery, embedding))
            conn.commit()
            cursor.close()
            print("Row added successfully.")
        except psycopg2.Error as error:
            print(f"Error adding row: {error}")
            conn.rollback()
