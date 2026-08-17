#!/usr/bin/env python3
"""
Radon Report Generator
======================
Drag a raw SunRADON test PDF + a house photo onto the droplet to produce
a branded customer report.

Outputs a 7-page report:
  1. Cover (logo, house photo, client info, RMS, monitor info)
  2. Hourly Graph -- the actual chart image extracted from the raw PDF
  3-4. Test Table (hourly readings)
  5. Indoor Environmental Conditions During Test (from raw data)
  6. Outdoor Weather During Test (from Open-Meteo, by ZIP code)
  7. EPA action-level reference + Surgeon General narrative

All test data comes from the raw PDF. Outdoor weather comes from
Open-Meteo (free, no API key). Static company branding (RMS, website,
logo) lives in the COMPANY dict below.

Usage:
    python radon_report.py <raw.pdf> <house.jpg> [-o output.pdf]
"""

import argparse
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import json
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pdfplumber
from PIL import Image, ImageOps
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

# Branding is supplied per request by the caller, from the firm's own record.
# These defaults are deliberately blank: a firm that has set nothing gets a
# report with nothing in those slots, never somebody else's name or licence.
COMPANY = {
    "rms_name":      "",
    "rms_license":   "",
    "rms_name_2":    "",
    "rms_license_2": "",
    "website":       "",
    "logo_path":     "",
    # Used only when the raw monitor PDF has no phone in its header.
    "company_phone": "",
}

NAVY          = HexColor("#1a3a6c")
YELLOW        = HexColor("#f4d03f")
GOLD          = HexColor("#f4a020")
GREEN         = HexColor("#2e8b2e")
RED           = HexColor("#d32f2f")
LIGHT_GRAY_BG = HexColor("#e8e4dc")
TABLE_ALT     = HexColor("#f2f2f2")
BAND_BORDER   = HexColor("#a89f8a")
LABEL_TINT    = HexColor("#cfd8e3")
SEP_BLUE      = HexColor("#4a90e2")
LINK_BLUE     = HexColor("#87cefa")
LEVEL_BLUE    = HexColor("#7a90b8")
CAUTION_ORANGE = HexColor("#d97e2e")  # caution-mode accent


# ---------------------------------------------------------------------------
# EPA action-level categorization (used to color the page-2 number ONLY)
#   < 2.0 pCi/L  -> PASS    (green)
#   2.0 - 3.9    -> CAUTION (yellow)
#   >= 4.0       -> FAIL    (red)
# This does NOT change the cover page banner -- the cover continues to use
# the raw PDF's pass/fail flag exactly as before.
# ---------------------------------------------------------------------------
def epa_category(epa_average):
    if epa_average is None:
        return ("PASS", GREEN)
    if epa_average < 2.0:
        return ("PASS", GREEN)
    if epa_average < 4.0:
        return ("CAUTION", YELLOW)
    return ("FAIL", RED)


PAGE_W, PAGE_H = letter
MARGIN = 0.5 * inch


# ===========================================================================
# Parse the raw data PDF
# ===========================================================================
def parse_sunradon_pdf(pdf_path):
    """Parse a SunRADON raw test PDF.

    Handles both the older format (where Page 1 has 3 columns:
    Test Location / Test For / Test Performed By) and the newer format
    (where the same fields are stacked vertically and use slightly
    different keys).
    """
    data = {"readings": []}
    with pdfplumber.open(pdf_path) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        page1_words = pdf.pages[0].extract_words()

    lines = [l for l in full_text.splitlines()]
    nonempty = [l.strip() for l in lines if l.strip()]

    # ----- Company header (first 1-3 non-empty lines) ----------------
    # Old format: "<Company>\n<City, State>\n<10-digit phone>"
    # New format: "<Company>\n<Address>\n<City, State Zip>"
    #             OR sometimes "<Company>\n<City, State>" (no phone)
    data["company_name"] = nonempty[0] if nonempty else ""
    data["company_city"] = ""
    data["company_phone"] = ""

    # Try to find the phone number in the first ~10 lines
    for line in nonempty[:10]:
        m = re.match(r"^(\d{3})[-.\s]?(\d{3})[-.\s]?(\d{4})$",
                     line.strip())
        if m:
            data["company_phone"] = f"({m.group(1)}) {m.group(2)}-{m.group(3)}"
            break
    # Fallback: if no phone was found in the raw PDF header, use the
    # hardcoded one from COMPANY.
    if not data.get("company_phone"):
        data["company_phone"] = COMPANY.get("company_phone", "")
    # Try to find a city/state line in the first 5 lines
    for line in nonempty[1:5]:
        if re.search(r"[A-Za-z]+,\s*[A-Z]{2}", line):
            data["company_city"] = line
            break

    # ----- Client name and address ------------------------------------
    data["client_name"] = ""
    data["address_line1"] = ""
    data["address_line2"] = ""

    # Try OLD format first: column-aware extraction with "Location:" + "Test"
    loc_x = loc_top = None
    for w in page1_words:
        if w["text"] == "Location:":
            if any(ww["text"] == "Test" and abs(ww["top"] - w["top"]) < 3
                   and ww["x1"] < w["x0"] and w["x0"] - ww["x1"] < 10
                   for ww in page1_words):
                loc_x = w["x0"] - 25
                loc_top = w["top"]
                break

    if loc_x is not None and loc_top is not None:
        same_row = [w for w in page1_words
                    if abs(w["top"] - loc_top) < 3 and w["x0"] > loc_x + 50]
        middle_x = min(w["x0"] for w in same_row) if same_row else loc_x + 150
        col_words = [
            w for w in page1_words
            if loc_x - 5 <= w["x0"] < middle_x - 5
            and loc_top + 5 < w["top"] < loc_top + 80
        ]
        col_lines = []
        for w in sorted(col_words, key=lambda x: (x["top"], x["x0"])):
            if col_lines and abs(w["top"] - col_lines[-1][0]["top"]) < 3:
                col_lines[-1].append(w)
            else:
                col_lines.append([w])
        text_lines = [" ".join(x["text"] for x in line) for line in col_lines]
        if len(text_lines) >= 1:
            data["client_name"] = text_lines[0]
        if len(text_lines) >= 2:
            data["address_line1"] = text_lines[1]
        if len(text_lines) >= 3:
            data["address_line2"] = re.sub(r"\s+,", ",", text_lines[2])

    # If column extraction failed (new format), try line-based scan:
    # Look for "Test Location:" line, then take the next 2-4 non-empty lines
    # as name / addr1 / addr2 / type. Skip "Residential ..." property type line.
    if not data["client_name"]:
        for i, line in enumerate(lines):
            if "Test Location:" in line:
                # Collect following non-empty lines
                trailing = []
                for j in range(i + 1, min(i + 8, len(lines))):
                    s = lines[j].strip()
                    if not s:
                        continue
                    # Stop if we hit the next labeled section
                    if re.match(r"^(Test\s|Residential|Commercial|Inspector|"
                                r"Monitor your|Scan QR)", s):
                        if s.startswith("Residential") or s.startswith("Commercial"):
                            break
                        break
                    trailing.append(s)
                    if len(trailing) >= 3:
                        break
                if len(trailing) >= 1:
                    data["client_name"] = trailing[0]
                if len(trailing) >= 2:
                    data["address_line1"] = trailing[1]
                if len(trailing) >= 3:
                    data["address_line2"] = re.sub(r"\s+,", ",", trailing[2])
                break

    data["zip_code"] = (_extract_zip(data["address_line2"])
                        or _extract_zip(data["address_line1"])
                        or _extract_zip(data["client_name"]))

    # ----- Test window -----------------------------------------------
    # Both formats:
    #   "<startdate> <starttime> <enddate> <endtime> N hr N hr"
    m = re.search(
        r"(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2}\s*[AP]M)\s+"
        r"(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2}\s*[AP]M)\s+"
        r"\d+\s*hr\s+(\d+)\s*hr",
        full_text,
    )
    if not m:
        raise ValueError("Could not find test start/stop/duration block")
    data["start_dt"] = _parse_dt(m.group(1), m.group(2))
    data["end_dt"] = _parse_dt(m.group(3), m.group(4))
    data["duration_hr"] = int(m.group(5))

    # ----- Room / location of monitor --------------------------------
    # Old format: "CRM Location:\nStart Stop\n...\n<room> <date>..."
    # New format: "CRM Location: Start Stop Interval Duration\n<room> <date>..."
    data["room"] = "First Floor"
    # ROOMFIX v2: monitor-location extraction. PRIMARY source is the
    # standalone "Location: X" chart/table header, which carries the full
    # location on a single line in the OneRADON format. The "CRM Location:"
    # Test Summary cell is unreliable: when the location wraps, pdfplumber
    # places the first line on the date row and orphans the tail BELOW the
    # date, so a date-terminated capture silently drops it. A trailing
    # "(*Data ...)" parenthetical is stripped; a short wrapped continuation
    # fragment (old-format headers) is conservatively joined. The CRM
    # Location cell is used only as a fallback when no header is present.
    _glines = full_text.splitlines()
    _STOP = re.compile(
        r"^(Test\b|CRM\b|Start Time|End Time|SN:|Calibration|Red Line|"
        r"Highest|Lowest|EPA|Date/Time|Inspection|Page |The test data|"
        r"Overall |Radon |Temperature|Humidity|Pressure|Closed )")
    def _clean_room(_s):
        _s = re.sub(r"\s*\(\*.*$", "", _s)
        return re.sub(r"\s+", " ", _s).strip()
    for _i, _ln in enumerate(_glines):
        _m = re.match(r"^\s*Location:\s*(.+?)\s*$", _ln)
        if not _m:
            continue
        _cand = _clean_room(_m.group(1))
        _nxt = _glines[_i + 1].strip() if _i + 1 < len(_glines) else ""
        if (_nxt and len(_nxt.split()) <= 2
                and re.fullmatch(r"[A-Za-z][A-Za-z /-]*", _nxt)
                and not _STOP.match(_nxt)
                and not re.search(r"\d{1,2}:\d{2}\s*[AP]M|\d{2}/\d{2}/\d{4}", _nxt)):
            _cand = _clean_room(_cand + " " + _nxt)
        if _cand:
            data["room"] = _cand
            break
    if data["room"] == "First Floor":
        rm = re.search(r"CRM Location:.*?\n(.+?)\s+\d{2}/\d{2}/\d{4}",
                       full_text, re.DOTALL)
        if rm:
            room = re.sub(r"\s+", " ", rm.group(1).strip())
            room = re.sub(r"^Start\s+Stop\s+Interval\s+Duration\s*", "", room).strip()
            if room:
                data["room"] = room
    # ----- Monitor model / serial / calibration ----------------------
    m = re.search(r"SunRADON CRM:\s*(\S+)", full_text)
    data["monitor_model"] = m.group(1) if m else "1028xp"
    m = re.search(r"Serial Number:\s*(\S+)", full_text)
    data["monitor_serial_full"] = m.group(1) if m else ""
    data["monitor_serial_short"] = (
        data["monitor_serial_full"].lstrip("0")[-4:]
        if data["monitor_serial_full"] else ""
    )
    m = re.search(r"Next Calibration:\s*(\d{2}/\d{2}/\d{4})", full_text)
    data["calibration_due"] = m.group(1) if m else ""

    # ----- EPA average / overall average -----------------------------
    # Old format: "Overall Average:\s*EPA Average:\s*\n?\s*X pCi/l Y pCi/l"
    # New format: averages on separate stacked lines, e.g.
    #   "Overall Average:"
    #   "10.6 pCi/l"
    #   "EPA Average:"
    #   "10.6 pCi/l"
    data["overall_average"] = None
    data["epa_average"] = None

    # Try old single-line format first
    m = re.search(
        r"Overall Average:\s*EPA Average:\s*\n?\s*"
        r"([\d.]+)\s*pCi/l\s+([\d.]+)\s*pCi/l",
        full_text,
    )
    if m:
        data["overall_average"] = float(m.group(1))
        data["epa_average"] = float(m.group(2))
    else:
        # Try new stacked format with values on lines after each label
        em = re.search(
            r"EPA Average:[\s\n]*([\d.]+)\s*pCi/?l", full_text, re.IGNORECASE)
        om = re.search(
            r"Overall Average:[\s\n]*([\d.]+)\s*pCi/?l", full_text,
            re.IGNORECASE)
        if em:
            data["epa_average"] = float(em.group(1))
        if om:
            data["overall_average"] = float(om.group(1))

    # Final fallback: pull from the "Test Details" stats line
    # e.g. "Radon Concentration   3.0   21.2   10.6   pCi/l"
    if data["epa_average"] is None:
        m = re.search(
            r"Radon Concentration\s+[\d.]+\s+[\d.]+\s+([\d.]+)\s+pCi",
            full_text)
        if m:
            data["epa_average"] = float(m.group(1))
            data["overall_average"] = data["epa_average"]

    # ----- Test result (PASS/FAIL) -----------------------------------
    if "Test Result: Pass" in full_text:
        data["result"] = "PASS"
    elif "Test Result: Fail" in full_text:
        data["result"] = "FAIL"
    else:
        # Derive from EPA average if not explicit
        avg = data.get("epa_average")
        data["result"] = "FAIL" if (avg is not None and avg >= 4.0) else "PASS"

    # ----- Caution flag (PASS but EPA avg in 2.7-3.9 range) ----------
    _avg_check = data.get("epa_average")
    data["caution"] = (data["result"] == "PASS"
                       and _avg_check is not None
                       and 2.7 <= _avg_check <= 3.9)

    # ----- Hourly readings -------------------------------------------
    # Two row formats:
    #   FULL: "MM/DD/YY HH:MM AM 7.2 67.8 29.78 53 -"
    #         (date, time, radon, temp, pres, humid, flag)
    #   RADON-ONLY: "MM/DD/YY HH:MM AM 7.2 -"
    #         (date, time, radon, flag)
    full_row_re = re.compile(
        r"(\d{2}/\d{2}/\d{2})\s+(\d{1,2}:\d{2}\s*[AP]M)\s+"
        r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)\s+(\S)"
    )
    radon_row_re = re.compile(
        r"^(\d{2}/\d{2}/\d{2})\s+(\d{1,2}:\d{2}\s*[AP]M)\s+"
        r"([\d.]+)\s+(\S)\s*$"
    )

    for line in full_text.splitlines():
        s = line.strip()
        # Try full row first
        m = full_row_re.match(s)
        if m:
            date_s, time_s, radon, temp, pres, humid, flag = m.groups()
            dt = _parse_dt(date_s, time_s, short_year=True)
            data["readings"].append({
                "dt": dt, "radon": float(radon), "temp": float(temp),
                "pres": float(pres), "humid": int(humid), "flag": flag,
            })
            continue
        # Radon-only row (new monitors that lack env data)
        m = radon_row_re.match(s)
        if m:
            date_s, time_s, radon, flag = m.groups()
            dt = _parse_dt(date_s, time_s, short_year=True)
            data["readings"].append({
                "dt": dt, "radon": float(radon),
                "temp": None, "pres": None, "humid": None,
                "flag": flag,
            })

    if not data["readings"]:
        raise ValueError("Could not parse any hourly readings from the PDF")

    radon_vals = [r["radon"] for r in data["readings"]]
    max_idx = radon_vals.index(max(radon_vals))
    min_idx = len(radon_vals) - 1 - radon_vals[::-1].index(min(radon_vals))
    data["highest"] = data["readings"][max_idx]
    data["lowest"] = data["readings"][min_idx]

    return data


