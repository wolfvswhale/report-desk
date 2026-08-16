"""Build a synthetic SunRADON-format monitor PDF.

Everything in it is invented: the firm, the homeowner, the street address,
the monitor serial. It exists so the public demo can generate a real report
without putting a real customer's name and address on the internet.

Run:  ./.venv/bin/python make_sample.py
Out:  ../public/samples/sample-monitor-data.pdf
"""
import math
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

SAMPLES = Path(__file__).resolve().parent.parent / "public" / "samples"
OUT = SAMPLES / "sample-monitor-data.pdf"
HOUSE_OUT = SAMPLES / "sample-house.jpg"

FIRM = "Cardinal Radon Services"
FIRM_ADDR = "5120 Harbour Pointe Drive"
FIRM_CITY = "Midlothian, VA 23113"
FIRM_PHONE = "8045550142"          # 555-01xx is the reserved fictional range

CLIENT = "Harold Vance"
ADDR1 = "1400 Sample Ridge Court"
ADDR2 = "Midlothian, VA 23113"
ROOM = "Basement Family Room"

MODEL = "1028XP"
SERIAL = "0000004242"
CAL_DUE = "03/01/2027"

START = datetime(2026, 8, 11, 9, 0)
HOURS = 48


def readings():
    """Plausible 48-hour run: overnight rises, daytime dips."""
    rows = []
    for i in range(HOURS):
        dt = START + timedelta(hours=i + 1)
        hour = dt.hour
        base = 2.9 + 1.15 * math.cos((hour - 4) / 24 * 2 * math.pi)
        wobble = 0.16 * math.sin(i * 1.7)
        radon = max(0.4, round(base + wobble, 1))
        temp = round(69.5 + 2.1 * math.sin((hour - 15) / 24 * 2 * math.pi), 1)
        pres = round(29.82 + 0.06 * math.sin(i / 9), 2)
        humid = int(46 + 5 * math.sin((hour - 6) / 24 * 2 * math.pi))
        rows.append((dt, radon, temp, pres, humid))
    return rows


ROWS = readings()
AVG = round(sum(r[1] for r in ROWS) / len(ROWS), 1)
LO = min(r[1] for r in ROWS)
HI = max(r[1] for r in ROWS)
END = START + timedelta(hours=HOURS)


def chart_png():
    fig, ax = plt.subplots(figsize=(8.6, 3.5), dpi=150)
    xs = [r[0] for r in ROWS]
    ys = [r[1] for r in ROWS]
    ax.plot(xs, ys, color="#1a3a6c", linewidth=1.8)
    ax.fill_between(xs, ys, color="#1a3a6c", alpha=0.10)
    ax.axhline(4.0, color="#d32f2f", linewidth=1.2, linestyle="--")
    ax.text(xs[1], 4.06, "EPA action level 4.0 pCi/L", color="#d32f2f", fontsize=8)
    ax.set_ylim(0, max(5.0, HI + 1))
    ax.set_ylabel("pCi/L", fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
    ax.tick_params(labelsize=8)
    for label in ax.get_xticklabels():
        label.set_rotation(20)
        label.set_horizontalalignment("right")
    ax.grid(True, color="#dddddd", linewidth=0.6)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def line(c, y, text, size=9, bold=False, x=0.7 * inch):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, text)
    return y - (size + 4)


def page_one(c):
    y = 10.4 * inch
    y = line(c, y, FIRM, size=14, bold=True)
    y = line(c, y, FIRM_ADDR)
    y = line(c, y, FIRM_CITY)
    y = line(c, y, FIRM_PHONE)
    y -= 14

    y = line(c, y, "Test Location:", bold=True)
    y = line(c, y, CLIENT)
    y = line(c, y, ADDR1)
    y = line(c, y, ADDR2)
    y -= 14

    y = line(c, y, "Test Summary", size=11, bold=True)
    y = line(c, y, "CRM Location: Start Stop Interval Duration")
    y = line(
        c, y,
        f"{START.strftime('%m/%d/%Y')} {START.strftime('%-I:%M %p')} "
        f"{END.strftime('%m/%d/%Y')} {END.strftime('%-I:%M %p')} "
        f"1 hr {HOURS} hr",
    )
    y = line(c, y, f"Location: {ROOM}")
    y -= 10

    y = line(c, y, f"SunRADON CRM: {MODEL}")
    y = line(c, y, f"Serial Number: {SERIAL}")
    y = line(c, y, f"Next Calibration: {CAL_DUE}")
    y -= 10

    y = line(c, y, "Overall Average:")
    y = line(c, y, f"{AVG} pCi/l")
    y = line(c, y, "EPA Average:")
    y = line(c, y, f"{AVG} pCi/l")
    y -= 6
    y = line(c, y, f"Test Result: {'Fail' if AVG >= 4.0 else 'Pass'}", bold=True)
    y -= 10
    y = line(c, y, f"Highest: {HI} pCi/l    Lowest: {LO} pCi/l")
    y -= 18
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(0.7 * inch, y, "Sample file. Firm, homeowner, address and serial number are invented.")


