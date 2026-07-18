#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
# CineGram — Oracle Cloud Free Tier Setup Script
# Run once on a fresh Ubuntu 22.04/24.04 ARM VM as root or with sudo.
# ══════════════════════════════════════════════════════════════════════════
set -euo pipefail

APP_USER="ubuntu"
APP_DIR="/home/${APP_USER}/CineGram"
REPO_URL="https://github.com/kevorteg/cinegram-Bot.git"

echo "════════════════════════════════════════════"
echo " CineGram — Oracle Cloud Setup"
echo "════════════════════════════════════════════"

# ── 1. System update ───────────────────────────────────────────────────
echo "[1/7] Updating system packages..."
apt-get update -qq && apt-get upgrade -y -qq

# ── 2. Install Python 3.12 + dependencies ─────────────────────────────
echo "[2/7] Installing Python 3.12 and build tools..."
apt-get install -y -qq python3.12 python3.12-venv python3-pip git curl

# ── 3. Create app user (skip if exists) ────────────────────────────────
echo "[3/7] Ensuring user '${APP_USER}' exists..."
if ! id "${APP_USER}" &>/dev/null; then
    useradd -m -s /bin/bash "${APP_USER}"
    echo "Created user ${APP_USER}"
fi

# ── 4. Clone or pull the repo ──────────────────────────────────────────
echo "[4/7] Setting up CineGram in ${APP_DIR}..."
su - "${APP_USER}" -c "
    if [ -d '${APP_DIR}' ]; then
        cd '${APP_DIR}' && git pull
    else
        git clone '${REPO_URL}' '${APP_DIR}'
    fi
"

# ── 5. Create virtualenv and install requirements ──────────────────────
echo "[5/7] Installing Python dependencies..."
su - "${APP_USER}" -c "
    cd '${APP_DIR}'
    python3.12 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip -q
    pip install -r requirements.txt -q
"

# ── 6. Create .env if it doesn't exist ─────────────────────────────────
echo "[6/7] Checking .env file..."
su - "${APP_USER}" -c "
    cd '${APP_DIR}'
    if [ ! -f .env ]; then
        cp .env.example .env
        echo '⚡ Created .env from .env.example — PLEASE EDIT IT with your credentials:'
        echo '   nano ${APP_DIR}/.env'
    else
        echo '.env already exists — skipping.'
    fi
"

# ── 7. Install systemd service ─────────────────────────────────────────
echo "[7/7] Installing systemd service..."
cp "${APP_DIR}/deploy/cinegram.service" /etc/systemd/system/cinegram.service
systemctl daemon-reload
systemctl enable cinegram
systemctl start cinegram

echo ""
echo "════════════════════════════════════════════"
echo " ✅ Setup complete!"
echo "════════════════════════════════════════════"
echo ""
echo " Next steps:"
echo "   1. Edit .env with your credentials:"
echo "        sudo nano ${APP_DIR}/.env"
echo ""
echo "   2. Restart the bot:"
echo "        sudo systemctl restart cinegram"
echo ""
echo "   3. Check logs:"
echo "        sudo journalctl -u cinegram -f"
echo ""
echo "   4. Check status:"
echo "        sudo systemctl status cinegram"
echo ""