def _normalize_image(path):
    """Prepare an input image for reportlab.

    reportlab draws raw pixels and ignores the EXIF orientation tag, so two
    fixes are needed:
      1. Bake in EXIF orientation. Phone photos are often stored sideways with
         an orientation tag telling viewers to rotate them; without this the
         cover photo renders rotated 90 degrees.
      2. Convert HEIC/HEIF to JPEG (reportlab cannot read HEIC at all).

    Returns a normalized temp-file path when work was needed, otherwise the
    original path unchanged.
    """
    if path is None:
        return None
    p = Path(path)
    ext = p.suffix.lower()
    is_heic = ext in ('.heic', '.heif')
    try:
        img = Image.open(p)
        try:
            orientation = img.getexif().get(0x0112, 1)
        except Exception:
            orientation = 1
        needs_rotate = orientation not in (0, 1)
        # Not HEIC and already upright: leave the original file untouched.
        if not is_heic and not needs_rotate:
            return path
        # Bake orientation into the pixels and strip the tag.
        out = ImageOps.exif_transpose(img)
        # Keep PNG + alpha when only rotating a PNG; everything else -> JPEG.
        if not is_heic and ext == '.png':
            suffix, fmt = '.png', 'PNG'
        else:
            suffix, fmt = '.jpg', 'JPEG'
        if fmt == 'JPEG' and out.mode not in ('RGB', 'L'):
            out = out.convert('RGB')
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, prefix='radon_')
        tmp.close()
        if fmt == 'JPEG':
            out.save(tmp.name, 'JPEG', quality=95)
        else:
            out.save(tmp.name, 'PNG')
        return tmp.name
    except Exception as e:
        print(f'[warn] image normalization failed for {p}: {e}', file=sys.stderr)
        return path


def _extract_zip(city_line):
    m = re.search(r"(\d{5})", city_line or "")
    return m.group(1) if m else ""


def _parse_dt(date_s, time_s, short_year=False):
    fmt = "%m/%d/%y %I:%M %p" if short_year else "%m/%d/%Y %I:%M %p"
    return datetime.strptime(f"{date_s} {time_s}", fmt)


# ===========================================================================
# Extract the chart image from the raw PDF (page 2 of SunRADON output)
# ===========================================================================
def _detect_chart_bbox(img):
    """Locate the chart's tight bounding box on a rendered SunRADON page 2.

    Anchors on the colored data/action lines (green Radon line + red action
    line -- the only saturated content on the page) then grows outward to the
    surrounding whitespace gaps so the crop includes the location title, both
    y-axes, the timeline and the legend, while excluding the page header,
    footer and the large blank band that newer SunRADON formats leave below
    the chart.  Returns (left, top, right, bottom), or None if not confident
    (in which case the caller falls back to a fixed proportional crop)."""
    try:
        import numpy as np
    except ImportError:
        return None
    a = np.asarray(img.convert("RGB")).astype(int)
    H, W = a.shape[:2]
    ink = a.max(2) < 245                      # any non-white pixel
    colored = (a.max(2) - a.min(2)) > 40      # saturated (green/red) pixel
    ys, xs = np.where(colored)
    if len(xs) < 50:
        return None
    cx0, cx1 = int(xs.min()), int(xs.max())
    cy0, cy1 = int(ys.min()), int(ys.max())
    padx, pady = int(0.10 * W), int(0.06 * H)
    wx0, wx1 = max(0, cx0 - padx), min(W, cx1 + padx)
    wy0, wy1 = max(0, cy0 - pady), min(H, cy1 + pady)
    row_empty = ink[:, wx0:wx1].sum(1) < 0.01 * (wx1 - wx0)
    col_empty = ink[wy0:wy1, :].sum(0) < 0.01 * (wy1 - wy0)
    gap = max(6, int(0.025 * H))              # blank run that ends the chart

    def grow(empty, start, step, limit):
        i, run = start, 0
        while 0 <= i < limit:
            if empty[i]:
                run += 1
                if run >= gap:
                    return i - step * run     # last inked line before the gap
            else:
                run = 0
            i += step
        return 0 if step < 0 else limit - 1

    top    = grow(row_empty, cy0, -1, H)
    bottom = grow(row_empty, cy1,  1, H)
    left   = grow(col_empty, cx0, -1, W)
    right  = grow(col_empty, cx1,  1, W)
    p = int(0.012 * H)
    left, top = max(0, left - p), max(0, top - p)
    right, bottom = min(W, right + p), min(H, bottom + p)
    # Sanity check: reject implausible detections -> fixed-crop fallback.
    if (bottom - top) < 0.12 * H or (bottom - top) > 0.95 * H \
            or (right - left) < 0.30 * W:
        return None
    return (left, top, right, bottom)


