from pydantic_settings import BaseSettings



class Settings(BaseSettings):
    app_env: str = "production"
    app_name: str = "myvault"

    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "ap-south-1"
    s3_bucket_name: str

    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str

    reducto_api_key: str
    anthropic_api_key: str

    class Config:
        env_file = ".env"


settings = Settings()

