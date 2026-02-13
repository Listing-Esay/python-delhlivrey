from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import httpx
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://icwi40-p0.myshopify.com"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

DELHIVERY_TOKEN = os.environ.get("DELHIVERY_API_TOKEN")
PICKUP_PINCODE = "226002"

PINCODE_API = "https://track.delhivery.com/c/api/pin-codes/json/"
TRANSIT_API = "https://track.delhivery.com/api/v1/json/route/"


class PincodeRequest(BaseModel):
    pincode: str = Field(..., pattern=r"^\d{6}$")


@app.post("/api/check-delivery")
async def check_delivery(req: PincodeRequest):

    if not DELHIVERY_TOKEN:
        raise HTTPException(status_code=500, detail="Delhivery API token not configured")

    headers = {
        "Authorization": f"Token {DELHIVERY_TOKEN}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=20) as client:

        # 1️⃣ Serviceability Check
        svc_resp = await client.get(
            PINCODE_API,
            params={"filter_codes": req.pincode},
            headers=headers
        )

        if svc_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Serviceability API failed")

        svc_data = svc_resp.json()
        delivery_codes = svc_data.get("delivery_codes", [])

        if not delivery_codes:
            return {"serviceable": False}

        info = delivery_codes[0].get("postal_code", {})

        cod_available = info.get("cod", "N") == "Y"
        district = info.get("district", "")
        state_code = info.get("state_code", "")

        # 2️⃣ Transit API – Surface
        surface_body = {
            "pickup_pincode": PICKUP_PINCODE,
            "delivery_pincode": req.pincode,
            "service_type": "SURFACE"
        }

        surface_resp = await client.post(
            TRANSIT_API,
            json=surface_body,
            headers=headers
        )

        if surface_resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Transit API not enabled or failed (Surface)"
            )

        surface_data = surface_resp.json()

        surface_days = surface_data.get("data", {}).get("estimated_days")
        if surface_days is None:
            raise HTTPException(
                status_code=502,
                detail="Surface ETA not returned by Delhivery"
            )

        # 3️⃣ Transit API – Air
        air_body = {
            "pickup_pincode": PICKUP_PINCODE,
            "delivery_pincode": req.pincode,
            "service_type": "EXPRESS"
        }

        air_resp = await client.post(
            TRANSIT_API,
            json=air_body,
            headers=headers
        )

        if air_resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail="Transit API not enabled or failed (Air)"
            )

        air_data = air_resp.json()

        air_days = air_data.get("data", {}).get("estimated_days")
        if air_days is None:
            raise HTTPException(
                status_code=502,
                detail="Air ETA not returned by Delhivery"
            )

    now = datetime.now()

    return {
        "serviceable": True,
        "cod_available": cod_available,
        "district": district,
        "state_code": state_code,
        "surface": {
            "days": int(surface_days),
            "eta": (now + timedelta(days=int(surface_days))).strftime("%A, %d %B %Y"),
        },
        "air": {
            "days": int(air_days),
            "eta": (now + timedelta(days=int(air_days))).strftime("%A, %d %B %Y"),
        }
    }
