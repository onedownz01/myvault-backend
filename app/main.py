from fastapi import FastAPI
from app.storage.s3 import s3_health_check

app = FastAPI(
    title="MyVault Backend",
    version="0.1.0"
)

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "myvault-backend"
    }

@app.get("/health")
def health():
    return {
        "status": "ok"
    }

@app.get("/health/s3")
def health_s3():
    try:
        s3_health_check()
        return {
            "status": "ok",
            "s3": "connected"
        }
    except Exception as e:
        return {
            "status": "error",
            "s3": "failed",
            "error": str(e)
        }
