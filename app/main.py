from fastapi import FastAPI
from app.webhooks.twilio import router as twilio_router

app = FastAPI(title="MyVault")

app.include_router(twilio_router)

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "ok"}
