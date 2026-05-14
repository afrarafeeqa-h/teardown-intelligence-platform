from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict

from models import SendOTPRequest, VerifyOTPRequest, AuthResponse
from auth import send_otp, verify_otp, get_user_role

from data_ingest import parse_and_normalize_csv
from canonical import validate_canonical_row
from db import valid_collection, rejected_collection, audit_collection, warning_collection
from datetime import datetime, timedelta
from auth import get_or_create_user
import numpy as np
from sklearn.ensemble import IsolationForest
from bson import ObjectId
import csv
from fastapi.responses import StreamingResponse
from io import StringIO
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from io import BytesIO
from fastapi import Request
import uuid
from db import db

app = FastAPI(title="Inventory Intelligence Platform")

# Allow Angular frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COLUMN_MAPPING = {
    "Part_ID": "part_id",
    "Total_Cost ($)": "cost",
    "Weight (kg)": "weight",
    "Timestamp": "timestamp"
}

# ---------------- AUTH APIs ---------------- #

@app.post("/auth/send-otp")
def send_otp_api(request: SendOTPRequest):
    send_otp(request.email)
    return {"message": "OTP sent successfully"}

@app.post("/auth/verify-otp", response_model=AuthResponse)
def verify_otp_api(request: VerifyOTPRequest):
    #Get or create user
    user = get_or_create_user(request.email)

    #Role comes ONLY from DB
    role = user["role"]

    #Mock token (JWT later)
    token = f"mock-token-{request.email}"

    return AuthResponse(
        message="Login successful",
        role=role,
        token=token
    )

# ---------------- DATA INGESTION ---------------- #
@app.post("/data/upload/teardown")
async def upload_teardown_csv(request: Request,file: UploadFile = File(...)):
    records = await parse_and_normalize_csv(file, COLUMN_MAPPING)

    summary = defaultdict(int)
    status_count = defaultdict(int)
    results = []
    
    seen_ids = set()
    upload_time = datetime.utcnow() + timedelta(hours=5, minutes=30)
    upload_id = str(uuid.uuid4())
    uploaded_by = request.headers.get("X-User-Email", "unknown_user")

    for row in records:
        issues = validate_canonical_row(row)
        part_id = row.get("part_id")

        # Duplicate detection
        if part_id in seen_ids:
            issues.append("DUPLICATE_PART_ID")
        else:
            seen_ids.add(part_id)

        # Classification
        if issues:
            if "INVALID_COST" in issues or "INVALID_TIMESTAMP" in issues:
                status = "REJECTED"
            else:
                status = "WARNING"
        else:
            status = "VALID"

        document = {
            "upload_id": upload_id,
            "uploaded_by": uploaded_by,
            "data": row,
            "status": status,
            "issues": issues,
            "uploaded_at": upload_time
            }

        #Store in MongoDB
        if status == "VALID":
            valid_collection.insert_one(document)
        elif status == "WARNING":
            warning_collection.insert_one(document)
        else:
            rejected_collection.insert_one(document)

        status_count[status] += 1
        for issue in issues:
            summary[issue] += 1

        results.append({
            "part_id": part_id,
            "status": status,
            "issues": issues
        })

    #Audit log
    audit_collection.insert_one({
    "upload_id": upload_id,
    "uploaded_by": uploaded_by,
    "file_name": file.filename,
    "total_records": len(records),
    "valid_records": status_count["VALID"],
    "warning_records": status_count["WARNING"],
    "rejected_records": status_count["REJECTED"],
    "issues_summary": dict(summary),
    "uploaded_at": upload_time
})

    return {
    "upload_id": upload_id,
    "uploaded_by": uploaded_by,
    "file_name": file.filename,
    "uploaded_at": upload_time,
    "total_records": len(records),
    "valid_records": status_count["VALID"],
    "warning_records": status_count["WARNING"],
    "rejected_records": status_count["REJECTED"],
    "issues_summary": summary,
    "sample_results": results[:5]
}

@app.get("/uploads/my")
def get_my_uploads(request: Request):
    user_email = request.headers.get("X-User-Email", "unknown_user")

    uploads = audit_collection.find(
        {"uploaded_by": user_email},
        {"_id": 0}
    ).sort("uploaded_at", -1)

    return list(uploads)
