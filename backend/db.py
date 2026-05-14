from pymongo import MongoClient
import os

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://localhost:27017/inventory_db"
)

client = MongoClient(MONGO_URI)

db = client["inventory_intelligence"]

users_collection = db.inventory_intelligence.users
valid_collection = db["teardown_valid_records"]
rejected_collection = db["teardown_rejected_records"]
audit_collection = db["teardown_import_audit"]
warning_collection = db["teardown_warning_records"]
users_collection = db["users"]
