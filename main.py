from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from bson import ObjectId
import csv
from google import genai
import os
import time
from datetime import datetime
from bson import ObjectId
from fastapi import Request

#INIT APP
app = FastAPI(title="Teardown Intelligence System")

#CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
genai_client = genai.Client(api_key="AIzaSyBbdNs8xHevwIOsEbDK5NKph3AGMrE4QaQ")

#DB CONNECTION (keep same DB as your project)
mongodb_client = MongoClient("mongodb://localhost:27017")
db = mongodb_client["genai_task"]
collection = db["records"]   #SINGLE COLLECTION
STYLE_RULES = """
Follow this response format STRICTLY:

1. Start with a short insight (1 line)
2. Mention impact (1 line)
3. Give action/recommendation (1-2 lines)

Rules:
- Maximum 4 lines total
- Use simple business language
- No technical jargon
- Be direct and practical
- Do NOT repeat dataset numbers unless necessary
- Do NOT give long explanations
"""

NO_EXAGGERATION_RULES = """
STRICT DATA ACCURACY RULES:

- Do NOT exaggerate (avoid words like: "significant", "massive", "critical", unless clearly justified)
- Do NOT assume trends beyond given data
- Do NOT infer growth, risk, or impact without evidence
- Use neutral and realistic language
- If data is small or limited, explicitly mention it
- Do NOT overstate risks or conclusions
- Stay strictly aligned with provided values
"""
# ---------------- AUTH APIs (UNCHANGED) ---------------- #

from models import SendOTPRequest, VerifyOTPRequest, AuthResponse
from auth import send_otp, get_or_create_user

@app.post("/auth/send-otp")
def send_otp_api(request: SendOTPRequest):
    send_otp(request.email)
    return {"message": "OTP sent successfully"}

@app.post("/auth/verify-otp", response_model=AuthResponse)
def verify_otp_api(request: VerifyOTPRequest):
    user = get_or_create_user(request.email)
    return AuthResponse(
        message="Login successful",
        role=user["role"],
        token=f"mock-token-{request.email}"
    )

# ---------------- NEW GENERIC UPLOAD ---------------- #

from datetime import datetime

@app.post("/data/upload/teardown")
async def upload_csv(request: Request, file: UploadFile = File(...)):

    #CLEAR OLD DATA
    #collection.delete_many({})

    content = await file.read()
    decoded = content.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)

    upload_time = datetime.now()

    count = 0
    upload_id = str(ObjectId())   #generate unique dataset id
    for row in reader:
        collection.insert_one({
        "upload_id": upload_id,   #ADD THIS
        "data": row,
        "file_name": file.filename,
        "uploaded_at": upload_time,
        "user_email": request.headers.get("X-User-Email")   #ADD THIS
    })
        count += 1

    return {
        "message": "Upload successful",
        "total_records": count,
        "upload_id": upload_id
    }

# ----------------GENERIC FETCH---------------- #

@app.get("/data/teardown/records/editable")
def get_records(upload_id: str):

    records = list(collection.find({"upload_id": upload_id}))

    for r in records:
        r["_id"] = str(r["_id"])

    return {
        "records": records
    }

# ---------------- OPTIONAL: DELETE ROW ---------------- #

@app.delete("/data/teardown/records/by-id/{record_id}")
def delete_record_by_id(record_id: str):
    _id = ObjectId(record_id)
    collection.delete_one({"_id": _id})
    return {"message": "Record deleted"}
