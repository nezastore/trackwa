#!/usr/bin/env python3
"""
IP Track Bot (Pro UI • Clean Card • Copy-friendly Password)
Dependencies:
  pip install python-telegram-bot==20.4 requests
Run:
  python3 iptrack_bot.py
"""

import logging, re, requests, ipaddress, secrets, string
from requests.utils import requote_uri
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# ---------- CONFIG ----------
TG_TOKEN = "8057275722:AAEZBhdXs14tJvCN4_JtIE5N8C49hlq1E6A"
IP_API_URL = (
    "http://ip-api.com/json/{}"
    "?fields=status,message,query,country,regionName,city,isp,as,lat,lon,reverse,timezone"
)
DEFAULT_PASSLEN = 24
CARD_WIDTH = 52  # lebar kartu monospace
# ----------------------------

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("iptrack")

# ---------- UTIL ----------
MDV2 = r'([_\*\[\]\(\)~`>\#\+\-\=\|\{\}\.\!])'
def tg_escape(text: str) -> str: return re.sub(MDV2, r'\\\1', text)

def generate_password_strict(length=DEFAULT_PASSLEN) -> str:
    uppers, lowers, digits = string.ascii_uppercase, string.ascii_lowercase, string.digits
    symbols = "!@#$%^&*()-_=+[]{}:;,.?/<>"
    if length < 8: length = 8
    base = [
        secrets.choice(uppers), secrets.choice(lowers),
        secrets.choice(digits), secrets.choice(symbols), secrets.choice(symbols)
    ]
    pool = uppers + lowers + digits + symbols
    for _ in range(length - len(base)):
        c = secrets.choice(pool)
        base.append(c if c != base[-1] else secrets.choice(pool.replace(c, "")))
    secrets.SystemRandom().shuffle(base)
    out = [base[0]]
    for ch in base[1:]:
        out.append(secrets.choice(pool.replace(out[-1], "")) if ch == out[-1] else ch)
    return "".join(out)

def extract_ips_from_text(text: str):
    found = set()
    for token in text.replace(",", " ").replace(";", " ").replace("|", " ").split():
        t = token.strip("[]()").rstrip(".,:;")
        if "%" in t: t = t.split("%", 1)[0]
        try:
            found.add(str(ipaddress.ip_address(t)))
        except Exception:
            pass
    return sorted(found)

# --- data fetch & render ---
def fetch_ip_data(ip: str):
    """Return dict with IP data or str error."""
    try:
        js = requests.get(requote_uri(IP_API_URL.format(ip)), timeout=8).json()
    except Exception as e:
        logger.error("API error: %s", e)
        return f"Error: gagal koneksi API untuk {ip}"
    if js.get("status") != "success":
        return f"Error: {ip} → {js.get('message','unknown')}"
    return {
        "ip": js.get("query"),
        "version": "IPv6" if ":" in js.get("query","") else "IPv4",
        "country": js.get("country"),
        "region": js.get("regionName","-"),
        "city": js.get("city","-"),
        "isp": js.get("isp","-"),
        "asn": js.get("as","-"),
        "reverse": js.get("reverse","-"),
        "tz": js.get("timezone","-"),
        "lat": js.get("lat"),
        "lon": js.get("lon"),
    }

def _pad_line(label: str, value: str, width: int):
    line = f" {label:<11}: {value}"
    return line[:width-1] if len(line) >= width-1 else line + " "*(width-1-len(line))

def render_card(data: dict) -> str:
    """Return a neat monospace card inside MarkdownV2 code block."""
    w = CARD_WIDTH
    top    = "┌" + "─"*(w-2) + "┐"
    bottom = "└" + "─"*(w-2) + "┘"
    header = f" IP Insight  •  {data['version']}"
    header_line = "│" + header.center(w-2) + "│"
    lines = [
        _pad_line("IP",        data["ip"], w),
        _pad_line("Country",   data["country"], w),
        _pad_line("Region",    data["region"], w),
        _pad_line("City",      data["city"], w),
        _pad_line("ISP",       data["isp"], w),
        _pad_line("ASN",       data["asn"], w),
        _pad_line("ReverseDNS",data["reverse"], w),
        _pad_line("Timezone",  data["tz"], w),
        _pad_line("Coords",    f"{data['lat']}, {data['lon']}", w),
    ]
    body = "\n".join("│" + ln + "│" for ln in lines)
    card = f"{top}\n{header_line}\n{body}\n{bottom}"
    # wrap as code block (content inside tidak perlu di-escape)
    return f"```\n{card}\n```"

# ---------- TEXT ----------
HELP_TEXT = (
    "┏━━━━━━━━━━━━━━━━━━━━━━┓\n"
    "  🚀 IP TRACK – ANGKASA EDITION\n"
    "┗━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
    "• Paste IP (IPv4/IPv6) atau baris log berisi IP.\n"
    "• Bot menampilkan kartu ringkas: Negara, Kota, ISP, ASN,\n"
    "  Reverse DNS, Timezone, Koordinat.\n"
    "• Setiap IP → password acak & kuat (pesan terpisah untuk mudah copy)."
)

# ---------- HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(tg_escape(HELP_TEXT), parse_mode="MarkdownV2")

async def auto_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    ips = extract_ips_from_text(text)
    if not ips:
        await update.message.reply_text(tg_escape("⚠️ Tidak ada IP valid ditemukan."), parse_mode="MarkdownV2")
        return

    for ip in ips:
        data = fetch_ip_data(ip)
        if isinstance(data, str):
            # error text
            await update.message.reply_text(tg_escape(f"❌ {data}"), parse_mode="MarkdownV2")
            continue

        # 1) KARTU INFO (code block monospace — rapi & profesional)
        card = render_card(data)
        await update.message.reply_text(card, parse_mode="MarkdownV2")

        # 2) PASSWORD (pesan terpisah TANPA parse_mode → copy lebih mulus & bebas karakter spesial)
        pwd = generate_password_strict()
        await update.message.reply_text(f"🔐 Password (copy 1x):\n{pwd}")

# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_process))
    print("✅ Bot berjalan (auto on paste). Tekan Ctrl+C untuk berhenti.")
    app.run_polling()

if __name__ == "__main__":
    main()
