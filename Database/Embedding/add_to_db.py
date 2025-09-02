import psycopg2
from embeding import get_ollama_embedding

def add_embedding_row(conn, question, answer_query):
    """
    Inserts a new row into the graphql_types table.
    """
    command = """
    INSERT INTO graphql_types (question, answer, embedding)
    VALUES (%s, %s, %s);
    """

    # get embedding in float type
    embedding=get_ollama_embedding(answer_query)
    
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute(command, (question, answer_query, str(embedding)))
            conn.commit()
            cursor.close()
            print("Row added successfully.")
        except psycopg2.Error as error:
            print(f"Error adding row: {error}")
            conn.rollback()