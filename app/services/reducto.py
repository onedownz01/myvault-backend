import requests
from app.config import REDUCTO_API_KEY

def run_reducto_parse(artifact_id: str, document_url: str):
    response = requests.post(
        "https://platform.reducto.ai/parse",
        headers={
            "Authorization": f"Bearer {REDUCTO_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "input": document_url
        }
    )

    return response.json()
