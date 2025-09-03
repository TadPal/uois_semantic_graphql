from dotenv import load_dotenv

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
top_level = os.path.dirname(parent_dir)
sys.path.insert(0, top_level)

from Database.connection import connect_to_postgres
from Database.Embedding.initialize_table import initialize_embedding_table

load_dotenv()
conn = connect_to_postgres(os.environ)

initialize_embedding_table(conn)
conn.close()

# # Testing
# from add_to_db import add_embedding_row

# answer_query = """query {userPage(where: {email: {_endswith: "%.com"}}, skip:0, limit:5){id  name  email} }"""
# question = "Give me 5 users wich email ends with .com"

# add_embedding_row(conn, question, answer_query)
