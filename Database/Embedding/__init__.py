from dotenv import load_dotenv
import os

from connection import connect_to_postgres
from initialize_table import initialize_embedding_table
from embeding import get_ollama_embedding
from add_to_db import  add_embedding_row

load_dotenv()
conn = connect_to_postgres(os.environ) 

initialize_embedding_table(conn)




# Testing

answer_query='query {userPage(where: {email: {_endswith: "%.com"}}, skip:0, limit:5){id  name  email} }  '
question=("Give me 5 users wich email ends with .com")

add_embedding_row(conn, question, answer_query)


# Close the connection when done
conn.close()