from sdl.sdl_parser import extractor as parser
from sdl.sdl_extract_object import extractor
from sdl.sdl_fetch import fetch_sdl
import json

token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiQmVhcmVyIiwiYWNjZXNzX3Rva2VuIjoiQUNDVC1GSkcwWks1VTc5YTJ4M1JtQWhud3ZIdXRzQ2dBSGxlWCIsImV4cGlyZXNfaW4iOjM2MDAsInJlZnJlc2hfdG9rZW4iOiJSRUZULTZjdGhqNVBVYUc1cVlzQUFSMnB4MlJKclZRWEdxamFWIiwidXNlcl9pZCI6IjUxZDEwMWEwLTgxZjEtNDRjYS04MzY2LTZjZjUxNDMyZThkNiJ9.HAteHUkGLPJZfM3k2V130LSOXAkSbAlUAGBjpXqG4_FAMvnqnxBTif-W0dpb26_3NKopbfDQBdffLCmqzEocALHtdGl9oajFxngKXnsPVvyvNtO_8eOt-VyvfxTEvtHu6O7i80gFLn5lfnu2P4c8R3WgDsLdjAIes_T2C1WM1jULCAMPJTfNktJhj4U0HLAmtHTEZOXU_zg0jiAJic_E9Q8pXfBTlLGURiPhnNNzKjrQg3hrHveiBbkuU5zDp8OKbHUWEC3h9dZtK9ctdOlMFgFhHKhuq4ndAaLm90sK99mMZRwQpSoQYCKZqB67XJm_pZ4pPBDQQsekn9Nw4VfepQ"
url = "http://localhost:33001/api/gql"

if __name__ == "__main__":
    # 1. Fetch sdl from graphql
    schema = fetch_sdl(token=token, url=url)
    # 2. Parse schema
    parsed = parser(schema)
    # 3. Extracted desired format
    extracted = extractor(parsed["types"])

    with open("schema.graphql", "w", encoding="utf-8") as f:
        f.write(schema)

    with open("json\\sld_parsed.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(parsed, indent=2, ensure_ascii=False))

    with open("json\\sld_extracted.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(extracted, indent=2, ensure_ascii=False))