def _crop_chart(img):
    """Crop a rendered page-2 image tightly to the chart, with a safe
    fixed-proportion fallback if content detection isn't confident."""
    box = _detect_chart_bbox(img)
    if box is None:
        w, h = img.size
        box = (0, int(h * 0.08), w, int(h * 0.82))
    return img.crop(box)


def extract_chart_image(pdf_path):
    """Render page 2 of the raw PDF as a PNG image and crop tightly to the
    chart region.  pdftoppm ships with poppler, which is on every Mac with
    Homebrew or directly available via 'brew install poppler'.  We try
    pdftoppm first; if unavailable, fall back to pdfplumber's rasterizer."""
    out_buf = BytesIO()

    # Try pypdfium2 first. It is a pip wheel, so it is native on Apple
    # Silicon and needs no system binary -- which also means it works on a
    # server. pdftoppm stays below as a fallback.
    try:
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(str(pdf_path))
        try:
            page = doc[1]  # 0-indexed -> page 2
            pil_img = page.render(scale=200 / 72).to_pil()
        finally:
            doc.close()
        _crop_chart(pil_img).save(out_buf, format="PNG")
        out_buf.seek(0)
        return out_buf
    except Exception as e:
        print(f"[warn] pypdfium2 render failed: {e}", file=sys.stderr)

    # Fallback: pdftoppm from poppler.
    # OSError catches "Bad CPU type in executable" -- an Intel poppler
    # install on an Apple Silicon Mac raises that, not CalledProcessError.
    try:
        with tempfile.TemporaryDirectory() as td:
            prefix = Path(td) / "p"
            subprocess.run(
                ["pdftoppm", "-r", "200", "-f", "2", "-l", "2", "-png",
                 str(pdf_path), str(prefix)],
                check=True, capture_output=True,
            )
            files = sorted(Path(td).glob("p-*.png"))
            if files:
                _crop_chart(Image.open(files[0])).save(out_buf, format="PNG")
                out_buf.seek(0)
                return out_buf
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass

    # Fallback: pdfplumber rasterizer (uses ghostscript or PyMuPDF if available)
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[1]  # 0-indexed -> page 2
            pil_img = page.to_image(resolution=200).original
            _crop_chart(pil_img).save(out_buf, format="PNG")
            out_buf.seek(0)
            return out_buf
    except Exception as e:
        print(f"[warn] could not extract chart image: {e}", file=sys.stderr)
        return None


# ===========================================================================
# Outdoor weather via Open-Meteo (free, no key)
# ===========================================================================
def _fetch_weather_by_city(address_line2, start_dt, end_dt):
    """Geocode City, ST from an address line and pull weather there.
    Used when a SunRADON address has no ZIP code."""
    if not address_line2:
        return None
    m = re.search(r"([A-Z][A-Za-z .'-]+?)\s*,\s*([A-Z]{2})\b", address_line2)
    if not m:
        print(f"[warn] could not parse city/state from {address_line2!r}", file=sys.stderr)
        return None
    city, state = m.group(1).strip(), m.group(2).strip()
    lat = lon = None
    try:
        url = ("https://geocoding-api.open-meteo.com/v1/search?"
               + urllib.parse.urlencode({"name": city, "country": "US",
                                         "admin1": state, "count": 1}))
        geo = _get_json(url)
        if geo and geo.get("results"):
            lat = geo["results"][0]["latitude"]
            lon = geo["results"][0]["longitude"]
    except Exception:
        pass
    if lat is None or lon is None:
        print(f"[warn] could not geocode {city}, {state}", file=sys.stderr)
        return None
    today = datetime.now().date()
    days_back = max(1, (today - start_dt.date()).days + 1)
    if days_back > 92:
        return _fetch_via_archive(lat, lon, start_dt, end_dt)
    return _fetch_via_forecast(lat, lon, start_dt, end_dt)


def fetch_outdoor_weather(zip_code, start_dt, end_dt, address_line2=None):
    """Returns dict with daily and hourly outdoor weather for the test
    window, or None if anything fails.

    Uses the regular forecast API (which includes past_days up to 92,
    so SAME-DAY reports work) -- not the archive API, which has a
    ~5 day lag and would return empty results for recent tests.

    Geocoding is tried in this order:
      1) Zippopotam.us (purpose-built ZIP -> lat/lon, no auth)
      2) Open-Meteo geocoder (fallback)
    """
    if not zip_code:
        return _fetch_weather_by_city(address_line2, start_dt, end_dt)

    # 1) Geocode the ZIP -> lat/lon
    lat = lon = None
    try:
        zp = _get_json(f"https://api.zippopotam.us/us/{zip_code}")
        if zp and zp.get("places"):
            lat = float(zp["places"][0]["latitude"])
            lon = float(zp["places"][0]["longitude"])
    except Exception:
        pass

    if lat is None or lon is None:
        try:
            url = ("https://geocoding-api.open-meteo.com/v1/search?"
                   + urllib.parse.urlencode(
                       {"name": zip_code, "country": "US", "count": 1}))
            geo = _get_json(url)
            if not geo or not geo.get("results"):
                url = ("https://geocoding-api.open-meteo.com/v1/search?"
                       + urllib.parse.urlencode(
                           {"name": zip_code, "count": 1}))
                geo = _get_json(url)
            if geo and geo.get("results"):
                lat = geo["results"][0]["latitude"]
                lon = geo["results"][0]["longitude"]
        except Exception:
            pass

    if lat is None or lon is None:
        print(f"[warn] could not geocode ZIP {zip_code}", file=sys.stderr)
        return None

    # 2) Pull weather via shared helper.
    today = datetime.now().date()
    days_back = max(1, (today - start_dt.date()).days + 1)
    if days_back > 92:
        return _fetch_via_archive(lat, lon, start_dt, end_dt)
    return _fetch_via_forecast(lat, lon, start_dt, end_dt)


def _fetch_via_forecast(lat, lon, start_dt, end_dt):
    try:
        today = datetime.now().date()
        days_back = max(1, (today - start_dt.date()).days + 1)

        # forecast_days needs to cover any portion of the test that
        # extends past today
        forecast_days = max(1, (end_dt.date() - today).days + 1) \
            if end_dt.date() >= today else 1

        params = {
            "latitude": lat, "longitude": lon,
            "past_days": days_back,
            "forecast_days": min(forecast_days, 16),
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,"
                      "weather_code,wind_speed_10m,pressure_msl",
            "daily": "temperature_2m_max,temperature_2m_min,"
                     "precipitation_sum,weather_code",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "America/New_York",
        }
        url = ("https://api.open-meteo.com/v1/forecast?"
               + urllib.parse.urlencode(params))
        wx = _get_json(url)
        if not wx or "hourly" not in wx:
            # Last-ditch: try the archive endpoint
            return _fetch_via_archive(lat, lon, start_dt, end_dt)

        return _shape_weather_response(wx, lat, lon, start_dt, end_dt)
    except Exception as e:
        print(f"[warn] outdoor weather fetch failed: {e}", file=sys.stderr)
        return None


def _fetch_via_archive(lat, lon, start_dt, end_dt):
    """Older tests use the archive endpoint."""
    try:
        params = {
            "latitude": lat, "longitude": lon,
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": end_dt.strftime("%Y-%m-%d"),
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,"
                      "weather_code,wind_speed_10m,pressure_msl",
            "daily": "temperature_2m_max,temperature_2m_min,"
                     "precipitation_sum,weather_code",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "America/New_York",
        }
        url = ("https://archive-api.open-meteo.com/v1/archive?"
               + urllib.parse.urlencode(params))
        wx = _get_json(url)
        if not wx or "hourly" not in wx:
            return None
        return _shape_weather_response(wx, lat, lon, start_dt, end_dt)
    except Exception as e:
        print(f"[warn] archive endpoint also failed: {e}", file=sys.stderr)
        return None


def _shape_weather_response(wx, lat, lon, start_dt, end_dt):
    """Convert the raw Open-Meteo JSON into the shape the renderer expects.
    Filters hourly + daily entries to only the test window."""
    start_d = start_dt.date()
    end_d = end_dt.date()

    hourly = []
    for (t, tt, hh, pp, cc, ww, ps) in zip(
        wx["hourly"]["time"],
        wx["hourly"]["temperature_2m"],
        wx["hourly"]["relative_humidity_2m"],
        wx["hourly"]["precipitation"],
        wx["hourly"]["weather_code"],
        wx["hourly"]["wind_speed_10m"],
        wx["hourly"]["pressure_msl"],
    ):
        try:
            dt = datetime.fromisoformat(t)
        except Exception:
            continue
        if dt.date() < start_d or dt.date() > end_d:
            continue
        hourly.append({
            "dt": dt, "temp": tt, "humid": hh, "precip": pp,
            "code": cc, "wind": ww, "pres": ps,
        })

    daily = []
    for (d, tmax, tmin, pp, cc) in zip(
        wx["daily"]["time"],
        wx["daily"]["temperature_2m_max"],
        wx["daily"]["temperature_2m_min"],
        wx["daily"]["precipitation_sum"],
        wx["daily"]["weather_code"],
    ):
        try:
            day = datetime.fromisoformat(d).date()
        except Exception:
            continue
        if day < start_d or day > end_d:
            continue
        daily.append({
            "date": day,
            "tmax": tmax if tmax is not None else 0,
            "tmin": tmin if tmin is not None else 0,
            "precip": pp if pp is not None else 0,
            "code": cc if cc is not None else 0,
        })

    if not hourly and not daily:
        return None

    out = {"lat": lat, "lon": lon, "hourly": hourly, "daily": daily}
    humids = [h["humid"] for h in hourly if h["humid"] is not None]
    out["humidity_range"] = (min(humids), max(humids)) if humids else None
    return out


