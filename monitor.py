import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

CHESS_API = "https://api.chess.com/pub/player"
ONLINE_THRESHOLD_SECONDS = 300
USER_AGENT = os.environ.get(
    "USER_AGENT",
    "ChessOnlineMonitor/1.0 (github.com/yoavjm/chess-online-monitor)",
)

TG_TOKEN = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

PLAYERS_FILE = Path("players.txt")
STATE_FILE = Path("state.json")


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def get_player_status(username):
    profile = fetch_json(f"{CHESS_API}/{username}")
    last_online = profile.get("last_online", 0)
    is_online = (time.time() - last_online) < ONLINE_THRESHOLD_SECONDS

    bullet_rating = None
    try:
        stats = fetch_json(f"{CHESS_API}/{username}/stats")
        bullet_rating = stats.get("chess_bullet", {}).get("last", {}).get("rating")
    except Exception:
        pass

    return is_online, bullet_rating


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = json.dumps(
        {"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    ).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=15).read()


def load_players():
    if not PLAYERS_FILE.exists():
        print("players.txt missing", file=sys.stderr)
        sys.exit(1)
    return [
        line.strip().lower()
        for line in PLAYERS_FILE.read_text().splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def main():
    players = load_players()
    state = load_state()
    new_state = {}

    for username in players:
        try:
            is_online, bullet = get_player_status(username)
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code} for {username}")
            new_state[username] = state.get(username, False)
            continue
        except Exception as e:
            print(f"Error for {username}: {e}")
            new_state[username] = state.get(username, False)
            continue

        was_online = state.get(username, False)
        new_state[username] = is_online

        if is_online and not was_online:
            bullet_str = str(bullet) if bullet is not None else "n/a"
            msg = (
                f"\u265f\ufe0f <b>{username}</b> is online\n"
                f"Bullet: {bullet_str}\n"
                f"https://www.chess.com/member/{username}"
            )
            try:
                send_telegram(msg)
                print(f"Notified: {username} (bullet {bullet_str})")
            except Exception as e:
                print(f"Telegram send failed for {username}: {e}")

        time.sleep(0.5)

    save_state(new_state)


if __name__ == "__main__":
    main()
