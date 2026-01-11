from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="MyVault Backend v0")

@app.get("/")
async def root():
    return {"status": "ok", "service": "myvault"}

@app.post("/webhooks/twilio")
async def twilio_webhook():
    """
    Temporary minimal webhook to confirm:
    - App boots
    - Route is reachable
    - Twilio can hit us
    """
    return JSONResponse(
        content={
            "message": "Hey 👋 MyVault is live. Send a document to begin."
        }
    )
