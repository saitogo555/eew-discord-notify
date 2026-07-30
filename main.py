import os
import json
import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
import websockets

PRODUCTION_WS_URL = "wss://api.p2pquake.net/v2/ws"
SANDBOX_WS_URL = "wss://api-realtime-sandbox.p2pquake.net/v2/ws"

PRODUCTION = os.getenv("PRODUCTION", "false").lower() == "true"
P2PQUAKE_WS_URL = os.getenv("P2PQUAKE_WS_URL", PRODUCTION_WS_URL if PRODUCTION else SANDBOX_WS_URL)
MIN_SCALE = int(os.getenv("MIN_SCALE", "40" if PRODUCTION else "-1"))
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

if not DISCORD_WEBHOOK_URL:
	raise RuntimeError("DISCORD_WEBHOOK_URL を環境変数に設定してください。")

logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("p2pquake-discord")

SCALE_LABELS = {
	-1: "不明",
	10: "震度1",
	20: "震度2",
	30: "震度3",
	40: "震度4",
	45: "震度5弱以上未入電",
	50: "震度5弱",
	55: "震度5強",
	60: "震度6弱",
	65: "震度6強",
	70: "震度7",
}

SCALE_COLORS = {
	-1: 0x95A5A6,
	10: 0x3498DB,
	20: 0x2ECC71,
	30: 0xF1C40F,
	40: 0xE67E22,
	45: 0xD35400,
	50: 0xE74C3C,
	55: 0xC0392B,
	60: 0x8E44AD,
	65: 0x6C3483,
	70: 0x4A235A,
}

TSUNAMI_LABELS = {
	"None": "なし",
	"Unknown": "不明",
	"Checking": "調査中",
	"NonEffective": "若干の海面変動が予想されるが、被害の心配なし",
	"Watch": "津波注意報",
	"Warning": "津波予報（種類不明）",
}

seen_events = set()
event_report_counts = {}


def parse_time(text: str) -> str:
	if not text:
		return "不明"

	patterns = [
		"%Y/%m/%d %H:%M:%S",
		"%Y-%m-%d %H:%M:%S",
		"%Y/%m/%d %H:%M",
		"%Y-%m-%dT%H:%M:%S%z",
	]

	for pattern in patterns:
		try:
			dt = datetime.strptime(text, pattern)
			return dt.strftime("%Y-%m-%d %H:%M:%S")
		except ValueError:
			pass

	return text


def build_event_key(data: dict) -> tuple:
	eq = data.get("earthquake", {}) or {}
	hyp = eq.get("hypocenter", {}) or {}
	return (
		data.get("code"),
		eq.get("time"),
		hyp.get("name"),
		hyp.get("latitude"),
		hyp.get("longitude"),
		hyp.get("depth"),
		hyp.get("magnitude"),
		eq.get("maxScale"),
	)


def to_str(v, fallback="不明"):
	if v is None or v == "":
		return fallback
	if v == -1 or v == -1.0 or str(v) in ("-1", "-1.0"):
		return fallback
	return str(v)


def build_embed(data: dict, report_num: int = 1) -> dict:
	eq = data.get("earthquake", {}) or {}
	hyp = eq.get("hypocenter", {}) or {}
	comments = data.get("comments", {}) or {}

	max_scale = int(eq.get("maxScale", -1))
	scale_label = SCALE_LABELS.get(max_scale, f"不明 ({max_scale})")
	color = SCALE_COLORS.get(max_scale, 0x5865F2)

	origin_time = parse_time(eq.get("time"))
	location = to_str(hyp.get("name"))
	magnitude = to_str(hyp.get("magnitude"))
	depth = to_str(hyp.get("depth"))
	raw_tsunami = eq.get("domesticTsunami") or data.get("domesticTsunami")
	domestic_tsunami = TSUNAMI_LABELS.get(raw_tsunami, to_str(raw_tsunami))

	depth_text = f"{depth} km" if depth.isdigit() else depth
	report_text = f"第{report_num}報"

	title_scale = "震度不明" if scale_label == "不明" else scale_label
	title_location = "震源地不明" if location == "不明" else location

	if PRODUCTION:
		title = f"🚨 地震情報 【{title_scale}】 {title_location} 🚨"
	else:
		title = f"🚨 地震情報 [Sandbox Mode] 【{title_scale}】 {title_location} 🚨"

	fields = [
		{"name": "報数", "value": report_text, "inline": True},
		{"name": "発生時刻", "value": origin_time, "inline": True},
		{"name": "震度", "value": scale_label, "inline": True},
		{"name": "マグニチュード", "value": magnitude, "inline": True},
		{"name": "震源地", "value": location, "inline": True},
		{"name": "深さ", "value": depth_text, "inline": True},
		{"name": "津波", "value": domestic_tsunami, "inline": True},
	]

	free_form_comment = (comments.get("freeFormComment") or "").strip()
	if free_form_comment:
		fields.append({"name": "補足情報", "value": free_form_comment, "inline": False})

	return {
		"title": title,
		"color": color,
		"fields": fields,
		"footer": {"text": "P2P地震情報"},
		"timestamp": datetime.now(timezone.utc).isoformat(),
	}


