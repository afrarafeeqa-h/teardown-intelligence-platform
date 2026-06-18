import random
from datetime import datetime, timedelta
from db import users_collection

# In-memory storage (POC only)
otp_store = {}
users = {
    "admin@company.com": "Admin",
    "user@company.com": "User"
}

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp(email: str):
    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=5)

    otp_store[email] = {
        "otp": otp,
        "expires": expiry
    }

    print(f"OTP for {email}: {otp}")  # Mock OTP output
    return otp

def verify_otp(email: str, otp: str):
    record = otp_store.get(email)

    if not record:
        return False

    if record["otp"] != otp:
        return False

    if record["expires"] < datetime.utcnow():
        return False

    return True

def get_user_role(email: str):
    return users.get(email, "User")


from datetime import datetime
from db import users_collection

def get_or_create_user(email: str):
    user = users_collection.find_one({"email": email})

    if not user:
        users_collection.insert_one({
            "email": email,
            "role": "USER",
            "is_active": True,
            "created_at": datetime.utcnow(),
            "last_login": datetime.utcnow()
        })
    else:
        users_collection.update_one(
            {"email": email},
            {"$set": {"last_login": datetime.utcnow()}}
        )

    #IMPORTANT: fetch fresh copy from DB
    user = users_collection.find_one({"email": email})
    return user