def _get_json(url, retries=5, timeout=30):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "RadonReportMaker/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status == 200:
                    return json.loads(r.read().decode("utf-8"))
                last = f"status={r.status}"
        except Exception as e:
            last = str(e)
        time.sleep(1.5 ** attempt)
    print(f"[warn] {url[:60]}... failed after {retries} tries: {last}",
          file=sys.stderr)
    return None


def render_outdoor_chart(weather):
    """Two-stack chart for outdoor weather: top = temperature, bottom =
    humidity + precipitation."""
    if not weather or not weather.get("hourly"):
        return None
    times = [h["dt"] for h in weather["hourly"]]
    temps = [h["temp"] for h in weather["hourly"]]
    humids = [h["humid"] for h in weather["hourly"]]
    precips = [h["precip"] or 0 for h in weather["hourly"]]
    winds = [h["wind"] for h in weather["hourly"]]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9, 7), gridspec_kw={"height_ratios": [1, 1]}
    )
    fig.suptitle("Outdoor Weather During Test", fontsize=12)

    ax1.plot(times, temps, color="#f4a020", linewidth=1.8, label="Temp (F)")
    ax1.set_ylabel("Temperature (F)")
    ax1.set_xlabel("Outdoor Temperature Timeline")
    ax1.grid(True, alpha=0.3)
    ax1_right = ax1.twinx()
    ax1_right.plot(times, winds, color="#888888", linewidth=1.0,
                   linestyle="--", label="Wind (mph)")
    ax1_right.set_ylabel("Wind (mph)")
    l1, lab1 = ax1.get_legend_handles_labels()
    l2, lab2 = ax1_right.get_legend_handles_labels()
    ax1.legend(l1 + l2, lab1 + lab2, loc="lower center",
               bbox_to_anchor=(0.5, -0.40), ncol=2, frameon=False, fontsize=9)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
    for label in ax1.get_xticklabels():
        label.set_fontsize(8)

    ax2.plot(times, humids, color="#87CEEB", linewidth=1.5,
             label="Relative Humidity (%)")
    ax2.set_ylabel("Humidity (%)")
    ax2.set_ylim(0, 105)
    ax2.set_xlabel("Outdoor Humidity & Precipitation Timeline")
    ax2.grid(True, alpha=0.3)
    ax2_right = ax2.twinx()
    ax2_right.bar(times, precips, color="#4a90e2", width=0.04,
                  alpha=0.6, label="Precipitation (in)")
    ax2_right.set_ylabel("Precipitation (in)")
    if precips and max(precips) > 0:
        ax2_right.set_ylim(0, max(0.5, max(precips) * 1.4))
    else:
        ax2_right.set_ylim(0, 0.5)
    l1, lab1 = ax2.get_legend_handles_labels()
    l2, lab2 = ax2_right.get_legend_handles_labels()
    ax2.legend(l1 + l2, lab1 + lab2, loc="lower center",
               bbox_to_anchor=(0.5, -0.40), ncol=2, frameon=False, fontsize=9)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
    for label in ax2.get_xticklabels():
        label.set_fontsize(8)

    fig.subplots_adjust(top=0.93, bottom=0.20, left=0.10, right=0.92,
                        hspace=0.85)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                pad_inches=0.3)
    plt.close(fig)
    buf.seek(0)
    return buf


# ===========================================================================
# PDF builder
# ===========================================================================
def build_pdf(data, house_image, output_path, report_number,
              raw_pdf_path, weather):
    c = canvas.Canvas(str(output_path), pagesize=letter)

    house_image = _normalize_image(house_image)
    chart_buf = extract_chart_image(raw_pdf_path)

    _draw_cover(c, data, house_image, report_number)
    c.showPage()
    _draw_chart_page(c, data, chart_buf)
    c.showPage()
    _draw_table_pages(c, data)
    _has_env = any(
        r.get("temp") is not None
        or r.get("humid") is not None
        or r.get("pres") is not None
        for r in data.get("readings", [])
    )
    if _has_env:
        _draw_environment_page(c, data)
    c.showPage()
    _draw_outdoor_weather_page(c, data, weather)
    c.showPage()
    _draw_epa_reference_page(c, data)
    c.save()


# ---- Cover page (bigger photo, packed navy box, no overlap) --------------
def _draw_cover(c, data, house_image, report_number):
    # Title banner
    c.setFillColor(NAVY)
    c.setStrokeColor(BAND_BORDER)
    c.setLineWidth(8)
    c.rect(MARGIN, PAGE_H - 2.1 * inch, PAGE_W - 2 * MARGIN, 1.5 * inch,
           fill=1, stroke=1)
    c.setFillColor(YELLOW)
    c.setFont("Helvetica-Bold", 40)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 1.25 * inch, "Radon Report")

    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 22)
    rt = "EPA Test Result: "
    rt_w = c.stringWidth(rt, "Helvetica-Bold", 22)
    _caution = data.get("caution", False)
    _result_label = ("*" + data["result"]) if _caution else data["result"]
    _suffix = " -With Caution" if _caution else ""
    _suffix_size = 13
    pass_w = c.stringWidth(_result_label, "Helvetica-Bold", 22)
    suffix_w = c.stringWidth(_suffix, "Helvetica-Bold", _suffix_size) if _suffix else 0
    x0 = (PAGE_W - (rt_w + pass_w + suffix_w)) / 2
    c.drawString(x0, PAGE_H - 1.85 * inch, rt)
    c.setFillColor(GREEN if data["result"] == "PASS" else RED)
    c.drawString(x0 + rt_w, PAGE_H - 1.85 * inch, _result_label)
    c.setStrokeColor(GREEN if data["result"] == "PASS" else RED)
    c.setLineWidth(1.5)
    c.line(x0 + rt_w, PAGE_H - 1.9 * inch,
           x0 + rt_w + pass_w, PAGE_H - 1.9 * inch)
    if _suffix:
        c.setFillColor(CAUTION_ORANGE)
        c.setFont("Helvetica-Bold", _suffix_size)
        c.drawString(x0 + rt_w + pass_w, PAGE_H - 1.85 * inch, _suffix)
        c.setFont("Helvetica-Bold", 22)

    # House photo -- BIGGER (was 2.8x3.0, now 3.6x4.0)
    photo_bottom = PAGE_H - 6.4 * inch
    try:
        img = Image.open(house_image)
        iw, ih = img.size
        max_w, max_h = 3.6 * inch, 4.0 * inch
        scale = min(max_w / iw, max_h / ih)
        w, h = iw * scale, ih * scale
        x = (PAGE_W - w) / 2
        y = PAGE_H - 2.1 * inch - h - 0.25 * inch
        pad = 0.08 * inch
        c.setFillColor(white)
        c.rect(x - pad, y - pad, w + 2 * pad, h + 2 * pad, fill=1, stroke=0)
        c.drawImage(str(house_image), x, y, w, h,
                    preserveAspectRatio=True, mask="auto")
        c.setStrokeColor(HexColor("#cccccc"))
        c.setLineWidth(0.5)
        c.rect(x - pad, y - pad, w + 2 * pad, h + 2 * pad, fill=0, stroke=1)
        photo_bottom = y - pad
    except Exception as e:
        print(f"[warn] could not place house image: {e}", file=sys.stderr)

    # Info box -- fills entire space below the photo down to the bottom margin
    box_top = photo_bottom - 0.2 * inch
    box_h = box_top - MARGIN
    c.setFillColor(LIGHT_GRAY_BG)
    c.rect(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, box_h, fill=1, stroke=0)
    c.setFillColor(NAVY)
    inner_x = MARGIN + 0.15 * inch
    inner_y = MARGIN + 0.15 * inch
    inner_w = PAGE_W - 2 * MARGIN - 0.3 * inch
    inner_h = box_h - 0.3 * inch
    c.rect(inner_x, inner_y, inner_w, inner_h, fill=1, stroke=0)

    # Two columns inside the navy box. Left column content is laid out
    # so it spans top to bottom of the box with consistent spacing --
    # no big dead zone at the bottom.
    col_pad_top = 0.30 * inch
    col_pad_bot = 0.28 * inch
    col_pad_x   = 0.35 * inch
    col_top = inner_y + inner_h - col_pad_top
    col_bot = inner_y + col_pad_bot
    col_avail_h = col_top - col_bot

    lx = inner_x + col_pad_x

    # Left-column rows. Each entry is (kind, label_or_text, value_or_None).
    rows = [
        ("title",  f"Report#: {report_number}", None),
        ("field",  "Start Date:", data["start_dt"].strftime("%B %-d, %Y")),
        ("field",  "End Date:",   data["end_dt"].strftime("%B %-d, %Y")),
        ("field",  "Duration:",   f"{data['duration_hr']} Hours"),
        ("field",  "Client:",     data["client_name"]),
        ("field",  "Location:",   data["address_line1"]),
        ("addr2",  data["address_line2"], None),
        ("rms",    None, None),
        ("mon_h",  "SunRadon Monitor Information :", None),
        ("mon_m",  f"Model: {data['monitor_model'].lower()}", None),
        ("mon_s",  data["monitor_serial_short"] or data["monitor_serial_full"], None),
    ]
    row_h = {
        "title": 0.40 * inch, "field": 0.24 * inch, "addr2": 0.24 * inch,
        "rms":   0.46 * inch, "mon_h": 0.18 * inch, "mon_m": 0.16 * inch,
        "mon_s": 0.16 * inch,
    }
    total_h = sum(row_h[r[0]] for r in rows)
    extra_gap = max(0.0, (col_avail_h - total_h) / max(1, len(rows) - 1))

    ly = col_top
    for kind, a, b in rows:
        if kind == "title":
            c.setFillColor(white)
            c.setFont("Helvetica-Bold", 17)
            c.drawString(lx, ly - 0.20 * inch, a)
        elif kind == "field":
            c.setFillColor(white)
            c.setFont("Helvetica", 11)
            c.drawString(lx, ly - 0.16 * inch, a)
            c.drawString(lx + 1.0 * inch, ly - 0.16 * inch, b or "")
        elif kind == "addr2":
            c.setFillColor(white)
            c.setFont("Helvetica", 11)
            c.drawString(lx + 1.0 * inch, ly - 0.16 * inch, a or "")
        elif kind == "rms":
            c.setFillColor(white)
            c.setFont("Helvetica", 11)
            y_text = ly - 0.20 * inch
            c.drawString(lx, y_text, "RMS:")
            c.drawString(lx + 1.0 * inch, y_text, COMPANY["rms_name"])
            name_w = c.stringWidth(COMPANY["rms_name"], "Helvetica", 11)
            c.setFont("Helvetica", 8)
            c.drawString(lx + 1.0 * inch + name_w + 4, y_text,
                         COMPANY["rms_license"])
            # Optional second RMS row (e.g., a co-licensed inspector)
            if COMPANY.get("rms_name_2"):
                y2 = y_text - 0.18 * inch
                c.setFont("Helvetica", 11)
                c.drawString(lx + 1.0 * inch, y2, COMPANY["rms_name_2"])
                name2_w = c.stringWidth(COMPANY["rms_name_2"], "Helvetica", 11)
                c.setFont("Helvetica", 8)
                c.drawString(lx + 1.0 * inch + name2_w + 4, y2,
                             COMPANY.get("rms_license_2", ""))
        elif kind == "mon_h":
            c.setFillColor(white)
            c.setFont("Helvetica", 9)
            c.drawString(lx, ly - 0.13 * inch, a)
        elif kind == "mon_m":
            c.setFillColor(white)
            c.setFont("Helvetica", 9)
            c.drawString(lx + 0.15 * inch, ly - 0.12 * inch, a)
        elif kind == "mon_s":
            c.setFillColor(white)
            c.setFont("Helvetica", 9)
            c.drawString(lx + 0.15 * inch, ly - 0.12 * inch,
                         f"Serial Number: {a}")
        ly -= (row_h[kind] + extra_gap)

    # Right column: contact, logo, phone -- vertically distributed
    right_x = inner_x + inner_w / 2 + 0.15 * inch
    right_w = inner_w / 2 - col_pad_x - 0.15 * inch
    rtop = col_top
    rbot = col_bot

    c.setFont("Helvetica", 11)
    c.setFillColor(white)
    contact_text = ("For more information about radon or this report "
                    "please contact:")
    text_y = _draw_wrapped(c, right_x, rtop, contact_text,
                           width=right_w, leading=14)

    # Phone -- prominently displayed right under contact text
    # Was hardcoded to one company's number. Now: whatever branding the
    # caller supplied, else what the raw PDF header carried.
    phone = COMPANY.get("company_phone") or data.get("company_phone", "")
    c.setFillColor(YELLOW)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(right_x, text_y - 0.32 * inch, phone)

    # Logo fills the rest of the column below the phone
    logo_top_y = text_y - 0.60 * inch
    logo_bot_y = rbot
    avail_h = logo_top_y - logo_bot_y
    avail_w = right_w
    try:
        logo_path = Path(COMPANY["logo_path"])
        if logo_path.exists():
            logo = Image.open(logo_path)
            lw, lh = logo.size
            scale = min(avail_w / lw, avail_h / lh)
            draw_w = lw * scale
            draw_h = lh * scale
            draw_x = right_x + (right_w - draw_w) / 2
            draw_y = logo_bot_y + (avail_h - draw_h) / 2
            c.drawImage(str(logo_path), draw_x, draw_y, draw_w, draw_h,
                        preserveAspectRatio=True, mask="auto")
        else:
            print(f"[warn] logo file not found at {logo_path}",
                  file=sys.stderr)
    except Exception as e:
        print(f"[warn] logo not placed: {e}", file=sys.stderr)


