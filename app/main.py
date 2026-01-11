from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse

app = FastAPI(title="MyVault v0")

# -------------------------
# Health / sanity check
# -------------------------
@app.get("/")
async def root():
    return {"status": "ok"}

# -------------------------
# WhatsApp Webhook (Twilio)
# -------------------------
@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()

    from_number = form.get("From", "")
    body = (form.get("Body") or "").strip()

    resp = MessagingResponse()

    # v0: simple reply to confirm loop works
    resp.message(
        "👋 Hey! MyVault is live.\n\n"
        "Send me any document (PDF / image) and I’ll store it safely."
    )

    return Response(
        content=str(resp),
        media_type="application/xml"
    )