@app.get("/data/teardown/records/quality-check")
def run_data_quality_check(upload_id: str):
    #store flag
    db["meta"].update_one(
        {"upload_id": upload_id},
        {"$set": {"qc_done": True}},
        upsert=True
    )
    records = list(collection.find({"upload_id": upload_id}))

    results = []
    seen_rows = set()

    warning_count = 0

    for r in records:
        data = r["data"]
        issues = []

        # Missing values
        for key, value in data.items():
            if value is None or value == "":
                issues.append(f"{key} is missing")

        # Duplicate
        row_tuple = tuple(data.items())
        if row_tuple in seen_rows:
            issues.append("Duplicate row")
        else:
            seen_rows.add(row_tuple)
        
        #NUMERIC CHECK
        for key, value in data.items():
            if any(word in key.lower() for word in ["cost", "price", "weight", "amount"]):
                try:
                    float(value)
                except:
                    issues.append(f"{key} must be numeric")

        #DATE VALIDATION (ADD THIS)
        for key, value in data.items():
            if "date" in key.lower() or "time" in key.lower():
                try:
                    val = str(value).strip()
                    datetime.strptime(val, "%Y-%m-%d")
                except:
                    issues.append(f"{key} must be in YYYY-MM-DD format")
        # If issue present
        status = "CLEAN"
        if issues:
            status = "WARNING"
            warning_count += 1

        results.append({
            "_id": str(r["_id"]),
            "data": data,
            "issues": issues,
            "quality_status": status
        })

    total = len(records)
    clean = total - warning_count
    db["qc_results"].delete_many({"upload_id": upload_id})
    db["qc_results"].insert_many([
        {**r, "upload_id": upload_id} for r in results
    ])
    return {
        "records": results,
        "summary": {
            "total_records": total,
            "clean_records": clean,
            "warning_records": warning_count,
            "rejected_records": 0
        }
    }

@app.get("/data/teardown/records/anomaly-check")
def run_anomaly_detection(upload_id: str):

    #store flag
    db["meta"].update_one(
        {"upload_id": upload_id},
        {"$set": {"anomaly_done": True}},
        upsert=True
    )

    records = list(collection.find({"upload_id": upload_id}))
    results = []

    #STEP 2: detect grouping column
    group_column = detect_group_column(records)

    #STEP 3: group data
    groups = {}

    for r in records:
        data = r["data"]
        group_key = data.get(group_column, "Unknown")
        
        nums = []
        numeric_cols = []
        for k, v in data.items():
            try:
                nums.append(float(v))
                numeric_cols.append(k)
            except:
                continue

        if len(nums) >= 2:
            groups.setdefault(group_key, []).append((r, nums, numeric_cols))

    #STEP 4: run anomaly detection per group
    for group, rows in groups.items():
        numeric_data = [nums for (_, nums, _) in rows]
        valid_rows = [r for (r, _, _) in rows]
        columns_list = [cols for (_, _, cols) in rows]

        data_np = np.array(numeric_data)
        columns = list(valid_rows[0]["data"].keys())
        #compute mean & std per group
        mean = np.mean(data_np, axis=0)
        std = np.std(data_np, axis=0)

        for i, r in enumerate(valid_rows):

            is_anomaly = False
            reasons = []

            normalized = []

            for j in range(len(data_np[i])):
                if std[j] != 0:
                    z = (data_np[i][j] - mean[j]) / std[j]
                else:
                    z = 0
                normalized.append(z)

            normalized = np.array(normalized)

            #score
            score = float(np.linalg.norm(normalized))

            #detect anomaly
            max_dev = 0
            reason_text = None
            for j in range(len(normalized)):
                value = data_np[i][j]
                avg = mean[j]
                z = normalized[j]
                col_name = columns_list[i][j].lower()
                if abs(z) > max_dev:
                    max_dev = abs(z)
                    # detect column type
                    if "weight" in col_name:
                        field = "Weight"
                    elif "cost" in col_name:
                        field = "Cost"
                    else:
                        field = columns[j]
                    if z > 0:
                        reason_text = f"{field} is high compared to other {group} components"
                    else:
                        reason_text = f"{field} is low compared to other {group} components"

            #FINAL DECISION
            if max_dev > 1.5:
                is_anomaly = True
                reasons.append(reason_text)

            results.append({
                "_id": str(r["_id"]),
                "data": r["data"],
                "group_by": group_column,   #which column used
                "group_value": group,       #actual group
                "anomaly": is_anomaly,
                "anomaly_score": round(score, 2),
                "anomaly_reason": ", ".join(reasons) if reasons else None
            })

    #save results
    db["anomaly_results"].delete_many({"upload_id": upload_id})
    db["anomaly_results"].insert_many([
        {**r, "upload_id": upload_id} for r in results
    ])

    return {"records": results}
