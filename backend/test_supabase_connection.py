
from app.integrations.supabase_client import supabase

response = (
    supabase.table("learners")
    .select("id")
    .limit(1)
    .execute()
)

print("Database query successful!")
print("Rows returned:", len(response.data))
