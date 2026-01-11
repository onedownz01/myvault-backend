from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
import os, uuid, logging
import requests
import boto3
from supabase import create_client

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
    body = (form.get("Body") or "").strip()
    num_media = int(form.get("NumMedia", 0))

    resp = MessagingResponse()

    if not phone:
        resp.message("Error. Please retry.")
        return Response(str(resp), media_type="application/xml")

    # 1️⃣ Vault = phone number (strict)
    vault = supabase.table("vaults").select("*").eq("phone_number", phone).execute().data
    if not vault:
        vault = supabase.table("vaults").insert({"phone_number": phone}).execute().data
    vault_id = vault[0]["vault_id"]

    # 2️⃣ Text-only
    if num_media == 0:
        if body.lower() in ["hi", "hello", "hey"]:
            resp.message("Hey 👋 Send me a document to store it safely.")
        else:
            resp.message("Please send a PDF or image document.")
        return Response(str(resp), media_type="application/xml")

    # 3️⃣ Media-safe handling
    media_url = form.get("MediaUrl0")
    content_type = form.get("MediaContentType0", "application/octet-stream")

    if not media_url:
        resp.message("Couldn't read the file. Please resend.")
        return Response(str(resp), media_type="application/xml")

    try:
        file_ext = content_type.split("/")[-1]
        file_id = str(uuid.uuid4())
        s3_key = f"{vault_id}/{file_id}.{file_ext}"

        file_bytes = requests.get(media_url, timeout=10).content

        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
        )

        supabase.table("artifacts").insert({
            "vault_id": vault_id,
            "s3_bucket": S3_BUCKET_NAME,
            "s3_key": s3_key,
            "file_type": file_ext,
            "file_size_bytes": len(file_bytes),
            "uploaded_via": "whatsapp",
        }).execute()

        # Fire-and-forget Reducto
        if REDUCTO_API_KEY:
            try:
                requests.post(
                    "https://api.reducto.ai/parse",
                    headers={"Authorization": f"Bearer {REDUCTO_API_KEY}"},
                    json={"input": f"s3://{S3_BUCKET_NAME}/{s3_key}"},
                    timeout=2,
                )
            except Exception:
                pass

        resp.message("📄 Document saved. Processing started.")

    except Exception as e:
        logging.exception("MEDIA FAILURE")
        resp.message("Upload failed. Please try again.")

    return Response(str(resp), media_type="application/xml")
