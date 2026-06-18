from pymongo import MongoClient

mongo_client = MongoClient("mongodb://localhost:27017")
db = mongo_client["genai_task"]

users_collection = db["users"]
records_collection = db["records"]
qc_collection = db["qc_results"]
anomaly_collection = db["anomaly_results"]
saved_state_collection = db["saved_state"]
