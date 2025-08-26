import json
import os
from dotenv import load_dotenv, dotenv_values

load_dotenv()

env = {
    "DBNAME": os.environ.get("DBNAME"),
    "DBUSERNAME": os.environ.get("DBUSERNAME"),
    "DBPASS": os.environ.get("DBPASS"),
    "DBHOSTNAME": os.environ.get("DBHOSTNAME"),
    "DBPORT": os.environ.get("DBPORT"),
    "TOKEN": os.environ.get("TOKEN"),
}

token = env["TOKEN"]
gql_url = "http://localhost:33001/api/gql"


def init_db(extracted_types):
    from postgresql.initialize_table import initialize_embedding_table
    from postgresql.ollama_embed_gql import generate_embedding

    # 1. If table doesn't exist initialize it
    initialize_embedding_table(conn=connection)

    # 2. Generate embeddings and fill pgvector table
    generate_embedding(conn=connection, types=extracted_types)


def extract_schema(token, url):

    from sdl.sdl_parser import extractor as parser
    from sdl.sdl_extract_object import extractor
    from sdl.sdl_fetch import fetch_sdl

    # 1. Fetch sdl from graphql
    schema = fetch_sdl(token=token, url=gql_url)

    # 2. Parse schema
    #     {
    #       "types": [
    #       {
    #           "name": "AcClassificationGQLModel",
    #           "kind": "OBJECT",
    #           "description": "Entity which holds a exam result for a subject semester and user / student",
    #           "fields": [
    #                {
    #                   "attribute": "id",
    #                   "description": "Entity primary key"
    #                }, ...

    parsed = parser(schema)

    # 3. Extracted desired format
    # [
    #     {
    #     "name": "AcClassificationGQLModel",
    #     "description": "Entity which holds a exam result for a subject semester and user / student"
    #     },
    #     {
    #     "name": "AcClassificationLevelGQLModel",
    #     "description": "Mark which student could get as an exam evaluation"
    #     },
    #     {
    #     "name": "AcClassificationTypeGQLModel",
    #     "description": "Classification at the end of semester"
    #     }, ...
    # ]

    extracted_types = extractor(parsed["types"])

    return extracted_types


if __name__ == "__main__":

    # extrated_types = extract_schema(token, gql_url)

    # Connect to pgvector and handle connection
    from postgresql.connection import connect_to_postgres
    from postgresql.ollama_search import search_index

    connection = connect_to_postgres(env=env)

    if connection:
        # init_db(extracted_types)
        search_index(conn=connection)
        connection.close()

    # with open("schema.graphql", "w", encoding="utf-8") as f:
    #     f.write(schema)

    # with open("json\\sld_parsed.json", "w", encoding="utf-8") as f:
    #     f.write(json.dumps(parsed, indent=2, ensure_ascii=False))

    # with open("json\\sld_extracted.json", "w", encoding="utf-8") as f:
    #     f.write(json.dumps(extracted_types, indent=2, ensure_ascii=False))
