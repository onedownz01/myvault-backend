from fastapi import FastAPI, Request
from twilio.twiml.messaging_response import MessagingResponse
import requests
import os
import uuid

app = FastAPI()


@app.get("/")
async def health():
    return {"status": "ok"}


# ✅ THIS MUST MATCH TWILIO EXACTLY
@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    resp = MessagingResponse()

    from_number = form.get("From")
    body = form.get("Body", "").strip()
    num_media = int(form.get("NumMedia", 0))

    # ---- TEXT MESSAGE ----
    if num_media == 0 and body:
        resp.message(
            "👋 Hey! MyVault is live.\n\n"
            "Send me any document (PDF / image) and I’ll store it safely."
        )
        return str(resp)

    # ---- MEDIA MESSAGE ----
    if num_media > 0:
        media_url = form.get("MediaUrl0")
        media_type = form.get("MediaContentType0")

        file_id = str(uuid.uuid4())
        tmp_path = f"/tmp/{file_id}"

        r = requests.get(
            media_url,
            auth=(
                os.environ["TWILIO_ACCOUNT_SID"],
                os.environ["TWILIO_AUTH_TOKEN"],
            ),
        )
        r.raise_for_status()

        with open(tmp_path, "wb") as f:
            f.write(r.content)

        # v0 behaviour: RAW storage only (S3 next)
        resp.message(
            "📄 Document received.\n\n"
            "Stored securely. Processing will begin shortly."
        )
        return str(resp)

    resp.message("⚠️ Could not process your message.")
    return str(resp)