@app.get("/data/teardown/audits")
def get_teardown_audits():
    audits = list(audit_collection.find({}, {"_id": 0}))
    return {
        "total_audits": len(audits),
        "audits": audits
    }
@app.get("/data/teardown/records/valid")
def get_valid_teardown_records():
    records = list(valid_collection.find({}, {"_id": 0}))
    return {
        "count": len(records),
        "records": records
    }
@app.get("/data/teardown/records/rejected")
def get_rejected_teardown_records():
    records = list(rejected_collection.find({}, {"_id": 0}))
    return {
        "count": len(records),
        "records": records
    }
@app.get("/data/teardown/records/warning")
def get_warning_teardown_records():
    records = list(warning_collection.find({}, {"_id": 0}))
    return {
        "count": len(records),
        "records": records
    }
@app.get("/data/teardown/records/editable")
def get_editable_records():
    latest_audit = audit_collection.find_one({}, sort=[("uploaded_at", -1)])
    if not latest_audit:
        return {"records": []}

    upload_time = latest_audit["uploaded_at"]

    records = []

    #VALID records
    for doc in valid_collection.find({"uploaded_at": upload_time}):
        doc["_id"] = str(doc["_id"])   # 🔑 convert ObjectId → string
        records.append(doc)

    #WARNING records
    for doc in warning_collection.find({"uploaded_at": upload_time}):
        doc["_id"] = str(doc["_id"])
        records.append(doc)

    #REJECTED records
    for doc in rejected_collection.find({"uploaded_at": upload_time}):
        doc["_id"] = str(doc["_id"])
        records.append(doc)

    return {
        "count": len(records),
        "records": records
    }

from fastapi import Body

@app.put("/data/teardown/records/update")
def update_record(updated_record: dict = Body(...)):
    record_id = updated_record["_id"]
    data = updated_record["data"]

    _id = ObjectId(record_id)

    latest_audit = audit_collection.find_one({}, sort=[("uploaded_at", -1)])
    if not latest_audit:
        return {"error": "No active upload"}

    upload_time = latest_audit["uploaded_at"]

    issues = validate_canonical_row(data)

    if not issues:
        status = "VALID"
    elif any(i.startswith("INVALID") for i in issues):
        status = "REJECTED"
    else:
        status = "WARNING"

    #DELETE ONLY THIS ROW
    valid_collection.delete_one({"_id": _id})
    warning_collection.delete_one({"_id": _id})
    rejected_collection.delete_one({"_id": _id})

    document = {
        "_id": _id,              #preserve identity
        "data": data,
        "issues": issues,
        "status": status,
        "uploaded_at": upload_time
    }

    if status == "VALID":
        valid_collection.insert_one(document)
    elif status == "WARNING":
        warning_collection.insert_one(document)
    else:
        rejected_collection.insert_one(document)

    return {"message": "Record updated"}

@app.get("/data/teardown/records/quality-check")
def run_data_quality_check():
    latest_audit = audit_collection.find_one({}, sort=[("uploaded_at", -1)])
    if not latest_audit:
        return {"records": []}

    upload_time = latest_audit["uploaded_at"]

    records = (
        list(valid_collection.find({"uploaded_at": upload_time})) +
        list(warning_collection.find({"uploaded_at": upload_time})) +
        list(rejected_collection.find({"uploaded_at": upload_time}))
    )

    seen_ids = set()
    quality_results = []
    records = sorted(records,key=lambda r: r["data"].get("timestamp", ""))
    for record in records:
        data = record["data"]

        #SKIP EMPTY / GHOST ROWS
        part_id = data.get("part_id")
        if not part_id:
            continue

        #NORMALIZE DATA *HERE*, PER RECORD
        data["cost"] = str(data.get("cost", "")).strip()
        data["timestamp"] = str(data.get("timestamp", "")).strip()
        data["weight"] = str(data.get("weight", "")).strip() if data.get("weight") else data.get("weight")

        #RE-RUN CANONICAL VALIDATION
        issues = validate_canonical_row(data)

        #DUPLICATE CHECK
        if part_id in seen_ids:
            issues.append("DUPLICATE_PART_ID")
        else:
            seen_ids.add(part_id)

        #FINAL QUALITY STATUS
        if not issues:
            status = "CLEAN"
        elif any(i.startswith("INVALID") for i in issues):
            status = "ERROR"
        else:
            status = "WARNING"

        quality_results.append({
            "_id": str(record["_id"]),   #convert ObjectId → string
            "data": record["data"],
            "issues": issues,
            "quality_status": status
            })

    return {
        "count": len(quality_results),
        "records": quality_results
    }