@app.get("/analytics/anomalies-by-group")
def anomalies_by_group(upload_id: str):

    pipeline = [
        {
            "$match": {
                "upload_id": upload_id,
                "anomaly": True
            }
        },
        {
            "$group": {
                "_id": "$group_value",
                "count": {"$sum": 1}
            }
        }
    ]

    results = list(db["anomaly_results"].aggregate(pipeline))

    return {
        "data": [
            {"group": r["_id"], "count": r["count"]}
            for r in results
        ]
    }
from fastapi.responses import StreamingResponse
from io import StringIO
def calculate_summary(records):
        total = len(records)
        warning_rows = 0
        seen = set()
        for r in records:
            data = r["data"]
            has_issue = False
            
            # Missing values
            for v in data.values():
                if v == "" or v is None:
                    has_issue = True
                    
            # Duplicate rows
            row_tuple = tuple(data.items())
            if row_tuple in seen:
                has_issue = True
            else:
                seen.add(row_tuple)
            # Invalid numeric
            for k, v in data.items():
                if any(word in k.lower() for word in ["cost", "weight", "salary"]):
                    try:
                        float(v)
                    except:
                        has_issue = True
            # Invalid date / timestamp
            from datetime import datetime
            for k, v in data.items():
                if "date" in k.lower() or "time" in k.lower():
                    try:
                        datetime.strptime(str(v).strip(), "%Y-%m-%d")
                    except:
                        has_issue = True
            if has_issue:
                warning_rows += 1
        clean = total - warning_rows
        return {
        "total_records": total,
        "clean_records": clean,
        "warning_records": warning_rows,
        "rejected_records": 0
    }
def get_full_dataset_with_analysis(upload_id: str):

    records = list(collection.find({"upload_id": upload_id}))

    #get QC
    meta = db["meta"].find_one({"upload_id": upload_id}) or {}
    qc_done = meta.get("qc_done", False)
    anomaly_done = meta.get("anomaly_done", False)
    qc = list(db["qc_results"].find({"upload_id": upload_id})) if qc_done else []

    #get anomaly
    anomaly = list(db["anomaly_results"].find({"upload_id": upload_id})) if anomaly_done else []

    qc_map = {r["_id"]: r for r in qc}
    anomaly_map = {r["_id"]: r for r in anomaly}

    final = []

    for r in records:
        _id = str(r["_id"])

        data = r["data"]

        q = qc_map.get(_id, {})
        a = anomaly_map.get(_id, {})

        combined = {
            **data,
            "quality_status": q.get("quality_status") if qc_done else None,
            "issues": ", ".join(q.get("issues", [])) if qc_done else None,
            "anomaly": a.get("anomaly") if anomaly_done else None,
            "anomaly_score": a.get("anomaly_score") if anomaly_done else None,
            "anomaly_reason": a.get("anomaly_reason"),
        }

        final.append(combined)

    return final
@app.get("/data/export/clean")
def export_clean(upload_id: str):

    records = list(collection.find({"upload_id": upload_id}))

    if not records:
        return {"error": "No data"}

    output = StringIO()
    writer = csv.writer(output)

    header = list(records[0]["data"].keys())
    writer.writerow(header)

    for r in records:
        writer.writerow([r["data"][h] for h in header])

    output.seek(0)
    file_name = records[0].get("file_name", "dataset").split('.')[0]
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={file_name}_clean.csv"}
        )
@app.get("/data/export/full/csv")
def export_full_csv(upload_id: str):

    records = get_full_dataset_with_analysis(upload_id)

    if not records:
        return {"error": "No data"}

    output = StringIO()
    writer = csv.writer(output)

    header = list(records[0].keys())
    writer.writerow(header)

    for r in records:
        writer.writerow([r[h] for h in header])

    output.seek(0)
    file_name = collection.find_one({"upload_id": upload_id}).get("file_name", "dataset")
    file_name = file_name.split(".")[0]
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={file_name}_full.csv"}
    )
