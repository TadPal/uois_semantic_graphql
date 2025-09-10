import psycopg2
from Database.Embedding.embeding import get_ollama_embedding
from Database.connection import connect_to_postgres
import os


def find_similar_question(
    user_prompt: str, threshold: float = 0.5, conn=None
) -> str | None:
    """
    Finds a similar question in the database and returns its corresponding answer.

    Args:
        user_prompt (str): The question from the user.
        threshold (float): The similarity threshold (cosine distance) to consider a match.
                           A smaller value indicates a closer match. Default is 0.5.
        conn: An optional database connection object. If None, a new one is created.

    Returns:
        str | None: The answer from the database if a similar question is found,
                    otherwise None.
    """
    if not conn:
        conn = connect_to_postgres(os.environ)

    if not conn:
        print("Error: Could not connect to the database.")
        return None

    # Get the embedding for the user's question
    try:
        user_embedding = get_ollama_embedding(user_prompt)
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None

    # The SQL query uses the '<=>' operator for cosine distance.
    # It orders by similarity and retrieves the top 1 result.
    # The user_embedding is explicitly cast to the 'vector' type to resolve the type error.
    command_with_distance = """
    SELECT question, query, variables, embedding <=> %s::vector AS distance FROM graphql_types
    ORDER BY distance
    LIMIT 1;
    """

    try:
        cursor = conn.cursor()
        cursor.execute(command_with_distance, (user_embedding,))

        result = cursor.fetchone()

        if result:
            db_question, db_query, db_variables, distance = result

            print(f"Found closest question: '{db_question}' with distance {distance}")

            if distance <= threshold:
                print("Match is very similar. Returning answer.")
                return (db_query, db_variables)
            else:
                print("Closest match is not similar enough. No answer returned.")
        else:
            print("No results found in the database.")

        cursor.close()
        return None

    except psycopg2.Error as error:
        print(f"Database query error: {error}")
        return None
    finally:
        if conn:
            conn.close()


from dotenv import load_dotenv

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
top_level = os.path.dirname(parent_dir)
sys.path.insert(0, top_level)

from Database.connection import connect_to_postgres

load_dotenv()
conn = connect_to_postgres(os.environ)


from Database.Embedding.find_simillar import find_similar_question

test_question = "Dej mi pár uživatelů"

found_answer = find_similar_question(test_question, threshold=0.7, conn=conn)

if found_answer:
    print(f"\nAnswer from DB: {found_answer}")
else:
    print(f"\nNo sufficiently similar question found in the database.")
