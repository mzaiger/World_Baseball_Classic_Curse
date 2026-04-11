import argparse
import json
import os
import sys
import time
import unicodedata
import webbrowser
from pathlib import Path
from urllib.parse import quote

import requests
from requests_oauthlib import OAuth2Session

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
CLIENT_ID     = os.getenv("YAHOO_CLIENT_ID")
CLIENT_SECRET = os.getenv("YAHOO_CLIENT_SECRET")

REDIRECT_URI      = "https://localhost"
AUTHORIZATION_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL         = "https://api.login.yahoo.com/oauth2/get_token"
TOKEN_CACHE       = Path("token_cache.json")

BASE_URL = "https://fantasysports.yahooapis.com/fantasy/v2"
REQUEST_DELAY = 1.0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_oauth_session() -> OAuth2Session:
    cached = _load_token()
    session = OAuth2Session(
        client_id=CLIENT_ID,
        redirect_uri=REDIRECT_URI,
        auto_refresh_url=TOKEN_URL,
        auto_refresh_kwargs={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        token_updater=_save_token,
    )
    if cached:
        session.token = cached
        if time.time() > cached.get("expires_at", 0) - 300:
            token = session.refresh_token(TOKEN_URL, client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
            _save_token(token)
    else:
        auth_url, _ = session.authorization_url(AUTHORIZATION_URL)
        print(f"\nAuthorize here: {auth_url}")
        webbrowser.open(auth_url)
        redirect_response = input("Paste redirect URL/code: ").strip()
        token = session.fetch_token(TOKEN_URL, authorization_response=redirect_response, client_secret=CLIENT_SECRET) if redirect_response.startswith("http") else session.fetch_token(TOKEN_URL, code=redirect_response, client_secret=CLIENT_SECRET)
        _save_token(token)
    return session

def _save_token(token): TOKEN_CACHE.write_text(json.dumps(token, indent=2))
def _load_token():
    # Check for token in GitHub Secrets first
    token_from_env = os.getenv("YAHOO_TOKEN")
    if token_from_env:
        try:
            return json.loads(token_from_env)
        except:
            pass

    # Fallback to local file for testing
    if TOKEN_CACHE.exists():
        try:
            return json.loads(TOKEN_CACHE.read_text())
        except:
            pass
    return None
def api_get(session: OAuth2Session, url: str, params: dict | None = None) -> dict:
    params = params or {}
    params["format"] = "json"
    resp = session.get(url, params=params)
    if resp.status_code != 200: return {}
    try: return resp.json()
    except: return {}

# ---------------------------------------------------------------------------
# Core Logic
# ---------------------------------------------------------------------------

def search_player(session, name, league_key):
    """Searches for player and extracts both metadata and ownership from the response."""
    clean_name = name.strip()
    search_queries = [clean_name, clean_name.replace("'", ""), clean_name.replace("'", " ")]
    if "." in clean_name: search_queries.append(clean_name.replace(".", ""))
    
    seen = set()
    search_queries = [x for x in search_queries if not (x in seen or seen.add(x))]

    for query in search_queries:
        safe_name = quote(query)
        url = f"{BASE_URL}/league/{league_key}/players;search={safe_name};out=ownership"
        time.sleep(REQUEST_DELAY)
        data = api_get(session, url)
        
        if not data: continue
            
        try:
            l_content = data.get("fantasy_content", {}).get("league", [{}, {}])
            if len(l_content) > 1:
                players_block = l_content[1].get("players", {})
                
                if players_block.get("count", 0) > 0:
                    p_entry = players_block.get("0", {}).get("player", [])
                    combined_info = {"fantasy_team": "None"}
                    
                    for item in p_entry:
                        if isinstance(item, list):
                            for sub_item in item:
                                if isinstance(sub_item, dict):
                                    combined_info.update(sub_item)
                        elif isinstance(item, dict):
                            if "ownership" in item:
                                own = item["ownership"]
                                if own.get("ownership_type") == "team":
                                    combined_info["fantasy_team"] = own.get("owner_team_name", "None")
                            else:
                                combined_info.update(item)
                    
                    if "player_key" in combined_info:
                        return combined_info
        except: pass
    return None

def get_player_ranks(session, league_key, player_key) -> dict:
    """Fetches preseason and current rank."""
    pre = cur = None
    time.sleep(REQUEST_DELAY)
    url = f"{BASE_URL}/league/{league_key}/players;player_keys={player_key}/ranks"
    data = api_get(session, url)
    
    if data:
        l_content = data.get("fantasy_content", {}).get("league", [{}, {}])
        if len(l_content) > 1:
            players_dict = l_content[1].get("players", {})
            p_entry = players_dict.get("0", {}).get("player", [])
            for entry in p_entry:
                if isinstance(entry, dict) and "player_ranks" in entry:
                    for rank_obj in entry["player_ranks"]:
                        r = rank_obj.get("player_rank", {})
                        if r.get("rank_type") == "OR":
                            pre = r.get("rank_value")
                        elif r.get("rank_type") == "S" and (r.get("rank_season") == "2026" or not r.get("rank_season")):
                            cur = r.get("rank_value")
    return {"preseason_rank": pre, "current_rank": cur}

def read_csv(csv_path: str) -> list[dict]:
    """Reads CSV and returns full rows to preserve all original columns."""
    import csv
    players = []
    with open(csv_path, encoding="latin-1", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("PLAYER"):
                # Preserve entire row (ORG, WBC TEAM, etc.) and add name_raw for internal use
                row["name_raw"] = row["PLAYER"].strip()
                players.append(row)
    return players

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="MLB_WBC_Roster.csv")
    parser.add_argument("--out", default="player_ranks.json")
    parser.add_argument("--league", default="469.l.23321")
    args = parser.parse_args()

    players = read_csv(args.csv)
    session = get_oauth_session()
    results = []
    
    print(f"Searching for {len(players)} players...")
    for i, p in enumerate(players, 1):
        print(f"[{i}/{len(players)}] {p['name_raw']}... ", end="", flush=True)
        
        match = search_player(session, p["name_raw"], args.league)
        
        if not match:
            print("NOT FOUND")
            results.append({**p, "status": "not_found"})
            continue
        
        ranks = get_player_ranks(session, args.league, match["player_key"])
        
        # Combine the original CSV row data with the new Yahoo metadata
        final_entry = {
            **p,
            "preseason_rank": ranks["preseason_rank"],
            "current_rank": ranks["current_rank"],
            "fantasy_team": match.get("fantasy_team", "None"),
            "yahoo_key": match["player_key"],
            "status": "ok"
        }
        
        print(f"Team: {final_entry['fantasy_team']} | O-Rank: {final_entry['preseason_rank']}")
        results.append(final_entry)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Results saved to {args.out}")

if __name__ == "__main__":
    main()