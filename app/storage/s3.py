import boto3
import uuid
from app.config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    S3_BUCKET_NAME
)

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

def upload_file_to_s3(file_bytes: bytes, vault_id: str, filename: str, content_type: str):
    key = f"vaults/{vault_id}/raw/{uuid.uuid4()}_{filename}"

    s3.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=key,
        Body=file_bytes,
        ContentType=content_type
    )

    return {
        "bucket": S3_BUCKET_NAME,
        "key": key
    }

def generate_presigned_url(key: str, expires_in: int = 3600):
    return s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": S3_BUCKET_NAME,
            "Key": key
        },
        ExpiresIn=expires_in
    )
