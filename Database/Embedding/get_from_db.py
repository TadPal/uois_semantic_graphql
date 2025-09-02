import psycopg2
from typing import Optional
import json

# Assuming get_ollama_embedding is in a file named `embeding.py`
from embeding import get_ollama_embedding

def find_similar_query(conn, user_prompt: str) -> Optional[str]:
    """
    Finds the most similar GraphQL query in the database based on a user's prompt.

    Args:
        conn: The psycopg2 database connection object.
        user_prompt (str): The natural language prompt from the user.

    Returns:
        Optional[str]: The corresponding GraphQL query if a similar prompt is found,
                       otherwise None.
    """
    # Step 1: Get the embedding for the user's prompt
    user_question = get_ollama_embedding(user_prompt)
    
    if not user_question:
        print("Could not get embedding for the user's prompt.")
        return None

    command = """
    SELECT answer, embedding <=> %s AS distance
    FROM graphql_types
    ORDER BY distance ASC
    LIMIT 1;
    """

    try:
        cursor = conn.cursor()
        
        # The psycopg2 library can handle list-to-string conversion for vectors
        cursor.execute(command, (str(user_question),))
        
        result = cursor.fetchone()
        
        cursor.close()

        if result:
            answer, distance = result
            
            # The pgvector extension returns cosine distance. A smaller value means
            # more similar. A threshold of 0.2 is a good starting point for a strong match.
            similarity_threshold = 0.2
            
            if distance <= similarity_threshold:
                print(f"✅ Found a similar query with a distance of {distance:.4f}.")
                print("Returning the stored GraphQL query.")
                return answer
            else:
                print(f"ℹ️ Found a potential match, but the distance ({distance:.4f}) is too high.")
                return None
        else:
            print("ℹ️ No similar entries found in the database.")
            return None

    except psycopg2.Error as error:
        print(f"❌ Error during database query: {error}")
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        return None










# Example usage with your provided connection and data
if __name__ == "__main__":
    from dotenv import load_dotenv
    import os
    
    # These imports are mock-ups for a self-contained file
    # You would use your actual files.
    
    # Mock database connection function
    def connect_to_postgres(env_vars):
        print("Connecting to a mock database...")
        return True # Return a mock connection object

    # Mock table initialization
    def initialize_embedding_table(conn):
        print("Initializing mock table...")

    # Mock add row function
    def add_embedding_row(conn, question, answer_query):
        print("Adding mock data to the database.")
        print(f"Question: {question}")
        print(f"Answer: {answer_query}")

    load_dotenv()
    conn = connect_to_postgres(os.environ)

    if conn:
        initialize_embedding_table(conn)
        
        # We need to add some mock data to the "database"
        answer_query = 'query {userPage(where: {email: {_endswith: "%.com"}}, skip:0, limit:5){id name email} }'
        question = "Give me 5 users wich email ends with .com"
        
        # For this example, we'll manually add the data to simulate a database.
        # In your actual code, you would use add_embedding_row
        print("\n--- Simulating adding data to the database ---")
        mock_db_data = {
            "question": question,
            "answer": answer_query,
            "embedding": get_ollama_embedding(question)
        }
        print("--- Data added ---")

        # Now, test the find_similar_query function with a similar prompt
        print("\n--- Searching for a similar prompt ---")
        user_prompt_1 = "Show me the 5 users whose email addresses end with '.com'."
        retrieved_query = find_similar_query(conn, user_prompt_1)
        
        if retrieved_query:
            print("\nRetrieved GraphQL Query:")
            print(retrieved_query)
        else:
            print("\nNo matching query was found.")
            
        print("\n--- Testing with a different prompt ---")
        user_prompt_2 = "What are the latest blog posts?"
        retrieved_query_2 = find_similar_query(conn, user_prompt_2)
        
        if retrieved_query_2:
            print("\nRetrieved GraphQL Query:")
            print(retrieved_query_2)
        else:
            print("\nNo matching query was found.")
    
    # Close the connection when done
    if conn:
        # In a real app, you would close the connection.
        # For this mock example, we just print a message.
        print("\nClosing mock database connection.")