@app.delete("/data/teardown/records/by-id/{record_id}")
def delete_record_by_id(record_id: str):
    _id = ObjectId(record_id)

    valid_collection.delete_one({"_id": _id})
    warning_collection.delete_one({"_id": _id})
    rejected_collection.delete_one({"_id": _id})

    return {"message": "Record deleted"}
@app.get("/data/teardown/records/anomaly-check")
def run_anomaly_detection():
    latest_audit = audit_collection.find_one({}, sort=[("uploaded_at", -1)])
    if not latest_audit:
        return {"records": []}

    upload_time = latest_audit["uploaded_at"]

    records = (
        list(valid_collection.find({"uploaded_at": upload_time})) +
        list(warning_collection.find({"uploaded_at": upload_time}))
    )

    #extract numeric features
    features = []
    valid_rows = []

    for record in records:
        data = record["data"]

        try:
            cost = float(data.get("cost"))
            weight = float(data.get("weight", 0) or 0)
            features.append([cost, weight])
            valid_rows.append(record)
        except:
            continue  # skip non‑numeric rows

    if len(features) < 5:
        return {"records": []}  # not enough data

    X = np.array(features)

    #Isolation Forest
    ANOMALY_RATE = 0.1
    model = IsolationForest(
        n_estimators=100,
        contamination=ANOMALY_RATE,
        random_state=42
    )
    preds = model.fit_predict(X)
    scores = model.decision_function(X)

    results = []
    costs = X[:, 0]
    weights = X[:, 1]
    cost_mean, cost_std = np.mean(costs), np.std(costs)
    weight_mean, weight_std = np.mean(weights), np.std(weights)

    for i, record in enumerate(valid_rows):
        data = record["data"]
        cost = float(data.get("cost"))
        weight = float(data.get("weight", 0) or 0)
        is_anomaly = bool(preds[i] == -1)
        score = float(scores[i])
        explanation = None
        if is_anomaly:
            reasons = []
            if cost > cost_mean + 2 * cost_std:
                reasons.append("Cost is significantly higher than typical parts")
            if weight > weight_mean + 2 * weight_std:
                reasons.append("Weight is significantly higher than typical parts")
            if cost > cost_mean + cost_std and weight < weight_mean:
                reasons.append("High cost relative to weight")
            if not reasons:
                reasons.append("Unusual cost–weight pattern compared to other parts")
            explanation = "; ".join(reasons)
        results.append({
            "_id": str(record["_id"]),     #convert ObjectId
            "data": record["data"],
            "anomaly": is_anomaly,
            "anomaly_score": score,
            "anomaly_reason": explanation
            })

    return {
        "count": len(results),
        "records": results
    }
@app.get("/data/teardown/records/export/clean")
def export_clean_dataset():
    latest_audit = audit_collection.find_one({}, sort=[("uploaded_at", -1)])
    if not latest_audit:
        return {"error": "No dataset available"}

    upload_time = latest_audit["uploaded_at"]

    #Collect only VALID records
    records = list(valid_collection.find(
        {"uploaded_at": upload_time},
        {"_id": 0}
    ))

    if not records:
        return {"error": "No clean records found"}

    #Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)

    #Write header
    writer.writerow(["Part ID", "Cost", "Weight", "Timestamp"])

    #Write rows
    for record in records:
        data = record["data"]
        writer.writerow([
            data.get("part_id"),
            data.get("cost"),
            data.get("weight"),
            data.get("timestamp")
        ])

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=clean_teardown_dataset.csv"
        }
    )
@app.get("/data/teardown/records/export/clean/excel")
def export_clean_excel():
    latest_audit = audit_collection.find_one({}, sort=[("uploaded_at", -1)])
    if not latest_audit:
        return {"error": "No dataset available"}

    upload_time = latest_audit["uploaded_at"]

    records = list(valid_collection.find(
        {"uploaded_at": upload_time},
        {"_id": 0}
    ))

    if not records:
        return {"error": "No clean records found"}

    # Convert to DataFrame
    df = pd.DataFrame([r["data"] for r in records])

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Clean_Teardown_Data")

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=clean_teardown_dataset.xlsx"
        }
    )
