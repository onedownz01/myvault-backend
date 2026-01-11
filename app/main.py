from fastapi import FastAPI

app = FastAPI(title="MyVault API")

@app.get("/health")
def health():
    return {"status": "ok"}
