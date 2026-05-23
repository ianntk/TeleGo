# copyright 2023 © Xron Trix | https://github.com/Xrontrix10

import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())

import os
import logging
import json
from uvloop import install
from pyrogram.client import Client

# ── Resolve base path: env var → Colab default ──────────────────────────────
BASE_PATH = os.environ.get("BOT_BASE_PATH", "/content/TeleGo")

# ── Load credentials: individual env vars → credentials.json file ───────────
if all(
    os.environ.get(k)
    for k in ("API_ID", "API_HASH", "BOT_TOKEN", "USER_ID", "DUMP_ID")
):
    API_ID    = int(os.environ["API_ID"])
    API_HASH  = os.environ["API_HASH"]
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    OWNER     = int(os.environ["USER_ID"])
    _dump     = os.environ["DUMP_ID"].strip()
    if not _dump.startswith("-100"):
        _dump = "-100" + _dump.lstrip("-")
    DUMP_ID   = int(_dump)
else:
    creds_file = os.path.join(BASE_PATH, "credentials.json")
    with open(creds_file, "r") as f:
        credentials = json.loads(f.read())
    API_ID    = credentials["API_ID"]
    API_HASH  = credentials["API_HASH"]
    BOT_TOKEN = credentials["BOT_TOKEN"]
    OWNER     = credentials["USER_ID"]
    DUMP_ID   = credentials["DUMP_ID"]

logging.basicConfig(level=logging.INFO)

install()

# Session stored alongside the bot code
colab_bot = Client(
    "my_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=BASE_PATH,
)
