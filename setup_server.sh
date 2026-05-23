#!/usr/bin/env bash
# setup_server.sh — Run ONCE on a fresh Ubuntu 22.04/24.04 VPS to prepare it
# for the TeleGo bot and GitHub Actions deploys.
#
# Usage:
#   chmod +x setup_server.sh
#   sudo ./setup_server.sh

set -euo pipefail

BOT_USER="${BOT_USER:-ubuntu}"      # OS user that will run the bot
BOT_PATH="${BOT_PATH:-/opt/telego}" # must match BOT_BASE_PATH secret & service file

echo "==> Installing system packages..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    aria2 ffmpeg megatools \
    rsync git curl

echo "==> Creating bot directory: $BOT_PATH"
mkdir -p "$BOT_PATH"
chown "$BOT_USER:$BOT_USER" "$BOT_PATH"

echo "==> Creating credentials env file: /etc/telego/env"
mkdir -p /etc/telego
chmod 700 /etc/telego

# Write env file — fill in real values or edit after running
cat > /etc/telego/env << 'ENV'
# TeleGo bot credentials — keep this file private (chmod 600)
BOT_BASE_PATH=/opt/telego
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
USER_ID=your_telegram_user_id
DUMP_ID=-100your_dump_channel_id
ENV

chmod 600 /etc/telego/env
chown root:root /etc/telego/env
echo "    !! Edit /etc/telego/env with your real credentials before starting !!"

echo "==> Installing systemd service..."
cp "$BOT_PATH/telego.service" /etc/systemd/system/telego.service

# Patch the User= line to match the actual OS user
sed -i "s/^User=.*/User=$BOT_USER/" /etc/systemd/system/telego.service
# Patch WorkingDirectory
sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$BOT_PATH|" /etc/systemd/system/telego.service
# Patch ExecStart to use full python path
PY=$(which python3)
sed -i "s|^ExecStart=.*|ExecStart=$PY -m colab_leecher|" /etc/systemd/system/telego.service

systemctl daemon-reload
systemctl enable telego.service

echo ""
echo "==> Adding deploy public key to $BOT_USER's authorized_keys"
echo "    Paste the PUBLIC key that matches your SSH_PRIVATE_KEY GitHub secret:"
read -rp "    Public key: " PUBKEY
if [[ -n "$PUBKEY" ]]; then
    HOME_DIR=$(eval echo "~$BOT_USER")
    mkdir -p "$HOME_DIR/.ssh"
    echo "$PUBKEY" >> "$HOME_DIR/.ssh/authorized_keys"
    chmod 700 "$HOME_DIR/.ssh"
    chmod 600 "$HOME_DIR/.ssh/authorized_keys"
    chown -R "$BOT_USER:$BOT_USER" "$HOME_DIR/.ssh"
    echo "    Key added."
fi

echo ""
echo "==> Granting bot user passwordless sudo for systemctl restart/daemon-reload"
SUDOERS_LINE="$BOT_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl daemon-reload, /usr/bin/systemctl restart telego.service, /usr/bin/journalctl"
echo "$SUDOERS_LINE" > /etc/sudoers.d/telego
chmod 440 /etc/sudoers.d/telego

echo ""
echo "======================================================"
echo " Setup complete. Next steps:"
echo ""
echo "  1. Edit /etc/telego/env with your real credentials"
echo "  2. Push your code to GitHub to trigger the first deploy"
echo "  3. After deploy completes, start the bot manually once:"
echo "       sudo systemctl start telego.service"
echo "  4. Check logs:"
echo "       journalctl -u telego.service -f"
echo "======================================================"
