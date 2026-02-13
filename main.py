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
    allow_origins=["https://icwi40-p0.myshopify.com"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

DELHIVERY_TOKEN = os.environ.get("DELHIVERY_API_TOKEN", "")
PICKUP_PINCODE = "226002"
PINCODE_API = "https://track.delhivery.com/c/api/pin-codes/json/"
TRANSIT_API = "https://track.delhivery.com/api/v1/json/route/"


class PincodeRequest(BaseModel):
    pincode: str = Field(..., pattern=r"^\d{6}$")


@app.post("/api/check-delivery")
async def check_delivery(req: PincodeRequest):
    if not DELHIVERY_TOKEN:
        raise HTTPException(status_code=500, detail="API token not configured")

    headers = {"Authorization": f"Token {DELHIVERY_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # 1. Serviceability check
            svc_resp = await client.get(PINCODE_API, params={"filter_codes": req.pincode}, headers=headers)
            svc_resp.raise_for_status()
            svc_data = svc_resp.json()

            delivery_codes = svc_data.get("delivery_codes", [])
            if not delivery_codes:
                return {"serviceable": False}

            info = delivery_codes[0].get("postal_code", {})
            if not info.get("pin"):
                return {"serviceable": False}

            cod = info.get("cod", "N") == "Y"
            district = info.get("district", "")
            state_code = info.get("state_code", "")

            # 2. Transit time — Surface & Air (parallel)
            surface_body = {"pickup_pincode": PICKUP_PINCODE, "delivery_pincode": req.pincode, "shipment_mode": "Surface"}
            air_body = {"pickup_pincode": PICKUP_PINCODE, "delivery_pincode": req.pincode, "shipment_mode": "Air"}

            surface_resp = await client.post(TRANSIT_API, json=surface_body, headers=headers)
            air_resp = await client.post(TRANSIT_API, json=air_body, headers=headers)

    except Exception:
        raise HTTPException(status_code=502, detail="Unable to reach Delhivery API")

    now = datetime.now()

    surface_days = int(surface_resp.json().get("estimated_days", 5))
    air_days = int(air_resp.json().get("estimated_days", 2))

    return {
        "serviceable": True,
        "cod_available": cod,
        "district": district,
        "state_code": state_code,
        "surface": {
            "days": surface_days,
            "eta": (now + timedelta(days=surface_days)).strftime("%A, %d %B %Y"),
            "extra_charge": 0,
        },
        "air": {
            "days": air_days,
            "eta": (now + timedelta(days=air_days)).strftime("%A, %d %B %Y"),
            "extra_charge": 30,
        },
    }
