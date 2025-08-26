import requests
import json

url = "http://localhost:33001/api/gql"
token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiQmVhcmVyIiwiYWNjZXNzX3Rva2VuIjoiQUNDVC1GSkcwWks1VTc5YTJ4M1JtQWhud3ZIdXRzQ2dBSGxlWCIsImV4cGlyZXNfaW4iOjM2MDAsInJlZnJlc2hfdG9rZW4iOiJSRUZULTZjdGhqNVBVYUc1cVlzQUFSMnB4MlJKclZRWEdxamFWIiwidXNlcl9pZCI6IjUxZDEwMWEwLTgxZjEtNDRjYS04MzY2LTZjZjUxNDMyZThkNiJ9.HAteHUkGLPJZfM3k2V130LSOXAkSbAlUAGBjpXqG4_FAMvnqnxBTif-W0dpb26_3NKopbfDQBdffLCmqzEocALHtdGl9oajFxngKXnsPVvyvNtO_8eOt-VyvfxTEvtHu6O7i80gFLn5lfnu2P4c8R3WgDsLdjAIes_T2C1WM1jULCAMPJTfNktJhj4U0HLAmtHTEZOXU_zg0jiAJic_E9Q8pXfBTlLGURiPhnNNzKjrQg3hrHveiBbkuU5zDp8OKbHUWEC3h9dZtK9ctdOlMFgFhHKhuq4ndAaLm90sK99mMZRwQpSoQYCKZqB67XJm_pZ4pPBDQQsekn9Nw4VfepQ"

query = """
query GetServiceSDL {
  _service {
    sdl
  }
}
"""

payload = {"query": query, "operationName": "GetServiceSDL"}

cookie = f"authorization={token}"

headers = {
    "accept": "application/json, multipart/mixed",
    "content-type": "application/json",
    "Cookie": cookie,
}

response = requests.post(url, headers=headers, json=payload)
response.raise_for_status()

data = response.json()
sdl = data["data"]["_service"]["sdl"]

print(sdl.replace("\\n", "\n"))

with open("schema.graphql", "w", encoding="utf-8") as f:
    f.write(sdl.replace("\\n", "\n"))
