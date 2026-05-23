# copyright 2023 © Xron Trix | https://github.com/Xrontrix10

import re
import logging
import asyncio
import subprocess
from datetime import datetime
from colab_leecher.utility.helper import sizeUnit, status_bar
from colab_leecher.utility.variables import BOT, Aria2c, Paths, Messages, BotTimes


async def aria2_Download(link: str, num: int):
    global BotTimes, Messages
    name_d = get_Aria2c_Name(link)
    BotTimes.task_start = datetime.now()
    Messages.status_head = (
        f"<b>📥 DOWNLOADING FROM » </b><i>🔗Link {str(num).zfill(2)}</i>\n\n"
        f"<b>🏷️ Name » </b><code>{name_d}</code>\n"
    )

    command = [
        "aria2c",
        "-x16",
        "--seed-time=0",
        "--summary-interval=1",
        "--max-tries=3",
        "--console-log-level=notice",
        "-d", Paths.down_path,
        link,
    ]

    # Async subprocess — does NOT block the event loop between lines,
    # so the cancel button and other Pyrogram callbacks keep working.
    proc = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        async for raw in proc.stdout:
            await on_output(raw.decode("utf-8", errors="replace"))
    except asyncio.CancelledError:
        proc.kill()
        raise
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
    if proc.returncode != 0:
        stderr = (await proc.stderr.read()).decode("utf-8", errors="replace")
        code = proc.returncode
        if code == 3:
            logging.error(f"Resource not found: {link}")
        elif code == 9:
            logging.error("Not enough disk space")
        elif code == 24:
            logging.error("HTTP authorization failed")
        else:
            logging.error(f"aria2c failed (code {code}) for {link}\n{stderr}")


def get_Aria2c_Name(link):
    if len(BOT.Options.custom_name) != 0:
        return BOT.Options.custom_name
    cmd = f'aria2c -x10 --dry-run --file-allocation=none "{link}"'
    result = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
    stdout_str = result.stdout.decode("utf-8")
    filename = stdout_str.split("complete: ")[-1].split("\n")[0]
    name = filename.split("/")[-1]
    return name if name else "UNKNOWN DOWNLOAD NAME"


async def on_output(output: str):
    total_size = "0B"
    progress_percentage = "0B"
    downloaded_bytes = "0B"
    eta = "0S"
    try:
        if "ETA:" in output:
            parts = output.split()
            total_size = parts[1].split("/")[1]
            total_size = total_size.split("(")[0]
            progress_percentage = parts[1][parts[1].find("(") + 1: parts[1].find(")")]
            downloaded_bytes = parts[1].split("/")[0]
            eta = parts[4].split(":")[1][:-1]
    except Exception as e:
        logging.error(f"aria2 output parse error: {e}")

    pct_nums = re.findall(r"\d+\.?\d*", progress_percentage)
    down_nums = re.findall(r"\d+\.?\d*", downloaded_bytes)
    down_units = re.findall(r"[a-zA-Z]+", downloaded_bytes)

    if not pct_nums or not down_nums or not down_units:
        return

    percentage = pct_nums[0]
    down = down_nums[0]
    unit_char = down_units[0][0].upper()
    spd = {"G": 3, "M": 2, "K": 1}.get(unit_char, 0)

    elapsed_time_seconds = max((datetime.now() - BotTimes.task_start).seconds, 1)

    if elapsed_time_seconds >= 270 and not Aria2c.link_info:
        logging.error("No download info after 4.5 min — possibly dead link 💀")

    if total_size != "0B":
        Aria2c.link_info = True
        current_speed = (float(down) * 1024 ** spd) / elapsed_time_seconds
        speed_string = f"{sizeUnit(current_speed)}/s"
        await status_bar(
            Messages.status_head,
            speed_string,
            int(float(percentage)),
            eta,
            downloaded_bytes,
            total_size,
            "Aria2c 🧨",
        )