def _draw_wrapped(c, x, y, text, width, leading=12):
    """Returns the y-coordinate of the LAST drawn line."""
    words = text.split()
    line = ""
    cur_y = y
    last_y = y
    for w in words:
        test = (line + " " + w).strip()
        if c.stringWidth(test, "Helvetica", 11) > width:
            c.drawString(x, cur_y, line)
            last_y = cur_y
            cur_y -= leading
            line = w
        else:
            line = test
    if line:
        c.drawString(x, cur_y, line)
        last_y = cur_y
    return last_y


# ---- Hourly graph page (extracted from raw PDF) --------------------------
def _draw_chart_page(c, data, chart_buf):
    _draw_page_header(c, "Hourly Graph", subtitle="Red Line=Action Level")

    c.setFillColor(NAVY)
    c.rect(MARGIN, MARGIN + 0.6 * inch,
           PAGE_W - 2 * MARGIN, PAGE_H - MARGIN - 1.8 * inch,
           fill=1, stroke=0)

    # LOCFIX: show the monitor room on the chart page (matches multi report)
    if data.get("room"):
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 1.62 * inch,
                            f"Location: {data['room']}")
    c.setFillColor(white)
    c.setFont("Helvetica", 10)
    c.drawString(MARGIN + 0.2 * inch, PAGE_H - 1.95 * inch,
                 f"Start Time: {data['start_dt'].strftime('%-m/%-d/%Y %-I:%M %p')}")
    c.drawString(MARGIN + 0.2 * inch, PAGE_H - 2.13 * inch,
                 f"SN: {data['monitor_serial_short'] or data['monitor_serial_full']}")
    c.drawRightString(PAGE_W - MARGIN - 0.2 * inch, PAGE_H - 1.95 * inch,
                      f"End Time: {data['end_dt'].strftime('%-m/%-d/%Y %-I:%M %p')}")
    c.drawRightString(PAGE_W - MARGIN - 0.2 * inch, PAGE_H - 2.13 * inch,
                      f"Calibration Due: {data['calibration_due']}")

    # White card with the EXTRACTED chart from the raw PDF.
    # Size the card to hug the chart's aspect ratio so the graph fills it
    # instead of floating in a large blank card (newer SunRADON charts are
    # much wider than tall). The card's TOP stays pinned just under the
    # header block; its height flexes to the chart, clamped to the space
    # available above the summary row.
    card_x = MARGIN + 0.3 * inch
    card_w = PAGE_W - 2 * MARGIN - 0.6 * inch
    card_top = MARGIN + 8.2 * inch            # fixed top edge (below header)
    max_card_h = PAGE_H - 5.0 * inch          # original height = upper bound
    card_h = max_card_h
    if chart_buf is not None:
        try:
            chart_buf.seek(0)
            _cw, _ch = Image.open(chart_buf).size
            chart_buf.seek(0)
            fit_h = (card_w - 4) * _ch / _cw + 4   # height to show chart full-width
            card_h = max(2.6 * inch, min(max_card_h, fit_h))
        except Exception:
            card_h = max_card_h
    card_y = card_top - card_h
    c.setFillColor(white)
    c.rect(card_x, card_y, card_w, card_h, fill=1, stroke=0)

    if chart_buf is not None:
        c.drawImage(_img_reader(chart_buf), card_x + 2, card_y + 2,
                    card_w - 4, card_h - 4, preserveAspectRatio=True,
                    mask="auto")
    else:
        # Fallback if extraction failed
        c.setFillColor(black)
        c.setFont("Helvetica", 11)
        c.drawCentredString(card_x + card_w / 2, card_y + card_h / 2,
                            "Chart unavailable")

    # ===========================================================
    # Bottom row: 3 fixed columns -- Highest | Lowest | EPA Average
    # Each column gets exactly 1/3 of usable width with a gutter
    # between them. Every text element is anchored inside its
    # column, with auto-shrink to prevent overflow.
    # ===========================================================
    hi = data["highest"]
    lo = data["lowest"]

    usable_w = PAGE_W - 2 * MARGIN - 0.4 * inch  # leave 0.2" pad each side
    gutter = 0.25 * inch
    col_w = (usable_w - 2 * gutter) / 3
    col1_x = MARGIN + 0.2 * inch                          # left edge of col 1
    col2_x = col1_x + col_w + gutter                      # left edge of col 2
    col3_x = col2_x + col_w + gutter                      # left edge of col 3
    label_y = MARGIN + 1.7 * inch
    value_y = MARGIN + 1.42 * inch
    underline_y = MARGIN + 1.39 * inch

    def _fit_size(text, font, max_w, start_size, min_size=8):
        """Shrink font size until text fits within max_w."""
        s = start_size
        while s > min_size and c.stringWidth(text, font, s) > max_w:
            s -= 1
        return s

    # --- Column 1: Highest Reading ---
    label1 = f"Highest Reading: {hi['dt'].strftime('%-m/%-d/%Y')}"
    s1 = _fit_size(label1, "Helvetica", col_w, 13)
    c.setFillColor(GOLD)
    c.setFont("Helvetica", s1)
    c.drawString(col1_x, label_y, label1)

    time1 = hi["dt"].strftime("%-I:%M %p")
    val1 = f"{hi['radon']:.1f} pCi/l"
    full1 = f"{time1}  {val1}"
    s1v = _fit_size(full1, "Helvetica", col_w, 12)
    c.setFont("Helvetica", s1v)
    c.drawString(col1_x, value_y, f"{time1}  ")
    time1_w = c.stringWidth(f"{time1}  ", "Helvetica", s1v)
    val1_x = col1_x + time1_w
    c.drawString(val1_x, value_y, val1)
    val1_w = c.stringWidth(val1, "Helvetica", s1v)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(val1_x, underline_y, val1_x + val1_w, underline_y)

    # --- Column 2: Lowest Reading ---
    label2 = f"Lowest Reading: {lo['dt'].strftime('%-m/%-d/%Y')}"
    s2 = _fit_size(label2, "Helvetica", col_w, 13)
    c.setFillColor(GOLD)
    c.setFont("Helvetica", s2)
    c.drawString(col2_x, label_y, label2)

    time2 = lo["dt"].strftime("%-I:%M %p")
    val2 = f"{lo['radon']:.1f} pCi/l"
    full2 = f"{time2}  {val2}"
    s2v = _fit_size(full2, "Helvetica", col_w, 12)
    c.setFont("Helvetica", s2v)
    c.drawString(col2_x, value_y, f"{time2}  ")
    time2_w = c.stringWidth(f"{time2}  ", "Helvetica", s2v)
    val2_x = col2_x + time2_w
    c.drawString(val2_x, value_y, val2)
    val2_w = c.stringWidth(val2, "Helvetica", s2v)
    c.line(val2_x, underline_y, val2_x + val2_w, underline_y)

    # --- Column 3: EPA Average ---
    label3 = "EPA Average"
    s3 = _fit_size(label3, "Helvetica-Bold", col_w, 20)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", s3)
    label3_w = c.stringWidth(label3, "Helvetica-Bold", s3)
    label3_x = col3_x + (col_w - label3_w) / 2  # centered in col 3
    c.drawString(label3_x, label_y, label3)

    epa_str = f"{data['epa_average']} pCi/L"
    s3v = _fit_size(epa_str, "Helvetica-Bold", col_w, 22)
    _, epa_value_color = epa_category(data.get("epa_average"))
    c.setFillColor(epa_value_color)
    c.setFont("Helvetica-Bold", s3v)
    epa_w = c.stringWidth(epa_str, "Helvetica-Bold", s3v)
    epa_x = col3_x + (col_w - epa_w) / 2
    c.drawString(epa_x, MARGIN + 1.30 * inch, epa_str)
    c.setStrokeColor(epa_value_color)
    c.setLineWidth(1.5)
    c.line(epa_x, MARGIN + 1.27 * inch, epa_x + epa_w, MARGIN + 1.27 * inch)

    # Closed-conditions disclaimer (single column, full width below).
    # If more than 4 readings have an "m" flag (movement), swap in the
    # movement-warning text instead of the no-tampering language.
    movement_count = sum(
        1 for r in data["readings"]
        if str(r.get("flag", "")).strip().lower() == "m"
    )
    c.setFillColor(white)
    c.setFont("Helvetica", 8)
    if movement_count > 4:
        c.drawString(MARGIN + 0.3 * inch, MARGIN + 1.05 * inch,
                     "Closed conditions were observed during this")
        c.drawString(MARGIN + 0.3 * inch, MARGIN + 0.92 * inch,
                     "measurement. Monitor movement detected during")
        c.drawString(MARGIN + 0.3 * inch, MARGIN + 0.79 * inch,
                     "measurement. Please refer to specialist if")
        c.drawString(MARGIN + 0.3 * inch, MARGIN + 0.66 * inch,
                     "movement altered test results.")
    else:
        c.drawString(MARGIN + 0.3 * inch, MARGIN + 1.0 * inch,
                     "Closed conditions were observed during")
        c.drawString(MARGIN + 0.3 * inch, MARGIN + 0.85 * inch,
                     "this measurement. No evidence of monitor")
        c.drawString(MARGIN + 0.3 * inch, MARGIN + 0.70 * inch,
                     "tampering detected.")


