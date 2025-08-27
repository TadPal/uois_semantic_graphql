import json
import os
from dotenv import load_dotenv, dotenv_values

load_dotenv()


def extract_schema(env):

    from SDL.sdl_parser import extractor as sql_parser
    from SDL.sdl_extract_object import extractor as sdl_types_extractor
    from SDL.sdl_fetch import fetch_sdl

    # 1. Fetch sdl from graphql
    schema = fetch_sdl(token=env["token"], url=env["GQL_API_URL"])

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

    parsed = sql_parser(schema)["types"]

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

    extracted_types = sdl_types_extractor(parsed)

    ###########################################
    #            SAVE TO FILES                #
    ###########################################

    # with open("schema.graphql", "w", encoding="utf-8") as f:
    #     f.write(schema)

    # with open("json\\sld_parsed.json", "w", encoding="utf-8") as f:
    #     f.write(json.dumps(parsed, indent=2, ensure_ascii=False))

    # with open("json\\sld_extracted.json", "w", encoding="utf-8") as f:
    #     f.write(json.dumps(extracted_types, indent=2, ensure_ascii=False))

    return extracted_types


def init_db(env):
    from Database.initialize_table import initialize_embedding_table
    from Database.ollama_embed_gql import generate_embedding

    extracted_types = extract_schema(env)

    # 1. If table doesn't exist initialize it
    initialize_embedding_table(conn=connection)

    # 2. Generate embeddings and fill pgvector table
    generate_embedding(conn=connection, types=extracted_types)


if __name__ == "__main__":
    ###########################################
    #               VARIABLES                 #
    ###########################################

    env = {
        "DBNAME": os.environ.get("DBNAME"),
        "DBUSERNAME": os.environ.get("DBUSERNAME"),
        "DBPASS": os.environ.get("DBPASS"),
        "DBHOSTNAME": os.environ.get("DBHOSTNAME"),
        "DBPORT": os.environ.get("DBPORT"),
        "TOKEN": os.environ.get("TOKEN"),
        "GQL_API_URL": "http://localhost:33001/api/gql",
    }

    ###########################################
    #               DATABASE                  #
    ###########################################

    # Connect to pgvector and handle connection
    from Database.connection import connect_to_postgres
    from Database.ollama_search import search_index

    connection = connect_to_postgres(env=env)

    if connection:
        # init_db(env)
        search_index(conn=connection)
        connection.close()
