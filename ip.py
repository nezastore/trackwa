#!/usr/bin/env python3
# IP Track Bot — Modern UI + One-tap Copy via code block (no HTML)
# pip install python-telegram-bot==20.4 requests

import logging, re, requests, ipaddress, secrets, string, urllib.parse
from requests.utils import requote_uri
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# ========== CONFIG ==========
TG_TOKEN = "8057275722:AAEZBhdXs14tJvCN4_JtIE5N8C49hlq1E6A"
IP_API_URL = (
    "http://ip-api.com/json/{}"
    "?fields=status,message,query,country,countryCode,regionName,city,isp,as,lat,lon,reverse,timezone"
)
DEFAULT_PASSLEN = 24
# ============================

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("iptrack")

# ---------- Utils ----------
MDV2_SPECIALS = r'([_\*\[\]\(\)~`>\#\+\-\=\|\{\}\.\!])'
def tg_escape(s: str) -> str: return re.sub(MDV2_SPECIALS, r'\\\1', s)

def flag_emoji(cc: str) -> str:
    if not cc or len(cc) != 2: return ""
    base = 127397
    return chr(ord(cc[0].upper()) + base) + chr(ord(cc[1].upper()) + base)

def generate_password_strict(n=DEFAULT_PASSLEN) -> str:
    U, L, D, S = string.ascii_uppercase, string.ascii_lowercase, string.digits, "!@#$%^&*()-_=+[]{}:;,.?/<>"
    # NOTE: tidak memasukkan backtick (`) agar aman di code block
    if n < 12: n = 12
    out = [secrets.choice(U), secrets.choice(L), secrets.choice(D), secrets.choice(S), secrets.choice(S)]
    pool = U + L + D + S
    for _ in range(n - len(out)):
        c = secrets.choice(pool)
        out.append(c if c != out[-1] else secrets.choice(pool.replace(c, "")))
    secrets.SystemRandom().shuffle(out)
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
        logger.error("API error: %s", e); return {"error": f"{ip}: gagal koneksi API"}
    if r.get("status") != "success":
        return {"error": f"{ip}: {r.get('message','unknown')}"}
    return {
        "ip": r.get("query") or "-",
        "ver": "IPv6" if ":" in (r.get("query") or "") else "IPv4",
        "country": r.get("country") or "-",
        "cc": r.get("countryCode") or "",
        "region": r.get("regionName") or "-",
        "city": r.get("city") or "-",
        "isp": r.get("isp") or "-",
        "asn": r.get("as") or "-",
        "rev": r.get("reverse") or "-",
        "tz": r.get("timezone") or "-",
        "lat": r.get("lat"),
        "lon": r.get("lon"),
    }

def format_ip_message(d: dict) -> str:
    flg = flag_emoji(d["cc"])
    title = f"*IP Report* · _{tg_escape(d['ver'])}_"
    country_line = (flg + " " + tg_escape(d["country"])) if flg else tg_escape(d["country"])
    coords = f"{d['lat']}, {d['lon']}"
    return (
        f"{title}\n"
        f"🧭 *IP*: `{d['ip']}`\n"
        f"🏳️ *Country*: {country_line}\n"
        f"🗺️ *Region*: {tg_escape(d['region'])}\n"
        f"🏙️ *City*: {tg_escape(d['city'])}\n"
        f"🏢 *ISP*: {tg_escape(d['isp'])}\n"
        f"📡 *ASN*: {tg_escape(d['asn'])}\n"
        f"🖥️ *Reverse DNS*: {tg_escape(d['rev'])}\n"
        f"⏱️ *Timezone*: {tg_escape(d['tz'])}\n"
        f"📍 *Coords*: {tg_escape(coords)}"
    )

def action_keyboard(ip: str, lat, lon):
    maps = f"https://maps.google.com/?q={lat},{lon}"
    rdns = f"https://dnschecker.org/reverse-dns.php?query={urllib.parse.quote_plus(ip)}"
    whois = f"https://who.is/whois-ip/ip-address/{urllib.parse.quote_plus(ip)}"
    scamalytics = f"https://scamalytics.com/ip/{urllib.parse.quote_plus(ip)}"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗺️ Maps", url=maps),
            InlineKeyboardButton("🔎 RDNS", url=rdns),
            InlineKeyboardButton("📖 WHOIS", url=whois),
            InlineKeyboardButton("⚠️ Scamalytics", url=scamalytics),
        ]
    ])

# ---------- Text ----------
START_TEXT = (
    "<b>✨ IP TRACK – NezaFx</b>\n\n"
    "<b>Cara pakai</b>:\n"
    "• Paste IP <i>(IPv4/IPv6)</i> atau baris log berisi IP.\n"
    "• Bot menampilkan: <b>Country</b>, <b>Region</b>, <b>City</b>, "
    "<b>ISP</b>, <b>ASN</b>, <b>Reverse DNS</b>, <b>Timezone</b>, <b>Coords</b>.\n"
    "• Password dikirim terpisah sebagai <code>code block</code> — tombol <b>Copy</b> muncul otomatis.\n\n"
    "<b>Quick actions</b>:\n"
    "• 🗺️ Maps  •  🔎 RDNS  •  📖 WHOIS  •  ⚠️ Scamalytics\n\n"
    "<b>Contoh</b>:\n"
    "Kirim: <code>97.229.26.68</code> atau log yang berisi IP.\n\n"
    "<i>Tip: Bisa kirim banyak IP sekaligus (mis. potongan log) — bot memproses satu per satu.</i>"
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

        # 1) Kartu IP + tombol aksi
        await update.message.reply_text(
            format_ip_message(data), parse_mode="MarkdownV2",
            reply_markup=action_keyboard(data["ip"], data["lat"], data["lon"])
        )

        # 2) Password sebagai CODE BLOCK (tombol Copy bawaan Telegram)
        pwd = generate_password_strict()
        await update.message.reply_text(f"🔐 Password:\n```\n{pwd}\n```", parse_mode="MarkdownV2")

# ---------- Main ----------
def main():
    app = ApplicationBuilder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_process))
    print("✅ Bot berjalan (auto on paste · password 1-tap copy via code block).")
    app.run_polling()

if __name__ == "__main__":
    main()