def _img_reader(buf):
    from reportlab.lib.utils import ImageReader
    return ImageReader(buf)


# ---- Test table pages -----------------------------------------------------
def _draw_table_pages(c, data):
    readings = data["readings"]
    rows_per_page = 48
    chunks = [readings[i:i + rows_per_page]
              for i in range(0, len(readings), rows_per_page)]
    for i, chunk in enumerate(chunks):
        if i > 0:
            c.showPage()
        _draw_one_table_page(c, data, chunk)


def _draw_one_table_page(c, data, rows):
    _draw_page_header(c, "Test Table", subtitle=None, smaller=True)
    c.setFillColor(black)
    c.setFont("Helvetica", 9)
    subtitle = (f"Location: {data['room']}  "
                "(*Data from first 4 hours excluded from EPA calculations)")
    c.drawCentredString(PAGE_W / 2, PAGE_H - 1.35 * inch, subtitle)
    c.setFont("Helvetica", 8)
    c.drawString(MARGIN, PAGE_H - 1.55 * inch,
                 "The test data was taken from a testing device approved by "
                 "the National Radon Proficiency Program. The test was")
    c.drawString(MARGIN, PAGE_H - 1.68 * inch,
                 "performed in accordance with the current ANSI/AARST "
                 "standards and guidelines accepted for radon testing.")

    headers = ["Date/Time", "Radon(pCi/l)", "Temp(F)", "Pres(inHg)",
               "Humidity(%)", "Flags"]
    col_x = [MARGIN + dx for dx in (0, 1.4 * inch, 2.55 * inch, 3.5 * inch,
                                     4.6 * inch, 6.0 * inch)]
    y = PAGE_H - 2.0 * inch
    c.setFillColor(HexColor("#d9d9d9"))
    c.rect(MARGIN, y - 4, PAGE_W - 2 * MARGIN, 16, fill=1, stroke=0)
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 9)
    for x, h in zip(col_x, headers):
        c.drawString(x + 2, y + 2, h)
    y -= 16

    c.setFont("Helvetica", 8)
    row_h = 12
    for i, r in enumerate(rows):
        if i % 2 == 0:
            c.setFillColor(TABLE_ALT)
            c.rect(MARGIN, y - 2, PAGE_W - 2 * MARGIN, row_h,
                   fill=1, stroke=0)
        c.setFillColor(black)
        c.drawString(col_x[0] + 2, y + 1,
                     r["dt"].strftime("%m/%d/%y %I:%M %p"))
        c.drawString(col_x[1] + 2, y + 1, f"{r['radon']:.1f}")
        # Env fields are None on radon-only monitors; render blank.
        c.drawString(col_x[2] + 2, y + 1,
                     f"{r['temp']:.1f}" if r.get("temp") is not None else "")
        c.drawString(col_x[3] + 2, y + 1,
                     f"{r['pres']:.2f}" if r.get("pres") is not None else "")
        c.drawString(col_x[4] + 2, y + 1,
                     f"{r['humid']}" if r.get("humid") is not None else "")
        c.drawString(col_x[5] + 2, y + 1, r["flag"])
        y -= row_h

    _draw_page_footer(c, data)


# ---- Indoor environmental summary page -----------------------------------
def _draw_environment_page(c, data):
    c.showPage()
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 1.0 * inch,
                        "Indoor Conditions During Test")

    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 1.4 * inch,
                        f"{data['start_dt'].strftime('%-m/%-d/%y')} - "
                        f"{data['end_dt'].strftime('%-m/%-d/%y')}   "
                        f"({data['duration_hr']} hours)")

    c.setFillColor(LABEL_TINT)
    c.setFont("Helvetica-Oblique", 11)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 1.65 * inch,
                        f"Location: {data.get('room', '')}")

    readings = data["readings"]
    by_day = {}
    for r in readings:
        d = r["dt"].date()
        by_day.setdefault(d, []).append(r)
    days = sorted(by_day.keys())
    n = len(days)

    if n > 0:
        total_w = PAGE_W - 1.5 * inch
        left_x = 0.75 * inch
        col_w = total_w / n
        col_top = PAGE_H - 2.3 * inch

        for i, d in enumerate(days):
            rs = by_day[d]
            temps  = [r["temp"]  for r in rs if r["temp"]  is not None]
            humids = [r["humid"] for r in rs if r["humid"] is not None]
            pres   = [r["pres"]  for r in rs if r["pres"]  is not None]
            cx = left_x + i * col_w + col_w / 2

            dt = datetime.combine(d, datetime.min.time())
            c.setFillColor(white)
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(cx, col_top, dt.strftime("%a, %b %-d"))

            y = col_top - 0.5 * inch
            c.setFillColor(LABEL_TINT)
            c.setFont("Helvetica-Oblique", 11)
            c.drawCentredString(cx, y, "Temperature")
            c.setFillColor(white)
            c.setFont("Helvetica", 13)
            hi_t = (f"{max(temps):.1f}" + chr(176) + "F") if temps else "--"
            lo_t = (f"{min(temps):.1f}" + chr(176) + "F") if temps else "--"
            c.drawCentredString(cx, y - 0.28 * inch, f"Hi: {hi_t}")
            c.drawCentredString(cx, y - 0.52 * inch, f"Lo: {lo_t}")

            y -= 1.10 * inch
            c.setFillColor(LABEL_TINT)
            c.setFont("Helvetica-Oblique", 11)
            c.drawCentredString(cx, y, "Humidity")
            c.setFillColor(white)
            c.setFont("Helvetica", 13)
            hum_s = f"{min(humids)}% - {max(humids)}%" if humids else "--"
            c.drawCentredString(cx, y - 0.28 * inch, hum_s)

            y -= 0.85 * inch
            c.setFillColor(LABEL_TINT)
            c.setFont("Helvetica-Oblique", 11)
            c.drawCentredString(cx, y, "Pressure (inHg)")
            c.setFillColor(white)
            c.setFont("Helvetica", 12)
            pres_s = f"{min(pres):.2f} - {max(pres):.2f}" if pres else "--"
            c.drawCentredString(cx, y - 0.28 * inch, pres_s)

        c.setStrokeColor(SEP_BLUE)
        c.setLineWidth(1.5)
        for i in range(1, n):
            x = left_x + i * col_w
            c.line(x, col_top - 3.5 * inch, x, col_top + 0.2 * inch)

    all_humids = [r["humid"] for r in readings if r["humid"] is not None]
    all_temps  = [r["temp"]  for r in readings if r["temp"]  is not None]
    all_pres   = [r["pres"]  for r in readings if r["pres"]  is not None]

    ovr_y = 2.4 * inch
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 15)
    _hum_o = f"{min(all_humids)}% - {max(all_humids)}%" if all_humids else "--"
    c.drawCentredString(PAGE_W / 2, ovr_y,
                        f"Overall Indoor Humidity: " + _hum_o)
    if all_temps:
        _tmp_o = (f"{min(all_temps):.1f}" + chr(176) + "F - "
                  f"{max(all_temps):.1f}" + chr(176) + "F")
    else:
        _tmp_o = "--"
    c.drawCentredString(PAGE_W / 2, ovr_y - 0.35 * inch,
                        f"Overall Indoor Temp: " + _tmp_o)
    _pres_o = (f"{min(all_pres):.2f} - {max(all_pres):.2f} inHg"
               if all_pres else "--")
    c.drawCentredString(PAGE_W / 2, ovr_y - 0.70 * inch,
                        f"Overall Pressure: " + _pres_o)

    c.setFillColor(LABEL_TINT)
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(PAGE_W / 2, ovr_y - 1.25 * inch,
                        "Values recorded by the SunRADON monitor "
                        "during the test")


