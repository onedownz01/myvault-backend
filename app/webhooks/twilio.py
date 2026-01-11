from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
import requests

router = APIRouter()

@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()

    from_number = form.get("From")  # e.g. 'whatsapp:+9183xxxxxxx'
    body = form.get("Body", "").strip()
    num_media = int(form.get("NumMedia", 0))

    # Normalize phone number
    phone_number = from_number.replace("whatsapp:", "")

    # CASE 1: Just text (e.g. "Hi")
    if num_media == 0:
        return PlainTextResponse(
            f"Hey 👋 I’ve got you.\nSend me a document and I’ll store it safely.",
            media_type="text/xml"
        )

    # CASE 2: Media received (handled next)
    return PlainTextResponse(
        "📄 Got your document. Processing and storing it securely.",
        media_type="text/xml"
    )
