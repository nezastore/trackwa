#!/usr/bin/env bash
# command.sh — One-shot installer & runner (targets ip.py) — NEZASTORE
set -euo pipefail

# ====== Warna ======
GREEN="\033[1;32m"; BLUE="\033[1;34m"; YELLOW="\033[1;33m"; RED="\033[1;31m"; MAG="\033[1;35m"; CYAN="\033[1;36m"; RESET="\033[0m"

banner() {
  echo -e "${BLUE}============================================================${RESET}"
  echo -e "${GREEN}   ███╗   ██╗███████╗ █████╗ ████████╗ █████╗ ██████╗ ${RESET}"
  echo -e "${GREEN}   ████╗  ██║██╔════╝██╔══██╗╚══██╔══╝██╔══██╗██╔══██╗${RESET}"
  echo -e "${MAG}   ███╔██╗ ██║█████╗  ███████║   ██║   ███████║██████╔╝${RESET}"
  echo -e "${MAG}   ██║╚██╗██║██╔══╝  ██╔══██║   ██║   ██╔══██║██╔══██╗${RESET}"
  echo -e "${YELLOW}   ██║ ╚████║███████╗██║  ██║   ██║   ██║  ██║██║  ██║${RESET}"
  echo -e "${BLUE}============================================================${RESET}"
  echo -e "${CYAN}              NEZASTORE · COMMAND INSTALLER (WIB)${RESET}"
  echo -e "${BLUE}============================================================${RESET}"
}

need_root() {
  if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Jalankan pakai sudo/root.${RESET}"
    exit 1
  fi
}

banner
need_root

# Lokasi kerja = folder file ini berada, menargetkan ip.py di folder yang sama
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}1) Set timezone ke Asia/Jakarta${RESET}"
timedatectl set-timezone Asia/Jakarta || true
echo -e "${GREEN}   Timezone diset WIB${RESET}"

echo -e "${BLUE}2) Update & install base deps (Python, pip, venv, Node, PM2)${RESET}"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv python3-pip python3-distutils \
  curl ca-certificates build-essential apt-transport-https lsb-release gnupg

# Node + PM2
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
  apt-get install -y nodejs
fi
npm install -g pm2@latest
echo -e "${GREEN}   Deps siap (Node: $(node -v), PM2: $(pm2 -v))${RESET}"

echo -e "${BLUE}3) Buat venv & install Python requirements${RESET}"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install python-telegram-bot==20.4 requests
echo -e "${GREEN}   venv siap & deps terpasang${RESET}"

# Pastikan ip.py ada
if [ ! -f "ip.py" ]; then
  echo -e "${RED}ip.py tidak ditemukan di folder ini (${SCRIPT_DIR}). Salin ip.py ke sini dulu.${RESET}"
  exit 1
fi

echo -e "${BLUE}4) Input TG_TOKEN (disembunyikan)${RESET}"
if [ -z "${TG_TOKEN:-}" ]; then
  read -s -p "Masukkan TG_TOKEN: " TG_TOKEN_INPUT
  echo
else
  TG_TOKEN_INPUT="$TG_TOKEN"
fi

if [ -z "$TG_TOKEN_INPUT" ]; then
  echo -e "${RED}TG_TOKEN kosong. Batal.${RESET}"
  exit 1
fi

echo -e "${BLUE}5) Start via PM2 menargetkan ip.py${RESET}"
# Stop dulu jika sudah ada
pm2 delete iptrack >/dev/null 2>&1 || true
# Jalankan dengan env inline agar TG_TOKEN hanya tersimpan di PM2 env
TG_TOKEN="$TG_TOKEN_INPUT" pm2 start ./venv/bin/python --name iptrack -- ./ip.py

pm2 save

# Setup startup systemd
SETUP_CMD=$(pm2 startup systemd -u "$(whoami)" --hp "$(eval echo ~$USER)" | tail -n 1 || true)
if [ -n "$SETUP_CMD" ]; then
  eval "$SETUP_CMD" || true
fi

echo -e "${BLUE}6) Status PM2${RESET}"
pm2 status

echo -e "${GREEN}Selesai!${RESET}"
echo -e "• Jalankan log   : ${MAG}pm2 logs iptrack --lines 200${RESET}"
echo -e "• Restart bot    : ${MAG}pm2 restart iptrack${RESET}"
echo -e "• Stop bot       : ${MAG}pm2 stop iptrack${RESET}"
echo -e "• Hapus dari PM2 : ${MAG}pm2 delete iptrack${RESET}"
echo -e "${YELLOW}WATERMARK: NEZASTORE${RESET}"
echo -e "${BLUE}============================================================${RESET}"
