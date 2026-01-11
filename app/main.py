from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
import os
import boto3
import requests
from supabase import create_client
import uuid
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# ENV
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = os.environ["AWS_REGION"]
S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]

REDUCTO_API_KEY = os.environ.get("REDUCTO_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    phone = form.get("From", "").replace("whatsapp:", "")
    body = form.get("Body", "").strip()
    num_media = int(form.get("NumMedia", 0))

    resp = MessagingResponse()

    # --- SAFETY: no phone, no processing
    if not phone:
        resp.message("Something went wrong. Please retry.")
        return Response(content=str(resp), media_type="application/xml")

    # --- FETCH OR CREATE VAULT (STRICT 1:1)
    vault = (
        supabase.table("vaults")
        .select("*")
        .eq("phone_number", phone)
        .execute()
        .data
    )

    if not vault:
        vault = (
            supabase.table("vaults")
            .insert({"phone_number": phone})
            .execute()
            .data
        )

    vault_id = vault[0]["vault_id"]

    # --- TEXT ONLY
    if num_media == 0:
        if body.lower() in ["hi", "hello", "hey"]:
            resp.message("Hey 👋 Send me any document. I’ll store it safely.")
        else:
            resp.message("Send a document (PDF / image) to store it.")
        return Response(content=str(resp), media_type="application/xml")

    # --- MEDIA HANDLING (SAFE)
    media_url = form.get("MediaUrl0")
    content_type = form.get("MediaContentType0", "application/octet-stream")

    if not media_url:
        resp.message("I couldn't read that file. Please resend.")
        return Response(content=str(resp), media_type="application/xml")

    try:
        file_ext = content_type.split("/")[-1]
        file_id = str(uuid.uuid4())
        s3_key = f"{vault_id}/{file_id}.{file_ext}"

        # Download from Twilio
        file_bytes = requests.get(media_url).content

        # Upload raw to S3
        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
        )

        # Store artifact
        artifact = (
            supabase.table("artifacts")
            .insert(
                {
                    "vault_id": vault_id,
                    "s3_bucket": S3_BUCKET_NAME,
                    "s3_key": s3_key,
                    "file_type": file_ext,
                    "file_size_bytes": len(file_bytes),
                    "uploaded_via": "whatsapp",
                }
            )
            .execute()
            .data
        )

        # Fire Reducto async (no blocking)
        if REDUCTO_API_KEY:
            try:
                requests.post(
                    "https://api.reducto.ai/parse",
                    headers={"Authorization": f"Bearer {REDUCTO_API_KEY}"},
                    json={"input": f"s3://{S3_BUCKET_NAME}/{s3_key}"},
                    timeout=2,
                )
            except Exception as e:
                logging.warning(f"Reducto async failed: {e}")

        resp.message("📄 Document saved. Processing & indexing started.")

    except Exception as e:
        logging.exception("MEDIA FLOW FAILED")
        resp.message("Upload failed. Please resend the document.")

    return Response(content=str(resp), media_type="application/xml")
