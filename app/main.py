import os
import uuid
import hashlib
import requests
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from supabase import create_client
from datetime import datetime

# =========================
# ENV
# =========================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

REDUCTO_API_KEY = os.getenv("REDUCTO_API_KEY")

# =========================
# CLIENTS
# =========================
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

import boto3
s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

app = FastAPI()


# =========================
# HELPERS
# =========================
def normalize_phone(phone: str) -> str:
    return phone.replace("whatsapp:", "").strip()


def vault_id_from_phone(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()


def get_or_create_vault(phone: str):
    vault_id = vault_id_from_phone(phone)

    existing = (
        supabase.table("vaults")
        .select("*")
        .eq("vault_id", vault_id)
        .execute()
        .data
    )

    if existing:
        return existing[0]

    vault = {
        "vault_id": vault_id,
        "phone_number": phone,
        "created_at": datetime.utcnow().isoformat(),
    }

    supabase.table("vaults").insert(vault).execute()
    return vault


def upload_to_s3(file_bytes: bytes, key: str, content_type: str):
    s3.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )


def call_reducto(s3_url: str):
    headers = {
        "Authorization": f"Bearer {REDUCTO_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "input": s3_url,
    }

    r = requests.post(
        "https://platform.reducto.ai/parse",
        headers=headers,
        json=payload,
        timeout=60,
    )

    r.raise_for_status()
    return r.json()


# =========================
# ROUTES
# =========================
@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    msg = MessagingResponse()

    from_number = normalize_phone(form.get("From", ""))
    body = (form.get("Body") or "").strip()
    num_media = int(form.get("NumMedia", 0))

    # 🔒 ONE USER = ONE VAULT (PHONE-BASED)
    vault = get_or_create_vault(from_number)

    # =========================
    # TEXT ONLY
    # =========================
    if num_media == 0:
        reply = (
            "👋 Hey! I’m MyVault.\n\n"
            "Send me any document (PDF, image, etc).\n"
            "I’ll store it safely and make it searchable."
        )
        msg.message(reply)
        return Response(content=str(msg), media_type="application/xml")

    # =========================
    # MEDIA HANDLING
    # =========================
    media_url = form.get("MediaUrl0")
    media_type = form.get("MediaContentType0")

    # Download file from Twilio
    file_resp = requests.get(media_url)
    file_resp.raise_for_status()
    file_bytes = file_resp.content

    artifact_id = str(uuid.uuid4())
    s3_key = f"{vault['vault_id']}/{artifact_id}"

    upload_to_s3(file_bytes, s3_key, media_type)

    s3_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"

    # Store raw artifact
    supabase.table("artifacts").insert(
        {
            "artifact_id": artifact_id,
            "vault_id": vault["vault_id"],
            "s3_bucket": S3_BUCKET_NAME,
            "s3_key": s3_key,
            "file_type": media_type,
            "created_at": datetime.utcnow().isoformat(),
        }
    ).execute()

    # 🔁 REDUCTO
    try:
        reducto_output = call_reducto(s3_url)

        # 1️⃣ raw response
        supabase.table("processing_jobs").insert(
            {
                "artifact_id": artifact_id,
                "raw_response": reducto_output,
                "created_at": datetime.utcnow().isoformat(),
            }
        ).execute()

        # 2️⃣ chunks
        for i, chunk in enumerate(reducto_output.get("result", {}).get("chunks", [])):
            supabase.table("structured_chunks").insert(
                {
                    "artifact_id": artifact_id,
                    "chunk_index": i,
                    "content": chunk.get("content"),
                    "blocks": chunk.get("blocks"),
                }
            ).execute()

        # 3️⃣ searchable text (flattened)
        searchable = " ".join(
            c.get("content", "")
            for c in reducto_output.get("result", {}).get("chunks", [])
        )

        supabase.table("search_index").insert(
            {
                "artifact_id": artifact_id,
                "vault_id": vault["vault_id"],
                "searchable_text": searchable,
            }
        ).execute()

        msg.message("✅ Document saved and indexed.")

    except Exception as e:
        msg.message("⚠️ Saved file, but processing failed. We’ll retry.")

    return Response(content=str(msg), media_type="application/xml")
