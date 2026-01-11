from fastapi import FastAPI
from app.config import settings

app = FastAPI(
    title="MyVault API",
    version="0.1.0"
)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env
    }
