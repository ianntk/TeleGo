# copyright 2023 © Xron Trix | https://github.com/Xrontrix10
# Torrent / Magnet support — added by editor

import re
import logging
import subprocess
from urllib.parse import urlparse, parse_qs, unquote_plus
from datetime import datetime
from colab_leecher.utility.helper import sizeUnit, status_bar
from colab_leecher.utility.variables import BOT, Aria2c, Paths, Messages, BotTimes


def get_Torrent_Name(link: str) -> str:
    """Extract a human-readable name from a magnet link or return a placeholder."""
    if len(BOT.Options.custom_name) != 0:
        return BOT.Options.custom_name

    if link.startswith("magnet:"):
        try:
            params = parse_qs(urlparse(link).query)
            dn = params.get("dn", [""])[0]
            if dn:
                return unquote_plus(dn)
        except Exception:
            pass
        # Fallback: use the first 8 chars of the info-hash
        btih = re.search(r"btih:([a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", link, re.I)
        if btih:
            return f"Torrent_{btih.group(1)[:8].upper()}"

    return "Torrent Download"


async def torrent_Download(link: str, num: int):
    global BotTimes, Messages

    name_d = get_Torrent_Name(link)
    BotTimes.task_start = datetime.now()
    Messages.status_head = (
        f"<b>🧲 DOWNLOADING TORRENT » </b><i>Link {str(num).zfill(2)}</i>\n\n"
        f"<b>🏷️ Name » </b><code>{name_d}</code>\n"
    )

    command = [
        "aria2c",
        "-x16",
        "--seed-time=0",
        "--seed-ratio=0.0",
        "--enable-dht=true",
        "--dht-listen-port=6881",
        "--enable-peer-exchange=true",
        "--bt-save-metadata=true",
        "--bt-detach-seed-only=true",
        "--follow-torrent=mem",         # keep .torrent in memory, don't save it
        "--summary-interval=1",
        "--max-tries=3",
        "--console-log-level=notice",
        "-d", Paths.down_path,
        link,
    ]

    proc = subprocess.Popen(
        command, bufsize=0, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    Aria2c.link_info = False

    while True:
        output = proc.stdout.readline()
        if output == b"" and proc.poll() is not None:
            break
        if output:
            await on_torrent_output(output.decode("utf-8", errors="replace"))

    exit_code = proc.wait()
    if exit_code != 0:
        error_output = proc.stderr.read().decode("utf-8", errors="replace")
        logging.error(
            f"aria2c torrent failed (code {exit_code}) for: {link}\n{error_output}"
        )


async def on_torrent_output(output: str):
    """
    Parse aria2c's --summary-interval=1 progress lines for BitTorrent downloads.

    Progress line format:
        [#abc123 100MiB/500MiB(20%) CN:5 DL:1.0MiB ETA:7m10s]
    Metadata phase:
        [#abc123 (METADATA) CN:5 DL:2KiB]
    """
    # --- Metadata phase: no total size known yet ---
    if "(METADATA)" in output:
        Aria2c.link_info = False
        await status_bar(
            Messages.status_head,
            "Fetching...",
            0.0,
            "N/A",
            "0B",
            "Fetching Metadata",
            "Aria2c BT 🧲",
        )
        return

    if "ETA:" not in output:
        return

    total_size = ""
    progress_percentage = "0"
    downloaded_bytes = "0B"
    eta = "N/A"

    try:
        parts = output.split()

        # Find the size/progress token — looks like "100MiB/500MiB(20%)"
        size_token = next(
            (p for p in parts if "/" in p and "(" in p and ")" in p), None
        )
        if size_token:
            downloaded_bytes = size_token.split("/")[0]
            right = size_token.split("/")[1]
            total_size = right.split("(")[0]
            pct_str = right[right.find("(") + 1 : right.find(")")]
            pct_nums = re.findall(r"[\d.]+", pct_str)
            progress_percentage = pct_nums[0] if pct_nums else "0"

        # Find ETA token — "ETA:7m10s]" or "ETA:--]"
        eta_token = next((p for p in parts if p.upper().startswith("ETA:")), None)
        if eta_token:
            eta = eta_token.split(":", 1)[1].rstrip("]").strip()

    except Exception as e:
        logging.error(f"Torrent progress parse error: {e}")
        return

    if not total_size:
        return

    # Calculate approximate speed from elapsed time + downloaded bytes
    elapsed = max((datetime.now() - BotTimes.task_start).seconds, 1)

    if elapsed >= 270 and not Aria2c.link_info:
        logging.warning("No torrent download progress after 4.5 min — possibly no seeders.")

    down_nums = re.findall(r"[\d.]+", downloaded_bytes)
    down_units = re.findall(r"[a-zA-Z]+", downloaded_bytes)

    if down_nums and down_units:
        unit_char = down_units[0][0].upper()
        multiplier = {"G": 3, "M": 2, "K": 1}.get(unit_char, 0)
        bytes_done = float(down_nums[0]) * (1024 ** multiplier)
        current_speed = bytes_done / elapsed
        speed_string = f"{sizeUnit(current_speed)}/s"
        Aria2c.link_info = True
    else:
        speed_string = "N/A"

    try:
        percentage = float(progress_percentage)
    except ValueError:
        percentage = 0.0

    await status_bar(
        Messages.status_head,
        speed_string,
        percentage,
        eta,
        downloaded_bytes,
        total_size,
        "Aria2c BT 🧲",
    )
