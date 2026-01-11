import os
import uuid
import requests
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import Response

from supabase import create_client
import boto3
from twilio.twiml.messaging_response import MessagingResponse

# --------------------
# ENV
# --------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")

REDUCTO_API_KEY = os.getenv("REDUCTO_API_KEY")

# --------------------
# CLIENTS
# --------------------
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

app = FastAPI()

# --------------------
# HELPERS
# --------------------
def get_or_create_vault(phone: str):
    res = supabase.table("vaults").select("*").eq("phone_number", phone).execute()
    if res.data:
        return res.data[0]

    vault = {
        "vault_id": str(uuid.uuid4()),
        "phone_number": phone,
        "created_at": datetime.utcnow().isoformat(),
    }
    supabase.table("vaults").insert(vault).execute()
    return vault


def download_twilio_media(url: str):
    r = requests.get(url, auth=(TWILIO_SID, TWILIO_TOKEN))
    r.raise_for_status()
    return r.content


def upload_to_s3(vault_id: str, artifact_id: str, filename: str, content: bytes):
    key = f"vaults/{vault_id}/raw/{artifact_id}/{filename}"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=content,
        ContentType="application/octet-stream",
    )
    return key


def call_reducto(presigned_url: str):
    headers = {
        "Authorization": f"Bearer {REDUCTO_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"input": presigned_url}
    r = requests.post(
        "https://platform.reducto.ai/parse",
        headers=headers,
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


# --------------------
# WEBHOOK
# --------------------
@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    resp = MessagingResponse()

    from_number = form.get("From")  # whatsapp:+91...
    phone = from_number.replace("whatsapp:", "")

    vault = get_or_create_vault(phone)

    num_media = int(form.get("NumMedia", 0))

    # ---------------- TEXT ONLY ----------------
    if num_media == 0:
        resp.message(
            "👋 Hey! MyVault is live.\n\n"
            "Send me any document (PDF / image) and I’ll store it safely."
        )
        return Response(str(resp), media_type="application/xml")

    # ---------------- MEDIA INGESTION ----------------
    media_url = form.get("MediaUrl0")
    content_type = form.get("MediaContentType0", "")
    filename = f"upload_{datetime.utcnow().timestamp()}"

    if "pdf" in content_type:
        filename += ".pdf"
    elif "image" in content_type:
        filename += ".jpg"

    artifact_id = str(uuid.uuid4())

    # 1. Download file
    file_bytes = download_twilio_media(media_url)

    # 2. Upload raw to S3
    s3_key = upload_to_s3(vault["vault_id"], artifact_id, filename, file_bytes)

    # 3. Register artifact
    artifact = {
        "artifact_id": artifact_id,
        "vault_id": vault["vault_id"],
        "s3_bucket": S3_BUCKET,
        "s3_key": s3_key,
        "file_name": filename,
        "file_type": content_type,
        "file_size_bytes": len(file_bytes),
        "uploaded_at": datetime.utcnow().isoformat(),
        "uploaded_via": "whatsapp",
    }
    supabase.table("artifacts").insert(artifact).execute()

    # 4. Presigned URL
    presigned = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": s3_key},
        ExpiresIn=3600,
    )

    # 5. Send to Reducto
    reducto_result = call_reducto(presigned)

    job = {
        "job_id": str(uuid.uuid4()),
        "artifact_id": artifact_id,
        "status": "completed",
        "raw_response": reducto_result,
        "created_at": datetime.utcnow().isoformat(),
    }
    supabase.table("processing_jobs").insert(job).execute()

    # 6. Store chunks
    chunks = reducto_result.get("result", {}).get("chunks", [])
    for idx, chunk in enumerate(chunks):
        supabase.table("structured_chunks").insert(
            {
                "chunk_id": str(uuid.uuid4()),
                "artifact_id": artifact_id,
                "job_id": job["job_id"],
                "chunk_index": idx,
                "content": chunk.get("content", ""),
                "blocks": chunk.get("blocks", {}),
            }
        ).execute()

    resp.message("📄 Document saved. Processing & indexing started.")
    return Response(str(resp), media_type="application/xml")
