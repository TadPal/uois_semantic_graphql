import psycopg2
import requests
import json
import ollama
import os
from dotenv import load_dotenv, dotenv_values

load_dotenv()

with open("json\\sld_extracted.json", "r") as file:
    data = json.load(file)

# === CONFIG ===
MODEL = "mxbai-embed-large"
GRAPHQL_TYPES = data

# === DB connection ===
conn = psycopg2.connect(
    host=os.getenv("DBHOSTNAME"),
    database=os.getenv("DBNAME"),
    user=os.getenv("DBUSERNAME"),
    password=os.getenv("DBPASS"),
    port=os.getenv("DBPORT"),
)
cur = conn.cursor()


# === Function to call Ollama ===
def get_embedding(text: str):
    response = ollama.embeddings(model=MODEL, prompt=text)
    return response["embedding"]


# === Ingest types ===
for gql_type in GRAPHQL_TYPES:
    text_to_embed = f"{gql_type['name']}: {gql_type['description']}"
    embedding = get_embedding(text_to_embed)

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
conn.close()

print("GraphQL types ingested into pgvector")
