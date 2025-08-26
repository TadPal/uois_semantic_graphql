import requests


def fetch_sdl(token: str, url: str):
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

    return sdl.replace("\\n, ", "\n")
