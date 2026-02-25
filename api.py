# api.py
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

# --- EXISTING ENDPOINTS ---
@app.get("/")
def read_root():
    return {"status": "AI Engine is Online"}

@app.get("/api/power-rankings/{tournament_id}")
def get_rankings(tournament_id: str):
    try:
        rankings = generate_power_rankings(tournament_id)
        return {"tournament_id": tournament_id, "rankings": rankings}
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

# --- NEW: WEBHOOK ENDPOINT ---
@app.post("/webhook/match-finished")
async def process_match_result(payload: SupabaseWebhookPayload):
    """
    Supabase calls this automatically when a match finishes.
    It crunches the Glicko-2 math and saves the results.
    """
    match = payload.record

    # Guard clause to ensure we only process newly finished matches
    if match.status != "finished" or (payload.old_record and payload.old_record.get("status") == "finished"):
        return {"status": "ignored", "reason": "Match not newly finished"}

    team_a, team_b, winner_name = match.team_a, match.team_b, match.winner
    tourney_id = match.tournament_id

    # The engine needs to know if "team_a" or "team_b" won structurally
    winner_key = "team_a" if winner_name == team_a else "team_b"

    try:
        # 1. Fetch current ratings from the database
        res = supabase.table("team_ratings").select("*").in_("team_name", [team_a, team_b]).eq("tournament_id", tourney_id).execute()
        current_data = {row["team_name"]: row for row in res.data}

        # 2. Set defaults if this is the first time these teams are playing (Cold Start)
        stats_a = current_data.get(team_a, {"rating": 1500.0, "rd": 350.0, "volatility": 0.06, "matches_played": 0})
        stats_b = current_data.get(team_b, {"rating": 1500.0, "rd": 350.0, "volatility": 0.06, "matches_played": 0})

        # 3. Crunch the advanced math
        new_a, new_b = calculate_glicko2_match(stats_a, stats_b, winner_key)

        # 4. Save directly back to Supabase
        supabase.table("team_ratings").upsert([
            {"team_name": team_a, "tournament_id": tourney_id, "matches_played": stats_a["matches_played"] + 1, **new_a},
            {"team_name": team_b, "tournament_id": tourney_id, "matches_played": stats_b["matches_played"] + 1, **new_b}
        ]).execute()

        return {"status": "success", "message": f"Ratings updated for {team_a} and {team_b}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/futures/{tournament_id}")
def get_tournament_futures(tournament_id: str):
    """
    Fetches live ratings and runs a 10,000 iteration Monte Carlo simulation.
    """
    try:
        # 1. Grab the current live power rankings (Super fast O(1) fetch)
        res = supabase.table("team_ratings").select("*").eq("tournament_id", tournament_id).order("rating", desc=True).execute()
        
        if not res.data or len(res.data) < 8:
            return {"error": "Need at least 8 teams with calculated ratings to run the Monte Carlo simulation."}

        # 2. Format the data for the simulator
        teams = [{"team": row["team_name"], "power_rating": round(row["rating"])} for row in res.data]

        # 3. Fire up the engine! Runs 10k simulations in milliseconds.
        futures_forecast = run_tournament_simulation(teams, iterations=10000)

        return {
            "tournament_id": tournament_id,
            "iterations": 10000,
            "forecast": futures_forecast
        }
    except Exception as e:
        return {"error": str(e)}

# Add this to api.py
@app.get("/api/bracket/{tournament_id}")
def get_bracket(tournament_id: str):
    # This calls your TournamentGraphGenerator logic
    # For now, we return the structured rounds
    try:
        res = supabase.table("matches").select("*").eq("tournament_id", tournament_id).execute()
        # Logic to group matches by 'round_name' (QF, Semi-Final, Final)
        return {"rounds": organized_matches} 
    except Exception as e:
        return {"error": str(e)}
