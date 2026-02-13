# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import httpx
import os
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://icwi40-p0.myshopify.com"],  # Restrict to your Shopify domain in production
    allow_methods=["POST"],
    allow_headers=["*"],
)

DELHIVERY_TOKEN = os.environ.get("DELHIVERY_API_TOKEN", "")
PICKUP_PINCODE = "226002"
DELHIVERY_API_URL = "https://track.delhivery.com/c/api/pin-codes/json/"


class PincodeRequest(BaseModel):
    pincode: str = Field(..., pattern=r"^\d{6}$")


@app.post("/api/check-delivery")
async def check_delivery(req: PincodeRequest):
    if not DELHIVERY_TOKEN:
        raise HTTPException(status_code=500, detail="API token not configured")

    if not re.match(r"^\d{6}$", req.pincode):
        raise HTTPException(status_code=400, detail="Invalid pincode")

    params = {
        "filter_codes": req.pincode,
    }
    headers = {"Authorization": f"Token {DELHIVERY_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(DELHIVERY_API_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to reach Delhivery API")

    delivery_codes = data.get("delivery_codes", [])
    if not delivery_codes:
        return {"serviceable": False}

    info = delivery_codes[0].get("postal_code", {})
    if not info.get("pin"):
        return {"serviceable": False}

    # Extract transit days (pre_paid estimated days)
    transit_days = info.get("estimated_delivery_days", None)
    cod = info.get("cod", "N")
    district = info.get("district", "")
    state_code = info.get("state_code", "")

    if transit_days is None:
        # Fallback: use a default
        transit_days = 7

    delivery_date = datetime.now() + timedelta(days=int(transit_days))

    return {
        "serviceable": True,
        "estimated_days": int(transit_days),
        "delivery_date": delivery_date.strftime("%A, %d %B %Y"),
        "cod_available": cod == "Y",
        "district": district,
        "state_code": state_code,
    }
