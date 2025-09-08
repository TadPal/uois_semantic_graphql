from dotenv import load_dotenv
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
top_level = os.path.dirname(parent_dir)
sys.path.insert(0, top_level)

from Database.connection import connect_to_postgres
from Database.ChatHistory.initialize_table import initialize_chathistory_table


load_dotenv()
conn = connect_to_postgres(os.environ)

initialize_chathistory_table(conn)

# from get_sessions import get_unique_sessions_by_user_id

# sessions = get_unique_sessions_by_user_id("51d101a0-81f1-44ca-8366-6cf51432e8d6", conn)
# print(sessions[0])
##### DANDA

# from get_messages import get_messages_by_session_id

# x = get_messages_by_session_id("8ef1aab8-b041-45d2-aecb-eb464dac7d44", conn)

# x = x[7][4]

# import json

# x = json.loads(x)
# print("\n\n", x["Response"])

# conn.close()

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
