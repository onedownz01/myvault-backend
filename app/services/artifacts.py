from app.db import supabase

def create_artifact(
    vault_id: str,
    s3_bucket: str,
    s3_key: str,
    file_name: str,
    file_type: str,
    file_size: int
):
    res = supabase.table("artifacts").insert({
        "vault_id": vault_id,
        "s3_bucket": s3_bucket,
        "s3_key": s3_key,
        "file_name": file_name,
        "file_type": file_type,
        "file_size_bytes": file_size,
        "uploaded_via": "whatsapp"
    }).execute()

    return res.data[0]