# ---- Outdoor weather page ------------------------------------------------
def _draw_outdoor_weather_page(c, data, weather):
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Header
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 0.85 * inch,
                        "Outdoor Weather During Test")
    c.setFont("Helvetica-Bold", 12)
    _hdr_loc = (f"ZIP {data['zip_code']}   " if data.get("zip_code")
                else f"{data.get('address_line2', '')}   ")
    c.drawCentredString(PAGE_W / 2, PAGE_H - 1.2 * inch,
                        _hdr_loc
                        + f"{data['start_dt'].strftime('%-m/%-d/%y')} - "
                        + f"{data['end_dt'].strftime('%-m/%-d/%y')}")

    if not weather:
        c.setFillColor(LABEL_TINT)
        c.setFont("Helvetica-Oblique", 12)
        c.drawCentredString(PAGE_W / 2, PAGE_H / 2,
                            "Outdoor weather data could not be retrieved.")
        c.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 18,
                            "(Check internet connection.)")
        return

    # Daily summary cards
    days = weather["daily"]
    n = len(days)
    if n > 0:
        total_w = PAGE_W - 1.5 * inch
        left_x = 0.75 * inch
        col_w = total_w / n
        col_top = PAGE_H - 1.7 * inch

        for i, d in enumerate(days):
            cx = left_x + i * col_w + col_w / 2
            dt = datetime.combine(d["date"], datetime.min.time())
            c.setFillColor(white)
            c.setFont("Helvetica-Bold", 13)
            c.drawCentredString(cx, col_top, dt.strftime("%a, %b %-d"))

            _draw_weather_icon(c, cx, col_top - 0.45 * inch, d["code"])

            c.setFillColor(white)
            c.setFont("Helvetica", 12)
            c.drawCentredString(cx, col_top - 0.95 * inch,
                                f"Hi: {int(d['tmax'])}" + chr(176) + "F")
            c.drawCentredString(cx, col_top - 1.13 * inch,
                                f"Lo: {int(d['tmin'])}" + chr(176) + "F")

            c.setFillColor(LABEL_TINT)
            c.setFont("Helvetica-Oblique", 9)
            c.drawCentredString(cx, col_top - 1.40 * inch, "Precip")
            c.setFillColor(white)
            c.setFont("Helvetica", 11)
            c.drawCentredString(cx, col_top - 1.58 * inch,
                                f"{d['precip']:.2f}\"")

        c.setStrokeColor(SEP_BLUE)
        c.setLineWidth(1.2)
        for i in range(1, n):
            x = left_x + i * col_w
            c.line(x, col_top - 1.75 * inch, x, col_top + 0.15 * inch)

    # Outdoor chart fills the rest of the page
    chart_buf = render_outdoor_chart(weather)
    if chart_buf is not None:
        chart_x = MARGIN + 0.3 * inch
        chart_top = PAGE_H - 3.7 * inch
        chart_h = chart_top - MARGIN - 0.5 * inch
        chart_w = PAGE_W - 2 * MARGIN - 0.6 * inch
        c.setFillColor(white)
        c.rect(chart_x, MARGIN + 0.5 * inch, chart_w, chart_h,
               fill=1, stroke=0)
        c.drawImage(_img_reader(chart_buf),
                    chart_x + 2, MARGIN + 0.5 * inch + 2,
                    chart_w - 4, chart_h - 4, preserveAspectRatio=True,
                    mask="auto")

    # Bottom note
    c.setFillColor(LABEL_TINT)
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(PAGE_W / 2, MARGIN + 0.25 * inch,
                        "Outdoor weather sourced from Open-Meteo "
                        "historical archive")


def _draw_weather_icon(c, cx, cy, code):
    """Draw a small weather icon at (cx, cy) on the canvas."""
    try:
        # Sunny / clear
        if code in (0, 1):
            c.setFillColor(HexColor("#f4c430"))
            c.circle(cx, cy, 12, fill=1, stroke=0)
        # Partly cloudy
        elif code in (2, 3):
            c.setFillColor(HexColor("#f4c430"))
            c.circle(cx - 6, cy + 4, 9, fill=1, stroke=0)
            c.setFillColor(HexColor("#bbbbbb"))
            c.ellipse(cx - 4, cy - 8, cx + 14, cy + 4, fill=1, stroke=0)
        # Fog
        elif 45 <= code <= 48:
            c.setFillColor(HexColor("#cccccc"))
            for dy in (-4, 0, 4):
                c.rect(cx - 14, cy + dy - 1, 28, 2, fill=1, stroke=0)
        # Rain / drizzle / showers
        elif (51 <= code <= 67) or (80 <= code <= 82):
            c.setFillColor(HexColor("#8aa8c8"))
            c.ellipse(cx - 14, cy - 4, cx + 14, cy + 8, fill=1, stroke=0)
            c.setStrokeColor(HexColor("#4a90e2"))
            c.setLineWidth(2)
            for dx in (-8, 0, 8):
                c.line(cx + dx, cy - 6, cx + dx - 3, cy - 12)
        # Snow
        elif 71 <= code <= 77:
            c.setFillColor(HexColor("#dddddd"))
            c.ellipse(cx - 12, cy - 4, cx + 12, cy + 8, fill=1, stroke=0)
            c.setFillColor(white)
            for dx in (-7, 0, 7):
                c.circle(cx + dx, cy - 9, 1.5, fill=1, stroke=0)
        # Thunderstorm
        elif 95 <= code <= 99:
            c.setFillColor(HexColor("#666666"))
            c.ellipse(cx - 14, cy - 4, cx + 14, cy + 8, fill=1, stroke=0)
            c.setFillColor(YELLOW)
            p = c.beginPath()
            p.moveTo(cx - 2, cy - 4)
            p.lineTo(cx - 6, cy - 12)
            p.lineTo(cx, cy - 10)
            p.lineTo(cx - 4, cy - 18)
            p.lineTo(cx + 6, cy - 8)
            p.lineTo(cx, cy - 10)
            p.lineTo(cx + 4, cy - 4)
            p.close()
            c.drawPath(p, fill=1, stroke=0)
        # Default cloudy
        else:
            c.setFillColor(HexColor("#bbbbbb"))
            c.ellipse(cx - 14, cy - 4, cx + 14, cy + 8, fill=1, stroke=0)
    except Exception:
        # If anything fails, just draw a simple circle
        c.setFillColor(HexColor("#bbbbbb"))
        c.circle(cx, cy, 10, fill=1, stroke=0)


