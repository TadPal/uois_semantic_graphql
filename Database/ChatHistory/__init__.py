from dotenv import load_dotenv
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
top_level = os.path.dirname(parent_dir)
sys.path.insert(0, top_level)

from Database.connection import connect_to_postgres
from initialize_table import initialize_chathistory_table


load_dotenv()
conn = connect_to_postgres(os.environ)

initialize_chathistory_table(conn)

conn.close()

# Testing functions for interacting with DB

# from Database.ChatHistory.add_to_db import add_chat_history
# from Database.ChatHistory.get_from_db import load_chat_history

# chat_history = "User: Ahoj CZ!\nAI: Hi CZ! How can I help you today?"

# # Save the sample chat history to the database
# add_chat_history(conn, chat_history, user_id="51d101a0-81f1-44ca-8366-6cf51432e8d6")

# # Load from database
# reponse = load_chat_history(conn,user_id="51d101a0-81f1-44ca-8366-6cf51432e8d6")
# print("reponse",reponse[0]["messages"])

# # Close the connection when done