import pandas as pd
from io import BytesIO
@app.get("/data/export/clean/excel")
def export_clean_excel(upload_id: str):

    records = list(collection.find({"upload_id": upload_id}))

    df = pd.DataFrame([r["data"] for r in records])

    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    buffer.seek(0)
    file_name = records[0].get("file_name", "dataset").split('.')[0]
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={file_name}_clean.xlsx"}
        )
@app.get("/data/export/full/excel")
def export_full_excel(upload_id: str):

    records = get_full_dataset_with_analysis(upload_id)

    df = pd.DataFrame(records)

    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    buffer.seek(0)
    file_name = collection.find_one({"upload_id": upload_id}).get("file_name", "dataset")
    file_name = file_name.split(".")[0]
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={file_name}_analysis.xlsx"}
        )
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A3
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from reportlab.lib.pagesizes import landscape

@app.get("/data/export/clean/pdf")
def export_clean_pdf(upload_id: str):

    records = list(collection.find({"upload_id": upload_id}))
    records = [r["data"] for r in records]
    if not records:
        return {"error": "No data"}

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A3))

    styles = getSampleStyleSheet()

    header = list(records[0].keys())

    #WRAP TEXT
    table_data = []

    # header
    table_data.append([
        Paragraph(f"<b>{str(h)}</b>", styles["Normal"]) for h in header
    ])

    # rows
    for r in records:
        row = []
        for v in r.values():
            text = str(v)
            #truncate long text
            if len(text) > 35:
                text = text[:35] + "..."
            #add to row
            row.append(Paragraph(text, styles["Normal"]))
        table_data.append(row)
    #CREATE TABLE
    table = Table(table_data, repeatRows=1)

    #FIX COLUMN WIDTHS (important)
    col_widths = []
    for h in header:
        #calculate max length of column values
        max_len = len(str(h))
        for r in records[:20]:   #sample first 20 rows (fast)
            val = str(r.get(h, ""))
            if len(val) > max_len:
                max_len = len(val)
        #convert length to width
        if max_len > 40:
            width = 90
        elif max_len > 25:
            width = 75
        elif max_len > 15:
            width = 60
        else:
            width = 50
        col_widths.append(width)
    table._argW = col_widths

    #STYLE (VERY IMPORTANT)
    table.setStyle(TableStyle([
    ('GRID', (0,0), (-1,-1), 0.3, colors.grey),
    ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ('FONTSIZE', (0,0), (-1,-1), 6),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ('WORDWRAP', (0,0), (-1,-1), 'LTR'),
    ('LEFTPADDING', (0,0), (-1,-1), 2),
    ('RIGHTPADDING', (0,0), (-1,-1), 2),
    ('TOPPADDING', (0,0), (-1,-1), 1),
    ('BOTTOMPADDING', (0,0), (-1,-1), 1),
]))
    #OPTIONAL: highlight anomaly rows
    for i, r in enumerate(records, start=1):
        if r.get("anomaly"):
            table.setStyle([
                ('BACKGROUND', (0,i), (-1,i), colors.lightcoral)
            ])
        elif r.get("quality_status") == "WARNING":
            table.setStyle([
                ('BACKGROUND', (0,i), (-1,i), colors.lightyellow)
            ])

    #BUILD PDF
    doc.build([table])
    buffer.seek(0)
    file_name = collection.find_one({"upload_id": upload_id}).get("file_name", "dataset")
    file_name = file_name.split(".")[0]
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={file_name}_clean.pdf"}
        )
