# copyright 2023 © Xron Trix | https://github.com/Xrontrix10
# Torrent / Magnet support — RPC polling mode

import re
import logging
import asyncio
import aiohttp
import subprocess
from urllib.parse import urlparse, parse_qs, unquote_plus
from datetime import datetime
from colab_leecher.utility.helper import sizeUnit, status_bar
from colab_leecher.utility.variables import BOT, Aria2c, Paths, Messages, BotTimes

RPC_PORT   = 6801          # separate port so it doesn't clash with anything
RPC_SECRET = "tg_bot_rpc"
RPC_URL    = f"http://127.0.0.1:{RPC_PORT}/jsonrpc"
TOKEN      = f"token:{RPC_SECRET}"


def get_Torrent_Name(link: str) -> str:
    if BOT.Options.custom_name:
        return BOT.Options.custom_name
    if link.startswith("magnet:"):
        try:
            dn = parse_qs(urlparse(link).query).get("dn", [""])[0]
            if dn:
                return unquote_plus(dn)
        except Exception:
            pass
        m = re.search(r"btih:([a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", link, re.I)
        if m:
            return f"Torrent_{m.group(1)[:8].upper()}"
    return "Torrent Download"


async def _rpc(session: aiohttp.ClientSession, method: str, params: list):
    try:
        async with session.post(
            RPC_URL,
            json={"jsonrpc": "2.0", "id": "bot", "method": method, "params": params},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as r:
            data = await r.json()
            return data.get("result")
    except Exception:
        return None


async def torrent_Download(link: str, num: int):
    global BotTimes, Messages

    name_d = get_Torrent_Name(link)
    BotTimes.task_start = datetime.now()
    Messages.status_head = (
        f"<b>🧲 DOWNLOADING TORRENT » </b><i>Link {str(num).zfill(2)}</i>\n\n"
        f"<b>🏷️ Name » </b><code>{name_d}</code>\n"
    )

    # ── 1. Start aria2c daemon ───────────────────────────────────────────────
    daemon_cmd = [
        "aria2c",
        "--enable-rpc=true",
        f"--rpc-listen-port={RPC_PORT}",
        f"--rpc-secret={RPC_SECRET}",
        "--rpc-allow-origin-all=true",
        "--enable-dht=true",
        "--dht-listen-port=6881",
        "--enable-peer-exchange=true",
        "--bt-save-metadata=true",
        "--bt-detach-seed-only=true",
        "--seed-ratio=0.0",
        "--seed-time=0",
        "--max-connection-per-server=16",
        "--split=16",
        "--console-log-level=error",
        f"--dir={Paths.down_path}",
    ]
    daemon = await asyncio.create_subprocess_exec(
        *daemon_cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    try:
        async with aiohttp.ClientSession() as session:
            # ── 2. Wait for RPC to be ready ──────────────────────────────
            for _ in range(40):
                if await _rpc(session, "aria2.getVersion", [TOKEN]):
                    break
                await asyncio.sleep(0.25)
            else:
                logging.error("aria2c RPC did not start in time")
                return

            # ── 3. Add the torrent ───────────────────────────────────────
            inp = link.strip()
            if inp.startswith("http") and inp.endswith(".torrent"):
                import base64
                async with session.get(inp) as resp:
                    b64 = base64.b64encode(await resp.read()).decode()
                gid = await _rpc(session, "aria2.addTorrent", [TOKEN, b64])
            else:
                gid = await _rpc(session, "aria2.addUri", [TOKEN, [inp]])

            if not gid:
                logging.error("Failed to add torrent to aria2c")
                return

            logging.info(f"Torrent GID: {gid}")
            Aria2c.link_info = False
            stall = 0

            # ── 4. Poll loop — fully async, never blocks the event loop ──
            while True:
                await asyncio.sleep(1)

                info = await _rpc(session, "aria2.tellStatus", [TOKEN, gid])
                if not info:
                    continue

                status    = info.get("status", "")
                completed = int(info.get("completedLength", 0))
                total     = int(info.get("totalLength", 0))
                speed_dl  = int(info.get("downloadSpeed", 0))
                speed_ul  = int(info.get("uploadSpeed", 0))
                peers     = int(info.get("numSeeders", 0))
                files     = info.get("files", [])
                fname     = (files[0].get("path", "") if files else "") or name_d
                fname     = fname.split("/")[-1] or name_d

                # Update display name once we have it
                if fname and fname != name_d:
                    Messages.status_head = (
                        f"<b>🧲 DOWNLOADING TORRENT » </b><i>Link {str(num).zfill(2)}</i>\n\n"
                        f"<b>🏷️ Name » </b><code>{fname}</code>\n"
                    )

                if status == "complete":
                    break
                if status == "error":
                    err = info.get("errorMessage", "unknown")
                    logging.error(f"Torrent error: {err}")
                    break

                # Stall detection
                if speed_dl == 0 and total == 0:
                    stall += 1
                    if stall >= 120:
                        logging.warning("No torrent progress for 2 min — no seeders?")
                        break
                else:
                    stall = 0
                    Aria2c.link_info = True

                pct = (completed / total * 100) if total else 0.0
                eta = int((total - completed) / speed_dl) if speed_dl else 0
                eta_str = (
                    f"{eta//3600:02d}h{(eta%3600)//60:02d}m"
                    if eta >= 3600
                    else f"{eta//60:02d}m{eta%60:02d}s"
                    if eta
                    else "N/A"
                )
                phase = "Metadata" if total == 0 else f"{sizeUnit(completed)}/{sizeUnit(total)}"
                spd_str = f"{sizeUnit(speed_dl)}/s ⬇  {sizeUnit(speed_ul)}/s ⬆  👥{peers}"

                await status_bar(
                    Messages.status_head,
                    spd_str,
                    pct,
                    eta_str,
                    phase,
                    sizeUnit(total) if total else "?",
                    "Aria2c BT 🧲",
                )

            # ── 5. Shutdown RPC daemon ───────────────────────────────────
            await _rpc(session, "aria2.shutdown", [TOKEN])

    except asyncio.CancelledError:
        # Cancel button pressed — shut down aria2c and re-raise
        try:
            async with aiohttp.ClientSession() as s:
                await _rpc(s, "aria2.forceShutdown", [TOKEN])
        except Exception:
            pass
        raise
    finally:
        await asyncio.sleep(0.5)
        if daemon.returncode is None:
            daemon.kill()
        await daemon.wait()
