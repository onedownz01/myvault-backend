from fastapi import FastAPI, Request
from twilio.twiml.messaging_response import MessagingResponse
import requests
import os
import uuid

app = FastAPI()

@app.post("/webhooks/twilio")
async def twilio_webhook(request: Request):
    form = await request.form()
    resp = MessagingResponse()

    from_number = form.get("From")
    body = form.get("Body")
    num_media = int(form.get("NumMedia", 0))

    # TEXT MESSAGE
    if num_media == 0 and body:
        resp.message(
            "👋 Hey! MyVault is live.\n\n"
            "Send me any document (PDF / image) and I’ll store it safely."
        )
        return str(resp)

    # MEDIA MESSAGE
    if num_media > 0:
        media_url = form.get("MediaUrl0")
        media_type = form.get("MediaContentType0")

        file_id = str(uuid.uuid4())
        local_path = f"/tmp/{file_id}"

        r = requests.get(
            media_url,
            auth=(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        )

        with open(local_path, "wb") as f:
            f.write(r.content)

        # RAW STORAGE DONE HERE (S3 later)
        resp.message(
            "📄 Document received.\n\n"
            "Stored securely. Processing will begin shortly."
        )

        return str(resp)

    resp.message("Something went wrong.")
    return str(resp)
