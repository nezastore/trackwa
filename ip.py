#!/usr/bin/env python3
# IP Track Bot — Modern UI + One-tap Copy (WebApp)
# pip install python-telegram-bot==20.4 requests

import logging, re, requests, ipaddress, secrets, string, base64, urllib.parse
from requests.utils import requote_uri
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# ========== CONFIG ==========
TG_TOKEN = "8057275722:AAEZBhdXs14tJvCN4_JtIE5N8C49hlq1E6A"
IP_API_URL = ("http://ip-api.com/json/{}"
              "?fields=status,message,query,country,regionName,city,isp,as,lat,lon,reverse,timezone")
DEFAULT_PASSLEN = 24
WEBAPP_URL = "https://ajurr.net/infoip/"   # ← URL WebApp kamu (HTTPS)
# ============================

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("iptrack")

# ---------- Utils ----------
MDV2_SPECIALS = r'([_\*\[\]\(\)~`>\#\+\-\=\|\{\}\.\!])'
def tg_escape(s: str) -> str: return re.sub(MDV2_SPECIALS, r'\\\1', s)

def generate_password_strict(n=DEFAULT_PASSLEN) -> str:
    U, L, D, S = string.ascii_uppercase, string.ascii_lowercase, string.digits, "!@#$%^&*()-_=+[]{}:;,.?/<>"
    if n < 8: n = 8
    out = [secrets.choice(U), secrets.choice(L), secrets.choice(D), secrets.choice(S), secrets.choice(S)]
    pool = U + L + D + S
    for _ in range(n - len(out)):
        c = secrets.choice(pool)
        out.append(c if c != out[-1] else secrets.choice(pool.replace(c, "")))
    secrets.SystemRandom().shuffle(out)
    # hindari duplikat berdempetan
    fixed = [out[0]]
    for ch in out[1:]:
        fixed.append(secrets.choice(pool.replace(fixed[-1], "")) if ch == fixed[-1] else ch)
    return "".join(fixed)

def extract_ips_from_text(text: str):
    found = set()
    for tok in text.replace(",", " ").replace(";", " ").replace("|", " ").split():
        t = tok.strip("[]()").rstrip(".,:;")
        if "%" in t: t = t.split("%", 1)[0]
        try:
            found.add(str(ipaddress.ip_address(t)))
        except Exception:
            pass
    return sorted(found)

def fetch_ip(ip: str):
    try:
        r = requests.get(requote_uri(IP_API_URL.format(ip)), timeout=8).json()
    except Exception as e:
        logger.error("API error: %s", e); return {"error": f"Gagal koneksi API untuk {ip}"}
    if r.get("status") != "success":
        return {"error": f"{ip} → {r.get('message','unknown')}"}
    return {
        "ip": r.get("query") or "-",
        "version": "IPv6" if ":" in (r.get("query") or "") else "IPv4",
        "country": r.get("country") or "-",
        "region": r.get("regionName") or "-",
        "city": r.get("city") or "-",
        "isp": r.get("isp") or "-",
        "asn": r.get("as") or "-",
        "reverse": r.get("reverse") or "-",
        "tz": r.get("timezone") or "-",
        "coords": f"{r.get('lat')}, {r.get('lon')}",
    }

def format_ip_message(d: dict) -> str:
    # Semua nilai di-escape agar aman untuk MarkdownV2
    ip = tg_escape(d["ip"]); ver = tg_escape(d["version"])
    country = tg_escape(d["country"]); region = tg_escape(d["region"]); city = tg_escape(d["city"])
    isp = tg_escape(d["isp"]); asn = tg_escape(d["asn"]); rev = tg_escape(d["reverse"])
    tz = tg_escape(d["tz"]); coords = tg_escape(d["coords"])
    # Tampilan modern: judul tebal + bullet icons, tanpa backtick yg mengganggu
    return (
        f"**IP Report** · *{ver}*\n"
        f"🧭 **IP**: {ip}\n"
        f"🏳️ **Country**: {country}\n"
        f"🗺️ **Region**: {region}\n"
        f"🏙️ **City**: {city}\n"
        f"🏢 **ISP**: {isp}\n"
        f"📡 **ASN**: {asn}\n"
        f"🖥️ **Reverse DNS**: {rev}\n"
        f"⏱️ **Timezone**: {tz}\n"
        f"📍 **Coords**: {coords}"
    )

START_TEXT = (
    "**IP TRACK – NezaFx**\n"
    "• Kirim/paste IP (IPv4/IPv6) atau baris log berisi IP.\n"
    "• Bot menampilkan: Country, Region, City, ISP, ASN, Reverse DNS, Timezone, Coords.\n"
    "• Password kuat dikirim terpisah + tombol *Copy* (1-tap)."
)

# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(tg_escape(START_TEXT), parse_mode="MarkdownV2")

async def auto_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    ips = extract_ips_from_text(text)
    if not ips:
        await update.message.reply_text(tg_escape("⚠️ Tidak ada IP valid ditemukan."), parse_mode="MarkdownV2")
        return

    for ip in ips:
        data = fetch_ip(ip)
        if "error" in data:
            await update.message.reply_text(tg_escape("❌ " + data["error"]), parse_mode="MarkdownV2")
            continue

        # 1) Info modern & rapi (MarkdownV2)
        await update.message.reply_text(format_ip_message(data), parse_mode="MarkdownV2")

        # 2) Password plain + tombol WebApp (1-tap copy)
        pwd = generate_password_strict()
        b64 = base64.urlsafe_b64encode(pwd.encode()).decode()
        url = f"{WEBAPP_URL}?t={urllib.parse.quote_plus(b64)}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Copy to Clipboard", web_app=WebAppInfo(url=url))]])
        await update.message.reply_text(f"🔐 Password:\n{pwd}", reply_markup=kb)  # tanpa parse_mode → aman

# ---------- Main ----------
def main():
    app = ApplicationBuilder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_process))
    print("✅ Bot berjalan (auto on paste, 1-tap copy via WebApp).")
    app.run_polling()

if __name__ == "__main__":
    main()