async def send_discord(session: aiohttp.ClientSession, embed: dict):
	payload = {
		"embeds": [embed],
		"allowed_mentions": {"parse": []},
	}

	logger.debug("sending webhook: title=%s", embed.get("title"))

	async with session.post(DISCORD_WEBHOOK_URL, json=payload) as resp:
		if resp.status not in (200, 204):
			text = await resp.text()
			logger.error("discord webhook failed: status=%s body=%s", resp.status, text)
			raise RuntimeError(f"Discord Webhook error: {resp.status} {text}")

	logger.info("discord sent: %s", embed.get("title"))


async def handle_message(session: aiohttp.ClientSession, raw_message: str):
	logger.debug("raw message received: %s", raw_message[:500])

	try:
		data = json.loads(raw_message)
	except json.JSONDecodeError:
		logger.warning("json decode failed")
		return

	code = data.get("code")
	logger.debug("message parsed: code=%s keys=%s", code, list(data.keys()))

	if code != 551:
		logger.debug("skip by code: %s", code)
		return

	eq = data.get("earthquake", {}) or {}
	max_scale = int(eq.get("maxScale", -1))
	logger.info(
		"earthquake event received: time=%s place=%s maxScale=%s",
		eq.get("time"),
		(eq.get("hypocenter", {}) or {}).get("name"),
		max_scale,
	)

	if max_scale < MIN_SCALE:
		logger.info("skip by min scale: event=%s threshold=%s", max_scale, MIN_SCALE)
		return

	event_key = build_event_key(data)
	if event_key in seen_events:
		logger.info("skip duplicated event: %s", event_key)
		return

	issue = data.get("issue", {}) or {}
	event_id = issue.get("eventId") or eq.get("time") or "unknown"
	report_num = event_report_counts.get(event_id, 0) + 1
	event_report_counts[event_id] = report_num

	embed = build_embed(data, report_num=report_num)
	await send_discord(session, embed)

	seen_events.add(event_key)
	logger.debug("seen_events size=%s", len(seen_events))

	if len(seen_events) > 1000:
		seen_events.clear()
		event_report_counts.clear()
		logger.info("seen_events and event_report_counts cleared")


async def main():
	logger.info("program started")
	logger.info(
		"config: production=%s ws_url=%s min_scale=%s",
		PRODUCTION,
		P2PQUAKE_WS_URL,
		MIN_SCALE,
	)

	timeout = aiohttp.ClientTimeout(total=15)
	async with aiohttp.ClientSession(timeout=timeout) as session:
		while True:
			try:
				logger.info("connecting websocket: %s", P2PQUAKE_WS_URL)
				async with websockets.connect(
					P2PQUAKE_WS_URL,
					ping_interval=20,
					ping_timeout=20,
					close_timeout=10,
					max_size=2**20,
				) as ws:
					logger.info("websocket connected")

					while True:
						try:
							message = await asyncio.wait_for(ws.recv(), timeout=60)
							logger.debug("websocket recv ok")
							await handle_message(session, message)
						except asyncio.TimeoutError:
							logger.info("no message received in 60s; connection still alive")
						except websockets.ConnectionClosed as e:
							logger.warning("websocket closed: code=%s reason=%s", e.code, e.reason)
							raise

			except KeyboardInterrupt:
				logger.info("keyboard interrupt received")
				raise
			except Exception as e:
				logger.exception("connection error: %s", e)
				await asyncio.sleep(5)

if __name__ == "__main__":
	asyncio.run(main())