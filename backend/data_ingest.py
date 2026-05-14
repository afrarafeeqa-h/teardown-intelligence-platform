import csv
from fastapi import UploadFile, HTTPException

async def parse_and_normalize_csv(file: UploadFile, column_mapping: dict):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files supported")

    content = await file.read()
    decoded = content.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)

    records = []

    for raw_row in reader:
        canonical_row = {}
        for csv_col, canonical_col in column_mapping.items():
            canonical_row[canonical_col] = raw_row.get(csv_col)
        records.append(canonical_row)

    return records
