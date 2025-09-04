import requests
from typing import List, Optional
import json
from dotenv import load_dotenv
import os

load_dotenv()
OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN")
OLLAMA_URL = os.getenv("OLLAMA_URL")


def get_ollama_embedding(
    text: str, model: str = "mxbai-embed-large"
) -> Optional[List[float]]:
    """
    Retrieves an embedding for the given text from the Ollama server.

    Args:
        text (str): The text to be embedded.
        model (str): The name of the Ollama model to use. Defaults to "mxbai-embed-large".

    Returns:
        Optional[List[float]]: A list of floats representing the embedding vector,
                               or None if the request fails.
    """
    # Ollama server endpoint for embeddings
    url = f"https://{OLLAMA_URL}/api/embeddings"

    # JSON payload for the request
    payload = json.dumps({"model": model, "prompt": text})
    token = f"Bearer {OLLAMA_TOKEN}"

    try:
        # Send the POST request to the Ollama server
        response = requests.post(
            url,
            data=payload,
            timeout=60,
            headers={"Authorization": token},
        )

        # Raise an HTTPError for bad responses (4xx or 5xx)
        response.raise_for_status()
        # Parse the JSON response
        data = response.json()

        # Return the embedding vector
        embedding = data.get("embedding", [])
        return embedding

    except requests.exceptions.RequestException as e:
        print(f"Error during API request: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None
