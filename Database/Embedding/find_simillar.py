import psycopg2
from Database.Embedding.embeding import get_ollama_embedding
from Database.connection import connect_to_postgres
import os
import json


def find_similar_question(
    user_prompt: str, threshold: float = 0.5, conn=None
) -> str | None:
    """
    Finds a similar question in the database and returns its corresponding answer in JSON.

    Args:
        user_prompt (str): The question from the user.
        threshold (float): The similarity threshold (cosine distance) to consider a match.
                        A smaller value indicates a closer match. Default is 0.5.
        conn: An optional database connection object. If None, a new one is created.

    Returns:
        dict | None: JSON with Query + Variables if a similar question is found,
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
            if distance <= threshold:
                print("Match is very similar. Returning answer.")

                return json.dumps(
                    {
                        "Question": db_question,
                        "Query": db_query,
                        "Variables": db_variables,
                    },
                    ensure_ascii=False,
                )

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
