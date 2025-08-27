import requests


def getToken(
    url: str = "http://localhost:33001/api/gql", username: str = "", password: str = ""
):
    authurl = url.replace("/api/gql", "/oauth/login3")

    # First GET to fetch initial JSON
    resp = requests.get(authurl)
    resp.raise_for_status()
    data = resp.json()

    # Add username & password to payload
    payload = {**data, "username": username, "password": password}

    # POST with payload
    resp = requests.post(authurl, json=payload)
    resp.raise_for_status()
    data = resp.json()

    token = data["token"]
    return token


def fetch_sdl(token: str = "", url: str = "http://localhost:33001/api/gql"):

    if not token:
        token = getToken(
            url, username="john.newbie@world.com", password="john.newbie@world.com"
        )

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
