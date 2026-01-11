from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
import requests

from app.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
from app.services.vaults import get_or_create_vault
from app.services.artifacts import create_artifact
from app.storage.s3 import upload_file_to_s3, generate_presigned_url
from app.services.reducto import run_reducto_parse

router = APIRouter()

@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()

    from_number = form.get("From")  # whatsapp:+91...
    body = form.get("Body", "").strip()
    num_media = int(form.get("NumMedia", 0))

    phone_number = from_number.replace("whatsapp:", "")
    vault = get_or_create_vault(phone_number)

    # TEXT MESSAGE (e.g. "Hi")
    if num_media == 0:
        return PlainTextResponse(
            "Hey 👋\nSend me any document and I’ll store it safely.",
            media_type="text/xml"
        )

    # MEDIA MESSAGE
    media_url = form.get("MediaUrl0")
    content_type = form.get("MediaContentType0")

    media_resp = requests.get(
        media_url,
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    )

    file_bytes = media_resp.content
    filename = media_url.split("/")[-1]

    # Store raw file
    s3_obj = upload_file_to_s3(
        file_bytes=file_bytes,
        vault_id=vault["vault_id"],
        filename=filename,
        content_type=content_type
    )

    artifact = create_artifact(
        vault_id=vault["vault_id"],
        s3_bucket=s3_obj["bucket"],
        s3_key=s3_obj["key"],
        file_name=filename,
        file_type=content_type,
        file_size=len(file_bytes)
    )

    # Feed to Reducto (async-style, no blocking logic here)
    presigned_url = generate_presigned_url(s3_obj["key"])
    run_reducto_parse(
        artifact_id=artifact["artifact_id"],
        document_url=presigned_url
    )

    return PlainTextResponse(
        "✅ Stored securely. Processing has started.",
        media_type="text/xml"
    )