@app.get("/data/export/full/pdf")
def export_full_pdf(upload_id: str):

    records = get_full_dataset_with_analysis(upload_id)

    if not records:
        return {"error": "No data"}

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A3))

    styles = getSampleStyleSheet()

    header = list(records[0].keys())

    table_data = []

    table_data.append([
        Paragraph(f"<b>{str(h)}</b>", styles["Normal"]) for h in header
    ])

    for r in records:
        row = []
        for v in r.values():   #IMPORTANT difference
            text = str(v)

            if len(text) > 35:
                text = text[:35] + "..."

            row.append(Paragraph(text, styles["Normal"]))

        table_data.append(row)

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
    ('GRID', (0,0), (-1,-1), 0.3, colors.grey),
    ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ('FONTSIZE', (0,0), (-1,-1), 6),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ('WORDWRAP', (0,0), (-1,-1), 'LTR'),
    ('LEFTPADDING', (0,0), (-1,-1), 2),
    ('RIGHTPADDING', (0,0), (-1,-1), 2),
    ('TOPPADDING', (0,0), (-1,-1), 1),
    ('BOTTOMPADDING', (0,0), (-1,-1), 1),
]))
    # (keep your same width + style block)
    doc.build([table])
    buffer.seek(0)
    file_name = collection.find_one({"upload_id": upload_id}).get("file_name", "dataset")
    file_name = file_name.split(".")[0]
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={file_name}_full.pdf"}
        )
def get_dataset(upload_id):
    return list(collection.find({"upload_id": upload_id}))
@app.get("/genai/insights")
def generate_ai_insights(upload_id: str):

    records = get_dataset(upload_id)

    total = len(records)
    missing_rows = 0
    duplicates = 0
    anomalies = 0
    seen = set()

    for r in records:
        data = r["data"]

        row_tuple = tuple(data.items())
        if row_tuple in seen:
            duplicates += 1
        else:
            seen.add(row_tuple)
        
        if any(v == "" or v is None for v in data.values()):
            missing_rows += 1

        anomalies = db["anomaly_results"].count_documents({
            "upload_id": upload_id,
            "anomaly": True
    })

    prompt = f"""
    Dataset summary:
    - Total records: {total}
    - Records with missing data: {missing_rows}
    - Duplicate records: {duplicates}
    - Anomalies detected: {anomalies}
    
    Provide insights:
    1. Key issues (be specific if possible)
    2. Business impact
    3. Recommended action
    
    IMPORTANT:
    - Do NOT assume all records are affected
    - Use data patterns (if visible) to make insights slightly specific
    - Avoid generic statements like “some records”
    - Be realistic and concise
    {NO_EXAGGERATION_RULES}
    {STYLE_RULES}
    """

    reply = generate_with_retry(prompt)
    return {"reply": reply}
from fastapi import Body
@app.put("/data/update")
def update_record(updated: dict):

    _id = ObjectId(updated["_id"])

    collection.update_one(
        {"_id": _id},
        {"$set": {"data": updated["data"]}}
    )

    return {"message": "updated"}
@app.delete("/data/teardown/records/by-id/{record_id}")
def delete_record_by_id(record_id: str):

    _id = ObjectId(record_id)

    result = collection.delete_one({"_id": _id})

    return {
        "message": "deleted",
        "deleted_count": result.deleted_count
    }
@app.get("/analytics/forecast")
def forecast():
    total = len(list(collection.find()))
    next_val = int(total * 1.1)

    return {
        "current": total,
        "next": next_val
    }
@app.get("/dashboard/summary")
def dashboard_summary(upload_id: str):
    meta = db["meta"].find_one({"upload_id": upload_id}) or {}
    qc_done = meta.get("qc_done", False)
    anomaly_done = meta.get("anomaly_done", False)
    #ONLY READ QC IF DONE
    if qc_done:
        qc_results = list(db["qc_results"].find({"upload_id": upload_id}))
        total = len(qc_results)
        clean = sum(1 for r in qc_results if r["quality_status"] == "CLEAN")
        warning = total - clean
        summary = {
        "total_records": total,
        "clean_records": clean,
        "warning_records": warning,
        "rejected_records": 0
    }
    else:
        summary = {
        "total_records": 0,
        "clean_records": 0,
        "warning_records": 0,
        "rejected_records": 0
    }
    #ANOMALY PART (already fixed)
    if anomaly_done:
        anomaly_count = db["anomaly_results"].count_documents({
        "upload_id": upload_id,
        "anomaly": True
    })
    else:
        anomaly_count = None
    summary["anomalies"] = anomaly_count
    return summary
