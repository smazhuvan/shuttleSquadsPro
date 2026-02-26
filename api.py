# api.py
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from monte_carlo import run_tournament_simulation
from engine import generate_power_rankings, calculate_glicko2_match, supabase
from tournament_builder import TournamentGraphGenerator

app = FastAPI(title="ShuttleSquads AI Oracle")

# --- MODELS ---
class TournamentConfigRequest(BaseModel):
    total_teams: int
    num_groups: int
    advancing_per_group: int
    playoff_style: str = "standard"

class MatchRecord(BaseModel):
    id: str
    tournament_id: str
    team_a: str
    team_b: str
    score_a: Optional[int]
    score_b: Optional[int]
    winner: Optional[str]
    status: str

class SupabaseWebhookPayload(BaseModel):
    type: str
    table: str
    record: MatchRecord
    old_record: Optional[Dict[str, Any]] = None

# --- MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HELPER: TOURNAMENT ID RESOLVER ---
def resolve_tournament_id(identifier: str) -> str:
    """
    Checks if the input is a full UUID. If not, queries the tournaments 
    table to find the UUID associated with the short_code.
    """
    try:
        uuid.UUID(identifier)
        return identifier # It's already a valid UUID
    except ValueError:
        pass # It's not a UUID, proceed to short_code lookup

    res = supabase.table("tournaments").select("id").eq("short_code", identifier).execute()
    
    if res.data and len(res.data) > 0:
        return res.data[0]["id"]
    
    raise ValueError(f"No tournament found with short code: {identifier}")


# --- EXISTING ENDPOINTS ---
@app.get("/")
def read_root():
    return {"status": "AI Engine is Online"}

@app.get("/api/power-rankings/{identifier}")
def get_power_rankings(identifier: str):
    try:
        tournament_id = resolve_tournament_id(identifier)

        # 1. Fetch Ratings & Matches
        ratings_res = supabase.table("team_ratings").select("*").eq("tournament_id", tournament_id).order("rating", desc=True).execute()
        matches_res = supabase.table("matches").select("*").eq("tournament_id", tournament_id).eq("status", "finished").execute()
        
        matches = matches_res.data or []
        team_stats = {}

        # 2. Process all finished matches for advanced metrics
        for m in matches:
            t1, t2 = m.get("team_a"), m.get("team_b")
            s1, s2 = m.get("score_a", 0), m.get("score_b", 0)
            winner = m.get("winner")

            if not t1 or not t2 or s1 is None or s2 is None: continue

            for t in [t1, t2]:
                if t not in team_stats:
                    team_stats[t] = {"scored": 0, "conceded": 0, "clutch_games": 0, "clutch_wins": 0, "upsets": 0}

            # Dominance Quotient Math
            team_stats[t1]["scored"] += s1
            team_stats[t1]["conceded"] += s2
            team_stats[t2]["scored"] += s2
            team_stats[t2]["conceded"] += s1

            # Clutch Factor Math (Games decided by 3 points or less)
            if abs(s1 - s2) <= 3:
                team_stats[t1]["clutch_games"] += 1
                team_stats[t2]["clutch_games"] += 1
                if winner == t1: team_stats[t1]["clutch_wins"] += 1
                if winner == t2: team_stats[t2]["clutch_wins"] += 1

        # 3. Format the final enriched payload
        enriched_rankings = []
        for r in ratings_res.data:
            team = r["team_name"]
            stats = team_stats.get(team, {"scored": 1, "conceded": 1, "clutch_games": 0, "clutch_wins": 0})
            
            # Avoid division by zero
            conceded = stats["conceded"] if stats["conceded"] > 0 else 1
            dq = round(stats["scored"] / conceded, 2)
            
            clutch_rate = round((stats["clutch_wins"] / stats["clutch_games"]) * 100, 1) if stats["clutch_games"] > 0 else 0.0

            enriched_rankings.append({
                "team": team,
                "power_rating": round(r["rating"]),
                "volatility": round(r.get("volatility", 0.06), 3),
                "dominance_quotient": dq,
                "clutch_win_rate": clutch_rate,
                "giant_killer": dq > 1.0 and round(r["rating"]) < 1550
            })

        return {"tournament_id": tournament_id, "rankings": enriched_rankings}
    except Exception as e:
        return {"error": str(e)}
    