def page_two(c):
    from reportlab.lib.utils import ImageReader

    c.setFont("Helvetica-Bold", 12)
    c.drawString(0.7 * inch, 10.4 * inch, "Radon Concentration vs. Time")
    img = ImageReader(chart_png())
    width = 7.1 * inch
    height = width * (3.5 / 8.6)
    c.drawImage(img, 0.7 * inch, 10.4 * inch - height - 0.35 * inch,
                width=width, height=height, mask="auto")


def data_pages(c):
    rows_per_page = 40
    chunks = [ROWS[i:i + rows_per_page] for i in range(0, len(ROWS), rows_per_page)]
    for chunk in chunks:
        c.showPage()
        c.setFont("Helvetica-Bold", 11)
        c.drawString(0.7 * inch, 10.4 * inch, "Test Data")
        c.setFont("Helvetica", 8)
        c.drawString(0.7 * inch, 10.15 * inch,
                     "Date/Time            Radon   Temp   Press   Hum  Flag")
        y = 9.9 * inch
        for dt, radon, temp, pres, humid in chunk:
            c.drawString(
                0.7 * inch, y,
                f"{dt.strftime('%m/%d/%y')} {dt.strftime('%-I:%M %p')} "
                f"{radon} {temp} {pres} {humid} -"
            )
            y -= 0.19 * inch


def house_illustration():
    """A drawn house, not a photograph of anyone's actual home."""
    from PIL import Image, ImageDraw

    W, H = 1400, 950
    sky, grass = (206, 222, 236), (150, 172, 128)
    wall, roof = (222, 214, 199), (92, 82, 74)
    trim, glass, door = (250, 250, 248), (120, 148, 168), (108, 76, 58)

    img = Image.new("RGB", (W, H), sky)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 640, W, H], fill=grass)

    d.rectangle([330, 400, 1070, 700], fill=wall)
    d.polygon([(290, 405), (700, 175), (1110, 405)], fill=roof)
    d.rectangle([610, 520, 730, 700], fill=door)
    d.rectangle([610, 520, 730, 700], outline=trim, width=6)

    for x in (410, 830, 950):
        d.rectangle([x, 470, x + 110, 580], fill=glass)
        d.rectangle([x, 470, x + 110, 580], outline=trim, width=6)
        d.line([(x + 55, 470), (x + 55, 580)], fill=trim, width=4)
        d.line([(x, 525), (x + 110, 525)], fill=trim, width=4)

    d.rectangle([1160, 520, 1200, 700], fill=(96, 78, 62))
    d.ellipse([1080, 380, 1290, 590], fill=(112, 138, 96))
    d.ellipse([120, 430, 300, 610], fill=(112, 138, 96))
    d.rectangle([200, 560, 226, 700], fill=(96, 78, 62))
    d.rectangle([560, 700, 790, H], fill=(196, 192, 184))

    img.save(HOUSE_OUT, quality=88)
    print(f"wrote {HOUSE_OUT}")


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    house_illustration()
    c = canvas.Canvas(str(OUT), pagesize=letter)
    page_one(c)
    c.showPage()
    page_two(c)
    data_pages(c)
    c.save()
    print(f"wrote {OUT}")
    print(f"  {HOURS} readings, average {AVG} pCi/L, range {LO}-{HI}")


if __name__ == "__main__":
    main()