@app.post("/genai/chat")
def chatbot(request: dict):
    upload_id = request.get("upload_id")
    query = request.get("query")
    records = list(collection.find({"upload_id": upload_id}))

    #send structured dataset (not raw huge text)
    #STEP 1: Extract data
    data = [r["data"] for r in records]
    #STEP 2: CHUNKING
    chunk_size = 100
    chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
    #STEP 3: PROCESS CHUNKS
    total_anomalies = 0
    missing_count = 0
    for chunk in chunks:
        for row in chunk:
            for v in row.values():
                if v == "" or v is None:
                    missing_count += 1
    #STEP 3B: Correct anomaly count (from processed DB)
    total_anomalies = db["anomaly_results"].count_documents({
        "upload_id": upload_id,
        "anomaly": True
})
    #STEP 4: SUMMARY JSON
    context = {
    "total_records": len(data),
    "anomalies": total_anomalies,
    "missing_values": missing_count
}
    #STEP 5: SMALL SAMPLE
    sample = data[:20]

    prompt = f"""
    Dataset summary:
    {context}
    
    Sample records:
    {sample}
    
    User question:
    {query}
    
    Respond intelligently:
    - Use summary for counts
    - Use sample records to identify patterns (columns, values)
    - Give specific answers where possible
    
    IMPORTANT:
    - Do NOT guess beyond data
    - Avoid generic answers
    - Be precise and helpful
    {NO_EXAGGERATION_RULES}
    {STYLE_RULES}
    """

    reply = generate_with_retry(prompt)
    return {"reply": reply}
@app.get("/genai/forecast")
def genai_forecast(upload_id: str):

    records = list(collection.find({"upload_id": upload_id}))
    total = len(records)

    forecast_val = int(total * 1.1)

    prompt = f"""
    Current dataset size: {total}
    Expected size: {forecast_val}
    
    Explain realistically:
    1. What change this represents
    2. Actual impact (small / moderate)
    3. What to do next
    
    IMPORTANT:
    - If change is small, clearly say "small increase"
    - Do NOT suggest large growth unless data supports it
    - Be practical and concise
    {NO_EXAGGERATION_RULES}
    {STYLE_RULES}
    """

    reply = generate_with_retry(prompt)
    return {"reply": reply}
@app.get("/genai/predictive")
def predictive_analysis(upload_id: str):
    records = list(collection.find({"upload_id": upload_id}))
    data = [r["data"] for r in records]
    summary = {
    "total_records": len(data),
    "sample": data[:10]
}
    
    prompt = f"""
    Dataset summary:
    {summary}
    
    Provide insights:
    - Mention specific observations from sample data
    - Avoid generic terms like "variety" unless needed
    - Highlight meaningful patterns
    
    ]
    IMPORTANT:
    - Base insights only on visible data
    - Be specific but safe
    {NO_EXAGGERATION_RULES}
    {STYLE_RULES}
    """

    reply = generate_with_retry(prompt)
    return {"reply": reply}
@app.get("/genai/fix")
def suggest_fixes(upload_id: str):
    records = list(collection.find({"upload_id": upload_id}))
    issues = []
    for r in records:
        data = r["data"]
        for k, v in data.items():
            if v == "" or v is None:
                issues.append(f"{k} missing")
            try:
                if float(v) > 1000:
                    issues.append(f"{k} high value")
            except:
                pass

    prompt = f"""
    Detected issues:
    {issues[:10]}
    
    Provide fixes:
    1. What is wrong
    2. How to fix it
    3. Why it matters
    
    IMPORTANT:
    - Do NOT introduce new issues
    - Base only on detected problems
    - Keep response short and actionable
    {NO_EXAGGERATION_RULES}
    {STYLE_RULES}
    """
    
    reply = generate_with_retry(prompt)

    return {"reply": reply}
