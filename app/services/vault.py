from app.db import supabase

def get_or_create_vault(phone_number: str):
    res = supabase.table("vaults") \
        .select("*") \
        .eq("phone_number", phone_number) \
        .execute()

    if res.data:
        return res.data[0]

    # Create vault if not exists
    created = supabase.table("vaults").insert({
        "phone_number": phone_number
    }).execute()

    return created.data[0]
