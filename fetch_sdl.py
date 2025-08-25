import requests
import json

url = "http://localhost:33001/api/gql"
token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiQmVhcmVyIiwiYWNjZXNzX3Rva2VuIjoiQUNDVC1DZng1cUlxeUZLSG9MdnhTMnZoaGlrbFZQdlB5NXRUQSIsImV4cGlyZXNfaW4iOjM2MDAsInJlZnJlc2hfdG9rZW4iOiJSRUZULTFEWjJzWXh4dkV2OEplUUVTRGVGbjJ2dHhYQjd2bkxMIiwidXNlcl9pZCI6IjUxZDEwMWEwLTgxZjEtNDRjYS04MzY2LTZjZjUxNDMyZThkNiJ9.N_TECmfU0yllOgnMsLpRRMefN3x8XLVjMMXVF9DmfFH_GMj005K-SsRYzPnFxxbuat20IW2RhZ2q8hYHw3CqahFJ_gF20u7XszcGtda86H4CU4-22-DBO4aHPTXXOsrIrmQNzKHFRz0NNF0Gdn-C1BmJvhIPSQ-nSZ7x14nhTUYBW76ArUzyegElcvrmWKB50O4YAae4DmZNwM88ziulJ0lVA1NwI_Hq3R6BOwe4WirAY9ZqUx-oLJAt4R4Ggop8FLaG45JibkVwGp6WNvpu1EjzzPp3yqzClrHuO3yFFtWyWWkykrQDEM4dWJnLuCRJq82fWZZauPay8mFnrwMaFQ"

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
