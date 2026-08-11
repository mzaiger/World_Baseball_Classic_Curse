# World Baseball Classic Curse

Tracks whether the "WBC curse" theory holds up — the idea that MLB
players who play in the World Baseball Classic underperform in the
fantasy season that follows.

## How it works

- **`MLB_WBC_Roster.csv`** lists every MLB player who played for a given
  WBC team, along with their org, position, and age
- **`yahoo_fantasy_ranks.py`** looks each player up in the Yahoo Fantasy
  API and enriches the roster with `preseason_rank`, `current_rank`,
  fantasy team, and Yahoo player key, writing the result to
  `player_ranks.json`
- **`index.html`** is a filterable, sortable table (dark theme) showing
  each player's WBC team, MLB org, fantasy team, and how their rank has
  moved from preseason to current — the core evidence for or against the
  "curse"

## GitHub secrets required

`.github/workflows/update_player_ranks.yml` runs daily and needs these
added under repo → Settings → Secrets and variables → Actions:

| Secret | Used for |
|---|---|
| `YAHOO_CLIENT_ID` | Yahoo Fantasy API OAuth2 |
| `YAHOO_CLIENT_SECRET` | Yahoo Fantasy API OAuth2 |
| `YAHOO_TOKEN` | Cached Yahoo OAuth token (JSON), so the workflow can refresh without an interactive login |

## Setup

Requires Yahoo Fantasy API OAuth2 credentials:

```bash
export YAHOO_CLIENT_ID="your_client_id"
export YAHOO_CLIENT_SECRET="your_client_secret"
```

## Running locally

```bash
pip install requests requests-oauthlib

python yahoo_fantasy_ranks.py
```

Then open `index.html` (or serve the folder with
`python -m http.server`) to browse the table.

## Structure

```
World_Baseball_Classic_Curse-main/
├── MLB_WBC_Roster.csv     # WBC roster input (org, team, player, position, age)
├── yahoo_fantasy_ranks.py  # enriches roster with Yahoo fantasy rank data
├── player_ranks.json       # generated: roster + preseason/current rank
└── index.html              # filterable rank-comparison table
```