# ---- EPA reference page --------------------------------------------------
def _draw_epa_reference_page(c, data):
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    table_left = MARGIN + 0.2 * inch
    table_right = PAGE_W - MARGIN - 0.2 * inch
    table_width = table_right - table_left
    split_x = table_left + table_width * 0.45

    top_y = PAGE_H - 1.2 * inch
    row_h = 0.7 * inch
    gap = 0.2 * inch
    header_h = row_h * 0.55

    c.setFillColor(YELLOW)
    c.rect(table_left, top_y, table_width, header_h, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(table_left + (split_x - table_left) / 2,
                        top_y + 0.15 * inch, "Radon Levels")
    c.drawCentredString(split_x + (table_right - split_x) / 2,
                        top_y + 0.15 * inch, "EPA Recommended Action")

    rows = [
        ("0.0 pCiL -1.9 pCi/L",
         "Retest every 2 years,|preferably in a different season"),
        ("2.0 pCi/L - 3.9 pCi/L",
         "Consider Fixing Your Home,|Retest every 2 years"),
        ("4.0 pCi/L and Above",
         "Fix the Home,|Continue to retest every 2 years|post remediation"),
    ]
    ry = top_y - row_h - gap
    _caution_page = data.get("caution", False)
    for level, action in rows:
        c.setFillColor(LEVEL_BLUE)
        c.rect(table_left, ry, split_x - table_left, row_h, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 13)
        if _caution_page and level.startswith("2.0"):
            ast_w = c.stringWidth("*", "Helvetica-Bold", 13)
            lvl_w = c.stringWidth(level, "Helvetica-Bold", 13)
            cell_cx = table_left + (split_x - table_left) / 2
            start_x = cell_cx - (ast_w + lvl_w) / 2
            c.setFillColor(CAUTION_ORANGE)
            c.drawString(start_x, ry + row_h / 2 - 4, "*")
            c.setFillColor(white)
            c.drawString(start_x + ast_w, ry + row_h / 2 - 4, level)
        else:
            c.setFillColor(white)
            c.drawCentredString(table_left + (split_x - table_left) / 2,
                                ry + row_h / 2 - 4, level)
        c.setFillColor(LEVEL_BLUE)
        c.rect(split_x, ry, table_right - split_x, row_h, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 11)
        lines = action.split("|")
        line_y = ry + row_h / 2 + (len(lines) - 1) * 6 - 3
        for line in lines:
            c.drawCentredString(split_x + (table_right - split_x) / 2,
                                line_y, line)
            line_y -= 13
        ry -= row_h + gap

    avg = data["epa_average"]
    below = avg is not None and avg < 4.0
    prose_y = ry - 0.4 * inch

    c.setFillColor(white)
    c.setFont("Helvetica", 11)
    if below and data.get("caution"):
        # CAUTION: rich-formatted intro paragraph + WHO sentence
        x_p = MARGIN + 0.2 * inch
        # Line 1: '...averaged below the EPA action level of' with bold+underlined 'below'
        c.setFont("Helvetica", 11)
        seg_a = "The radon levels inside this home averaged "
        seg_b = "below"
        seg_c = " the EPA action level of"
        c.drawString(x_p, prose_y, seg_a)
        xa = x_p + c.stringWidth(seg_a, "Helvetica", 11)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(xa, prose_y, seg_b)
        seg_b_w = c.stringWidth(seg_b, "Helvetica-Bold", 11)
        c.setStrokeColor(white); c.setLineWidth(0.6)
        c.line(xa, prose_y - 1.5, xa + seg_b_w, prose_y - 1.5)
        c.setFont("Helvetica", 11)
        c.drawString(xa + seg_b_w, prose_y, seg_c)
        prose_y -= 14
        # Line 2: '4.0 pCi/L but within * Cautionary Levels...'
        seg_d = "4.0 pCi/L"
        seg_e = " but within "
        seg_f = "* Cautionary Levels"
        seg_g = " during this testing period. Using the above"
        c.drawString(x_p, prose_y, seg_d)
        seg_d_w = c.stringWidth(seg_d, "Helvetica", 11)
        c.line(x_p, prose_y - 1.5, x_p + seg_d_w, prose_y - 1.5)
        c.drawString(x_p + seg_d_w, prose_y, seg_e)
        seg_e_w = c.stringWidth(seg_e, "Helvetica", 11)
        c.setFillColor(CAUTION_ORANGE)
        c.setFont("Helvetica-Oblique", 11)
        c.drawString(x_p + seg_d_w + seg_e_w, prose_y, seg_f)
        seg_f_w = c.stringWidth(seg_f, "Helvetica-Oblique", 11)
        c.setFillColor(white)
        c.setFont("Helvetica", 11)
        c.drawString(x_p + seg_d_w + seg_e_w + seg_f_w, prose_y, seg_g)
        prose_y -= 14
        # Lines 3-4
        for line in [
            "chart please note the strongly recommended actions by the U.S. Environmental",
            "Protection Agency (EPA) and the Surgeon General.",
        ]:
            c.drawString(x_p, prose_y, line)
            prose_y -= 14
        # WHO paragraph: main sentence + smaller italic parenthetical
        prose_y -= 8
        c.setFont("Helvetica", 11)
        who_main = "The World Health Organization has an action level of 2.7 pCi/L."
        c.drawString(x_p, prose_y, who_main)
        who_main_w = c.stringWidth(who_main, "Helvetica", 11)
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(x_p + who_main_w, prose_y, " (The most noteworthy")
        prose_y -= 11
        for line in [
            "recommendation of the 2009 WHO Handbook On Indoor Radon - A Public Health Perspective",
            "is that country reference levels for radon should be set at 2.7 pCi/L (picocuries per liter),",
            "if possible, or as-low-as-reasonably-achievable…)",
        ]:
            c.drawString(x_p, prose_y, line)
            prose_y -= 11
        c.setFont("Helvetica", 11)
    elif below:
        for line in [
            "The radon levels inside this home averaged below the EPA action level of",
            "4.0 pCi/L during this testing period. This is great news! Using the above chart",
            "please note the strongly recommended actions by the U.S. Environmental",
            "Protection Agency (EPA) and the Surgeon General.",
        ]:
            c.drawString(MARGIN + 0.2 * inch, prose_y, line)
            prose_y -= 14
    else:
        # FAIL: line 1 has "ABOVE" rendered bold + underlined inline.
        x = MARGIN + 0.2 * inch
        seg1a = "The radon levels inside this home averaged "
        seg1b = "ABOVE"
        seg1c = " the EPA action level of"
        c.setFont("Helvetica", 11)
        c.drawString(x, prose_y, seg1a)
        x_after_a = x + c.stringWidth(seg1a, "Helvetica", 11)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x_after_a, prose_y, seg1b)
        seg1b_w = c.stringWidth(seg1b, "Helvetica-Bold", 11)
        c.setStrokeColor(white)
        c.setLineWidth(0.6)
        c.line(x_after_a, prose_y - 1.5,
               x_after_a + seg1b_w, prose_y - 1.5)
        c.setFont("Helvetica", 11)
        c.drawString(x_after_a + seg1b_w, prose_y, seg1c)
        prose_y -= 14
        for line in [
            "4.0 pCi/L during this testing period. Using the above chart please note the",
            "strongly recommended actions by the U.S. Environmental Protection Agency",
            "(EPA) and the Surgeon General.",
        ]:
            c.drawString(MARGIN + 0.2 * inch, prose_y, line)
            prose_y -= 14

        # FAIL-only referral paragraph
        prose_y -= 10
        for line in [
            "Though elevated levels can pose a health risk, reducing the radon levels in",
            "your breathing space is available and effective. Your radon measurement",
            "specialist is happy to refer you to trusted remediation technicians in the",
            "RVA area as well as remain a resource to you during this process.",
        ]:
            c.drawString(MARGIN + 0.2 * inch, prose_y, line)
            prose_y -= 14

    prose_y -= 10
    for line in [
        "Radon is the leading cause of lung cancer in non-smokers. Smokers and former",
        "smokers are at especially high risk. The United States average indoor radon level is",
        "approximately 1.3 pCi/L.  The longer the exposure to elevated radon levels the",
        "higher the health risk.  The higher the radon levels the greater the health risk.",
    ]:
        c.drawString(MARGIN + 0.2 * inch, prose_y, line)
        prose_y -= 14

    prose_y -= 15
    website = COMPANY["website"]
    c.drawString(MARGIN + 0.2 * inch, prose_y,
                 "For more information about radon and a downloadable "
                 "brochure please go to")
    prose_y -= 14
    c.setFillColor(LINK_BLUE)
    c.drawString(MARGIN + 0.2 * inch, prose_y, website)
    c.line(MARGIN + 0.2 * inch, prose_y - 1,
           MARGIN + 0.2 * inch +
           c.stringWidth(website, "Helvetica", 11),
           prose_y - 1)

    prose_y -= 0.5 * inch
    c.setFillColor(white)
    c.setFont("Helvetica", 11)
    c.drawString(MARGIN + 0.2 * inch, prose_y,
                 "Additional State and National Radon Information Sources:")
    prose_y -= 0.35 * inch
    c.drawString(MARGIN + 0.2 * inch, prose_y, "USEPA Radon Program:")
    c.setFillColor(LINK_BLUE)
    c.drawString(MARGIN + 2.5 * inch, prose_y, "EPA-Gov/radon.com")
    c.setFillColor(white)
    prose_y -= 14
    c.drawString(MARGIN + 2.5 * inch, prose_y, "800-767-7236")
    prose_y -= 0.3 * inch
    c.drawString(MARGIN + 0.2 * inch, prose_y, "VDH-ORH Indoor")
    c.drawString(MARGIN + 0.2 * inch, prose_y - 14, "Radon Program:")
    c.setFillColor(LINK_BLUE)
    c.drawString(MARGIN + 2.5 * inch, prose_y, "VDH.Virginia.gov")
    c.setFillColor(white)
    c.drawString(MARGIN + 2.5 * inch, prose_y - 14, "804-864-8150")


# ---- Shared helpers -------------------------------------------------------
def _draw_page_header(c, title, subtitle=None, smaller=False):
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 28 if not smaller else 20)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 0.8 * inch, title)
    if subtitle:
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 1.05 * inch, subtitle)


def _draw_page_footer(c, data):
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(black)
    c.drawCentredString(PAGE_W / 2, 0.75 * inch,
                        f"Test Result: {data['result'].title()}")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(MARGIN, 0.5 * inch, "Test Location:")
    c.setFont("Helvetica", 9)
    c.drawString(MARGIN + 0.9 * inch, 0.5 * inch, data["address_line1"])
    c.drawString(MARGIN + 0.9 * inch, 0.38 * inch, data["address_line2"])
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(PAGE_W - MARGIN, 0.5 * inch, "Inspection Report Date:")
    c.setFont("Helvetica", 9)
    c.drawRightString(PAGE_W - MARGIN, 0.38 * inch,
                      data["end_dt"].strftime("%m/%d/%Y"))


# ===========================================================================
# CLI
# ===========================================================================
def generate_report_number(data):
    """R + month + day + 2-digit year + first letter of customer LAST name."""
    name = data.get("client_name", "").strip()
    parts = name.split()
    if parts:
        last_name = parts[-1]
        letter = last_name[0].upper()
    else:
        letter = "X"
    return f"R{data['start_dt'].strftime('%-m%-d%y')}{letter}"


def _slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "", s) or "Report"


def main():
    ap = argparse.ArgumentParser(description="Generate branded radon report")
    ap.add_argument("input_pdf", help="Raw SunRADON report PDF")
    ap.add_argument("house_image", help="Photo of the house (jpg or png)")
    ap.add_argument("-o", "--output", help="Output PDF path", default=None)
    ap.add_argument("--report-number", help="Override report number",
                    default=None)
    args = ap.parse_args()

    input_pdf = Path(args.input_pdf)
    house_image = Path(args.house_image)
    if not input_pdf.exists():
        sys.exit(f"Input PDF not found: {input_pdf}")
    if not house_image.exists():
        sys.exit(f"House image not found: {house_image}")

    print(f"Parsing {input_pdf}...")
    data = parse_sunradon_pdf(input_pdf)
    print(f"  Company: {data['company_name']} -- {data['company_phone']}")
    print(f"  Client: {data['client_name']}")
    print(f"  ZIP: {data['zip_code']}")
    print(f"  Window: {data['start_dt']} -> {data['end_dt']} "
          f"({data['duration_hr']} hr)")
    print(f"  EPA avg: {data['epa_average']} pCi/l  Result: {data['result']}")
    print(f"  {len(data['readings'])} hourly readings")

    print(f"Fetching outdoor weather for {data['zip_code'] or data.get('address_line2') or 'unknown location'}...")
    weather = fetch_outdoor_weather(
        data["zip_code"], data["start_dt"], data["end_dt"],
        address_line2=data.get("address_line2"))
    if weather:
        print(f"  Got {len(weather['daily'])} days of outdoor weather")
    else:
        print("  (outdoor weather unavailable)")

    report_number = args.report_number or generate_report_number(data)
    output = Path(args.output) if args.output else \
        input_pdf.with_name(f"{report_number}_{_slug(data['company_name'])}"
                            f"_Report.pdf")

    print(f"Writing {output}...")
    build_pdf(data, house_image, output, report_number, input_pdf, weather)
    print(f"Done: {output}")


if __name__ == "__main__":
    main()