@app.post("/api/generate-tournament-graph")
async def generate_tournament_graph(config: TournamentConfigRequest):
    try:
        engine = TournamentGraphGenerator(
            total_teams=config.total_teams,
            num_groups=config.num_groups,
            advancing_per_group=config.advancing_per_group
        )
        tournament_json = engine.build(playoff_style=config.playoff_style)
        return tournament_json
    except Exception as e:
        return {"error": str(e)}

# --- WEBHOOK ENDPOINT ---
@app.post("/webhook/match-finished")
async def process_match_result(payload: SupabaseWebhookPayload):
    match = payload.record

    if match.status != "finished" or (payload.old_record and payload.old_record.get("status") == "finished"):
        return {"status": "ignored", "reason": "Match not newly finished"}

    team_a, team_b, winner_name = match.team_a, match.team_b, match.winner
    tourney_id = match.tournament_id
    winner_key = "team_a" if winner_name == team_a else "team_b"

    try:
        res = supabase.table("team_ratings").select("*").in_("team_name", [team_a, team_b]).eq("tournament_id", tourney_id).execute()
        current_data = {row["team_name"]: row for row in res.data}

        stats_a = current_data.get(team_a, {"rating": 1500.0, "rd": 350.0, "volatility": 0.06, "matches_played": 0})
        stats_b = current_data.get(team_b, {"rating": 1500.0, "rd": 350.0, "volatility": 0.06, "matches_played": 0})

        new_a, new_b = calculate_glicko2_match(stats_a, stats_b, winner_key)

        supabase.table("team_ratings").upsert([
            {"team_name": team_a, "tournament_id": tourney_id, "matches_played": stats_a["matches_played"] + 1, **new_a},
            {"team_name": team_b, "tournament_id": tourney_id, "matches_played": stats_b["matches_played"] + 1, **new_b}
        ]).execute()

        return {"status": "success", "message": f"Ratings updated for {team_a} and {team_b}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/futures/{identifier}")
def get_tournament_futures(identifier: str):
    try:
        tournament_id = resolve_tournament_id(identifier)

        res = supabase.table("team_ratings").select("*").eq("tournament_id", tournament_id).order("rating", desc=True).execute()
        
        if not res.data or len(res.data) < 8:
            return {"error": "Need at least 8 teams with calculated ratings to run the Monte Carlo simulation."}

        teams = [{"team": row["team_name"], "power_rating": round(row["rating"])} for row in res.data]
        futures_forecast = run_tournament_simulation(teams, iterations=10000)

        return {
            "tournament_id": tournament_id,
            "iterations": 10000,
            "forecast": futures_forecast
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/bracket/{identifier}")
def get_bracket(identifier: str):
    try:
        tournament_id = resolve_tournament_id(identifier)

        # 1. Fetch matches
        res = supabase.table("matches").select("*").eq("tournament_id", tournament_id).execute()
        matches = res.data or []
        
        # 2. Group matches by their round
        rounds_dict = {}
        for m in matches:
            r_name = m.get("round_name") or "Qualifier" 
            
            if r_name not in rounds_dict:
                rounds_dict[r_name] = []
                
            rounds_dict[r_name].append({
                "id": m.get("id"),
                "t1": m.get("team_a") or "TBD",
                "t2": m.get("team_b") or "TBD",
                "s1": m.get("score_a"),
                "s2": m.get("score_b"),
                "winner": m.get("winner")
            })
            
        # 3. Format into the array structure
        organized_matches = []
        
        # UPDATED: Explicitly mapping your custom gameplay order
        round_order = {
            "Qualifier": 1,
            "Quarter-Finals": 2, 
            "Quarter-Final": 2, 
            "Semi-Finals": 3, 
            "Semi-Final": 3, 
            "3rd Place": 4, 
            "Final": 5, 
            "Championship": 5
        }
        
        sorted_round_names = sorted(rounds_dict.keys(), key=lambda x: round_order.get(x, 99))
        
        for name in sorted_round_names:
            organized_matches.append({
                "name": name,
                "matches": rounds_dict[name]
            })

        return {"tournament_id": tournament_id, "rounds": organized_matches} 

    except Exception as e:
        return {"error": str(e)}
