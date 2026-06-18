from datetime import datetime

CANONICAL_SCHEMA = {
    "part_id": {"required": True},
    "cost": {"required": True, "type": "number"},
    "weight": {"required": False, "type": "number"},
    "timestamp": {"required": True, "type": "datetime"}
}


def validate_canonical_row(row: dict):
    issues = []
    
#Missing value checks
    if not row.get("part_id"):
        issues.append("MISSING_PART_ID")

    if row.get("cost") is None or str(row.get("cost")).strip() == "":
        issues.append("MISSING_COST")

    if row.get("weight") is None or str(row.get("weight")).strip() == "":
        issues.append("MISSING_WEIGHT")

    if row.get("timestamp") is None or str(row.get("timestamp")).strip() == "":
        issues.append("MISSING_TIMESTAMP")

    #If missing, no need to parse further for that field
    # ---- Part ID ----
    if not row.get("part_id"):
        issues.append("MISSING_PART_ID")

    # ---- Cost ----
    cost = row.get("cost")
    if cost in ("", None):
        issues.append("MISSING_COST")
    else:
        try:
            float(cost)
        except:
            issues.append("INVALID_COST")

    # ---- Timestamp ----
    
    timestamp = row.get("timestamp")
    if isinstance(timestamp, str):
        timestamp = timestamp.strip()

    
    if timestamp in ("", None):
        issues.append("MISSING_TIMESTAMP")
    else:
        try:
            datetime.fromisoformat(timestamp)
        except:
            issues.append("INVALID_TIMESTAMP")

    # ---- Weight (optional but numeric if present) ----
    if "weight" in row:
        weight = row.get("weight")
        if weight not in ("", None):
            try:
                float(weight)
            except:
                issues.append("INVALID_WEIGHT")

    return issues