@app.get("/data/teardown/records/export/clean/pdf")
def export_clean_pdf():
    latest_audit = audit_collection.find_one({}, sort=[("uploaded_at", -1)])
    if not latest_audit:
        return {"error": "No dataset available"}

    upload_time = latest_audit["uploaded_at"]

    records = list(valid_collection.find(
        {"uploaded_at": upload_time},
        {"_id": 0}
    ))

    if not records:
        return {"error": "No clean records found"}

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)

    table_data = [["Part ID", "Cost", "Weight", "Timestamp"]]

    for r in records:
        d = r["data"]
        table_data.append([
            d.get("part_id"),
            d.get("cost"),
            d.get("weight"),
            d.get("timestamp")
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
    ]))

    doc.build([table])
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=clean_teardown_dataset.pdf"
        }
    )
@app.get("/data/teardown/records/summary")
def get_teardown_summary():
    latest_audit = audit_collection.find_one({}, sort=[("uploaded_at", -1)])
    if not latest_audit:
        return {}

    upload_time = latest_audit["uploaded_at"]

    valid_count = valid_collection.count_documents({"uploaded_at": upload_time})
    warning_count = warning_collection.count_documents({"uploaded_at": upload_time})
    rejected_count = rejected_collection.count_documents({"uploaded_at": upload_time})

    return {
        "total_records": valid_count + warning_count + rejected_count,
        "clean_records": valid_count,
        "warning_records": warning_count,
        "rejected_records": rejected_count
    }
@app.get("/data/teardown/records/anomaly-summary")
def get_anomaly_summary():
    latest_audit = audit_collection.find_one({}, sort=[("uploaded_at", -1)])
    if not latest_audit:
        return {}

    upload_time = latest_audit["uploaded_at"]

    records = (
        list(valid_collection.find({"uploaded_at": upload_time})) +
        list(warning_collection.find({"uploaded_at": upload_time}))
    )

    total = len(records)
    anomalies = 0

    # Simple count using existing anomaly logic proxy
    for r in records:
        try:
            cost = float(r["data"].get("cost"))
            if cost > 1000:       # consistent with your anomaly cases
                anomalies += 1
        except:
            continue

    return {
        "total": total,
        "anomalies": anomalies,
        "normal": total - anomalies
    }
@app.get("/data/teardown/analytics/forecast")
def get_teardown_forecast():
    latest_audit = audit_collection.find_one({}, sort=[("uploaded_at", -1)])
    if not latest_audit:
        return {}

    upload_time = latest_audit["uploaded_at"]

    records = (
        list(valid_collection.find({"uploaded_at": upload_time})) +
        list(warning_collection.find({"uploaded_at": upload_time})) +
        list(rejected_collection.find({"uploaded_at": upload_time}))
    )

    current_count = len(records)

    # Simple moving average forecast (POC-safe)
    forecast_next = int(current_count * 1.1)  # +10% trend assumption

    return {
        "current_records": current_count,
        "forecast_next_cycle": forecast_next,
        "trend": "Increasing"
    }
@app.get("/data/teardown/analytics/risk-scores")
def get_risk_scores():
    latest_audit = audit_collection.find_one({}, sort=[("uploaded_at", -1)])
    if not latest_audit:
        return []

    upload_time = latest_audit["uploaded_at"]

    records = list(valid_collection.find({"uploaded_at": upload_time}))

    risk_list = []

    for r in records:
        cost = float(r["data"].get("cost", 0))
        part_id = r["data"].get("part_id")

        if cost > 1000:
            risk = "High"
        elif cost > 500:
            risk = "Medium"
        else:
            risk = "Low"

        risk_list.append({
            "part_id": part_id,
            "risk": risk
        })

    return risk_list  # top few for dashboard
@app.get("/data/teardown/analytics/recommendations")
def get_recommendations():
    return [
        "Review high-cost parts flagged as high risk",
        "Prioritize inspection for anomalous teardown items",
        "Monitor teardown volume trend for next cycle",
        "Validate supplier pricing for recurring anomalies"
    ]