import requests
import time
def generate_with_retry(prompt):
    for i in range(3):
        try:
            response = genai_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={"temperature": 0.3}
            )
            return response.text

        except Exception as e:
            print("Retrying due to:", e)
            time.sleep(2)

    return "⚠ AI service busy. Try again."
import numpy as np

#STEP 1: Detect grouping column dynamically
def detect_group_column(records):
    candidate_columns = {}

    for r in records:
        data = r["data"]
        for k, v in data.items():
            if isinstance(v, str) and v.strip() != "":
                candidate_columns.setdefault(k, []).append(v)

    best_col = None
    best_score = -1

    for col, values in candidate_columns.items():
        unique_vals = set(values)
        unique_count = len(unique_vals)
        total = len(values)

        # skip bad candidates
        if unique_count <= 1 or unique_count == total:
            continue

        #SCORING LOGIC (VERY IMPORTANT)
        diversity_ratio = unique_count / total  

        # we want:
        # not too small (like Low/Medium/High)
        # not too large (like IDs)
        score = diversity_ratio

        if 0.05 < diversity_ratio < 0.5:
            if score > best_score:
                best_score = score
                best_col = col

    return best_col
@app.get("/uploads")
def get_uploads(request: Request):
    user_email = request.headers.get("X-User-Email")
    pipeline = [
        {"$match": {"user_email": user_email}},   #FILTER BY USER
        {
            "$group": {
                "_id": "$upload_id",
                "file_name": {"$first": "$file_name"},
                "uploaded_at": {"$first": "$uploaded_at"}
            }
        },
        {
            "$sort": {"uploaded_at": -1}
        }
    ]

    uploads = list(collection.aggregate(pipeline))

    result = []

    for u in uploads:
        upload_id = u["_id"]

        summary = run_data_quality_check(upload_id)["summary"]

        result.append({
            "upload_id": upload_id,
            "file_name": u["file_name"],
            "uploaded_at": u["uploaded_at"].isoformat(),
            "total_records": summary["total_records"],
            "valid_records": summary["clean_records"],
            "warning_records": summary["warning_records"],
            "rejected_records": summary["rejected_records"]
        })

    return result
@app.get("/debug")
def debug():
    records = list(collection.find())

    for r in records:
        r["_id"] = str(r["_id"])   #FIX
    return records
@app.post("/save-state")
def save_state(request: dict):

    upload_id = request.get("upload_id")
    records = request.get("records")

    # store everything
    db["saved_state"].update_one(
        {"upload_id": upload_id},
        {
            "$set": {
                "records": records,
                "saved_at": datetime.now()
            }
        },
        upsert=True
    )
    return {"message": "saved"}
@app.get("/load-state")
def load_state(upload_id: str):

    data = db["saved_state"].find_one({"upload_id": upload_id})

    if not data:
        return {}

    return {
        "records": data.get("records", [])
    }
@app.get("/audit-history")
def audit_history():

    grouped = list(collection.aggregate([
        {
            "$group": {
                "_id": "$upload_id",
                "file_name": {"$first": "$file_name"},
                "uploaded_at": {"$first": "$uploaded_at"},
                "user_email": {"$first": "$user_email"},
                "total": {"$sum": 1}
            }
        },
        {"$sort": {"uploaded_at": -1}}
    ]))

    result = []

    for g in grouped:
        upload_id = g["_id"]

        #GET SUMMARY FROM QC
        summary = run_data_quality_check(upload_id)["summary"]

        result.append({
            "_id": upload_id,
            "upload_id": upload_id,
            "file_name": g["file_name"],
            "uploaded_at": g["uploaded_at"],
            "user_email": g["user_email"],
            "total_records": summary["total_records"],
            "valid_records": summary["clean_records"],
            "warning_records": summary["warning_records"],
            "rejected_records": summary["rejected_records"]
        })

    return result