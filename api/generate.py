"""HTTP wrapper around radon_report.py.

The report logic is untouched. This file only takes two uploaded files,
hands them to the existing functions, and returns the finished PDF plus
the parsed numbers so the web app can store them.
"""
import base64
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile

import radon_report as rr

app = FastAPI(title="Report Desk generator")

SHARED_SECRET = os.environ.get("REPORT_SERVICE_SECRET", "")

# radon_report keeps branding in a module-level dict, so swap it per request
# under a lock rather than letting two firms' reports cross.
_BRANDING_LOCK = threading.Lock()


@contextmanager
def branding(overrides):
    with _BRANDING_LOCK:
        original = dict(rr.COMPANY)
        try:
            # Keep empty strings: "" is how a caller says "draw nothing here",
            # which is what suppresses a fallback logo or licence number.
            rr.COMPANY.update({k: v for k, v in overrides.items() if v is not None})
            yield
        finally:
            rr.COMPANY.clear()
            rr.COMPANY.update(original)


@app.get("/api/health")
def health():
    return {"ok": True}


def _parsed_fields(data, report_number):
    """The parts of the parse the web app stores in the database."""
    return {
        "report_number": report_number,
        "client_name": data.get("client_name"),
        "address_line1": data.get("address_line1"),
        "address_line2": data.get("address_line2"),
        "zip_code": data.get("zip_code"),
        "room": data.get("room"),
        "monitor_serial": data.get("monitor_serial_short")
        or data.get("monitor_serial_full"),
        "monitor_model": data.get("monitor_model"),
        "test_started_at": data["start_dt"].isoformat() if data.get("start_dt") else None,
        "test_ended_at": data["end_dt"].isoformat() if data.get("end_dt") else None,
        "duration_hr": data.get("duration_hr"),
        "epa_average": data.get("epa_average"),
        "result": data.get("result"),
        "readings": [
            {"recorded_at": r["dt"].isoformat(), "pci": r["radon"]}
            for r in data.get("readings", [])
        ],
    }


@app.post("/api/generate")
async def generate(
    raw_pdf: UploadFile = File(...),
    house_photo: UploadFile = File(...),
    report_number: str = Form(default=""),
    branding_json: str = Form(default=""),
    logo: Optional[UploadFile] = File(default=None),
    x_service_secret: str = Header(default=""),
):
    if SHARED_SECRET and x_service_secret != SHARED_SECRET:
        raise HTTPException(status_code=401, detail="bad service secret")

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        pdf_path = work / "raw.pdf"
        img_path = work / ("photo" + Path(house_photo.filename or "p.jpg").suffix)
        pdf_path.write_bytes(await raw_pdf.read())
        img_path.write_bytes(await house_photo.read())

        try:
            data = rr.parse_sunradon_pdf(pdf_path)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"could not read the monitor PDF: {e}")

        # Outdoor weather is optional. A failure here must not lose the report.
        try:
            weather = rr.fetch_outdoor_weather(
                data["zip_code"], data["start_dt"], data["end_dt"],
                address_line2=data.get("address_line2"),
            )
        except Exception:
            weather = None

        number = report_number or rr.generate_report_number(data)
        out_path = work / "report.pdf"

        overrides = json.loads(branding_json) if branding_json else {}
        if logo is not None:
            logo_path = work / ("logo" + Path(logo.filename or "l.png").suffix)
            logo_path.write_bytes(await logo.read())
            overrides["logo_path"] = str(logo_path)

        try:
            with branding(overrides):
                rr.build_pdf(data, img_path, out_path, number, pdf_path, weather)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"could not build the report: {e}")

        return {
            **_parsed_fields(data, number),
            "weather_included": weather is not None,
            "pdf_base64": base64.b64encode(out_path.read_bytes()).decode(),
        }
