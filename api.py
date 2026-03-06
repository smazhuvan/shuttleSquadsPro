# api.py
import uuid
import math
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

        # 1. Fetch Current Tournament Ratings & Matches
        ratings_res = supabase.table("team_ratings").select("*").eq("tournament_id", tournament_id).order("rating", desc=True).execute()
        matches_res = supabase.table("matches").select("*").eq("tournament_id", tournament_id).eq("status", "finished").execute()
        
        # 2. NEW: Fetch Global Player History!
        # Extract all individual player names from the team strings (e.g. "Lawrence - Divek" -> "Lawrence", "Divek")
        all_player_names = set()
        for r in ratings_res.data:
            # We replace common separators just in case your data entry varies
            players = [p.strip() for p in r["team_name"].replace('/', '-').replace('&', '-').split('-')]
            for p in players:
                if p: all_player_names.add(p)

        # Query the global 'players' table for everyone in this tournament
        players_res = supabase.table("global_players").select("*").in_("name", list(all_player_names)).execute()
        
        # Create a fast lookup dictionary: {"Lawrence": {career_data...}, "Divek": {career_data...}}
        global_players = {p["name"]: p for p in players_res.data} if players_res.data else {}

        # 3. Process current tournament metrics (DQ, Clutch)
        matches = matches_res.data or []
        team_stats = {}
        for m in matches:
            t1, t2 = m.get("team_a"), m.get("team_b")
            s1, s2 = m.get("score_a", 0), m.get("score_b", 0)
            winner = m.get("winner")

            if not t1 or not t2 or s1 is None or s2 is None: continue

            for t in [t1, t2]:
                if t not in team_stats:
                    team_stats[t] = {"scored": 0, "conceded": 0, "clutch_games": 0, "clutch_wins": 0}

            team_stats[t1]["scored"] += s1
            team_stats[t1]["conceded"] += s2
            team_stats[t2]["scored"] += s2
            team_stats[t2]["conceded"] += s1

            if abs(s1 - s2) <= 3:
                team_stats[t1]["clutch_games"] += 1
                team_stats[t2]["clutch_games"] += 1
                if winner == t1: team_stats[t1]["clutch_wins"] += 1
                if winner == t2: team_stats[t2]["clutch_wins"] += 1

        # 4. Format the final payload with BOTH Current and Historical data
        enriched_rankings = []
        for r in ratings_res.data:
            team_name = r["team_name"]
            stats = team_stats.get(team_name, {"scored": 1, "conceded": 1, "clutch_games": 0, "clutch_wins": 0})
            
            conceded = stats["conceded"] if stats["conceded"] > 0 else 1
            dq = round(stats["scored"] / conceded, 2)
            clutch_rate = round((stats["clutch_wins"] / stats["clutch_games"]) * 100, 1) if stats["clutch_games"] > 0 else 0.0

            # --- NEW: Career Aggregation Math ---
            team_players = [p.strip() for p in team_name.replace('/', '-').replace('&', '-').split('-')]
            career_matches = 0
            career_wins = 0
            career_tfp = 0
            career_trp = 0

            for p in team_players:
                if p in global_players:
                    gp = global_players[p]
                    career_matches += gp.get("career_matches", 0)
                    career_wins += gp.get("career_wins", 0)
                    career_tfp += gp.get("career_tfp", 0)
                    career_trp += gp.get("career_trp", 0)

            # Combined Career Metrics for this specific duo
            career_win_rate = round((career_wins / career_matches * 100), 1) if career_matches > 0 else 0.0
            career_dq = round((career_tfp / career_trp), 2) if career_trp > 0 else 1.0

            enriched_rankings.append({
                "team": team_name,
                "power_rating": round(r["rating"]),
                "volatility": round(r.get("volatility", 0.06), 3),
                "dominance_quotient": dq,
                "clutch_win_rate": clutch_rate,
                "giant_killer": dq > 1.0 and round(r["rating"]) < 1550,
                
                # Injected Global Stats
                "career_matches": career_matches,
                "career_win_rate": career_win_rate,
                "career_dq": career_dq,
                "veteran_status": career_matches >= 10  # Flags if they are highly experienced
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

    # Only process if the match was just marked as finished
    if match.status != "finished" or (payload.old_record and payload.old_record.get("status") == "finished"):
        return {"status": "ignored", "reason": "Match not newly finished"}

    team_a, team_b, winner_name = match.team_a, match.team_b, match.winner
    tourney_id = match.tournament_id
    
    # Map winner string to key for the Glicko engine
    winner_key = "team_a" if winner_name == team_a else ("team_b" if winner_name == team_b else "draw")

    try:
        # ====================================================================
        # 1. UPDATE TOURNAMENT-SPECIFIC RATINGS (Your existing logic)
        # ====================================================================
        res = supabase.table("team_ratings").select("*").in_("team_name", [team_a, team_b]).eq("tournament_id", tourney_id).execute()
        current_data = {row["team_name"]: row for row in res.data}

        stats_a = current_data.get(team_a, {"rating": 1500.0, "rd": 350.0, "volatility": 0.06, "matches_played": 0})
        stats_b = current_data.get(team_b, {"rating": 1500.0, "rd": 350.0, "volatility": 0.06, "matches_played": 0})

        new_a, new_b = calculate_glicko2_match(stats_a, stats_b, winner_key)

        supabase.table("team_ratings").upsert([
            {"team_name": team_a, "tournament_id": tourney_id, "matches_played": stats_a.get("matches_played", 0) + 1, **new_a},
            {"team_name": team_b, "tournament_id": tourney_id, "matches_played": stats_b.get("matches_played", 0) + 1, **new_b}
        ]).execute()

        # ====================================================================
        # 2. THE NEW GLOBAL ELO ENGINE (Individual Player Tracking)
        # ====================================================================
        
        # A. Get the Organizer ID to find the correct Global Players
        t_res = supabase.table("tournaments").select("organizer_id").eq("id", tourney_id).execute()
        if not t_res.data:
            return {"status": "success", "message": "Local updated. Tournament not found for global update."}
        organizer_id = t_res.data[0]["organizer_id"]

        # B. Split team strings into individual players (handles singles & doubles seamlessly)
        players_a = [p.strip() for p in team_a.replace('/', '-').replace('&', '-').split('-') if p.strip()]
        players_b = [p.strip() for p in team_b.replace('/', '-').replace('&', '-').split('-') if p.strip()]
        all_players = players_a + players_b

        # C. Fetch their current global stats from the Vault
        gp_res = supabase.table("global_players").select("id, name, global_elo, global_rd, global_volatility").in_("name", all_players).eq("organizer_id", organizer_id).execute()
        gp_dict = {p["name"]: p for p in gp_res.data} if gp_res.data else {}

        # D. Helper function: Average the Elo of two players for a Doubles match
        def get_team_avg_stats(player_names):
            if not player_names: return {"rating": 1500.0, "rd": 350.0, "volatility": 0.06}
            
            # Use 1500 as a default if a player isn't in the global vault yet
            avg_rating = sum([gp_dict.get(p, {}).get("global_elo", 1500.0) for p in player_names]) / len(player_names)
            avg_rd = sum([gp_dict.get(p, {}).get("global_rd", 350.0) for p in player_names]) / len(player_names)
            avg_vol = sum([gp_dict.get(p, {}).get("global_volatility", 0.06) for p in player_names]) / len(player_names)
            
            return {"rating": avg_rating, "rd": avg_rd, "volatility": avg_vol}

        global_stats_a = get_team_avg_stats(players_a)
        global_stats_b = get_team_avg_stats(players_b)

        # E. Calculate the Global Shift
        global_new_a, global_new_b = calculate_glicko2_match(global_stats_a, global_stats_b, winner_key)
        
        # Figure out exactly how many points the team gained or lost
        delta_rating_a = global_new_a["rating"] - global_stats_a["rating"]
        delta_rating_b = global_new_b["rating"] - global_stats_b["rating"]

        # F. Apply the exact same delta to the individual players
        global_updates = []
        
        for p in players_a:
            # We only update players who exist in the global vault (prevents phantom spam)
            if p in gp_dict:
                old_p = gp_dict[p]
                global_updates.append({
                    "id": old_p["id"],
                    "global_elo": round(old_p.get("global_elo", 1500.0) + delta_rating_a, 2),
                    "global_rd": global_new_a["rd"],
                    "global_volatility": global_new_a["volatility"]
                })

        for p in players_b:
            if p in gp_dict:
                old_p = gp_dict[p]
                global_updates.append({
                    "id": old_p["id"],
                    "global_elo": round(old_p.get("global_elo", 1500.0) + delta_rating_b, 2),
                    "global_rd": global_new_b["rd"],
                    "global_volatility": global_new_b["volatility"]
                })

        # G. Save individual player ratings back to Supabase
        if global_updates:
            supabase.table("global_players").upsert(global_updates).execute()

        return {"status": "success", "message": f"Dual-Layer AI Update Complete for {team_a} and {team_b}"}

    except Exception as e:
        print(f"Webhook Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/backfill-elo")
async def backfill_historical_elo():
    try:
        # 1. Fetch ALL finished matches in chronological order
        matches_res = supabase.table("matches").select("*").eq("status", "finished").order("created_at").execute()
        matches = matches_res.data or []

        if not matches:
            return {"message": "No historical matches found."}

        # 2. Fetch all global players and cache their details
        gp_res = supabase.table("global_players").select("id, name, organizer_id").execute()
        
        # Dictionary format: {"Lin Dan": {"id": "uuid", "name": "Lin Dan", "org_id": "uuid", ...}}
        gp_dict = {
            p["name"]: {
                "id": p["id"], 
                "name": p["name"],           # <--- CAPTURE NAME
                "org_id": p["organizer_id"],  # <--- CAPTURE ORG ID
                "rating": 1500.0, 
                "rd": 350.0, 
                "volatility": 0.06
            } 
            for p in gp_res.data
        } if gp_res.data else {}

        processed_count = 0

        # 3. Play back history chronologically
        for match in matches:
            team_a = match.get("team_a")
            team_b = match.get("team_b")
            winner_name = match.get("winner")

            if not team_a or not team_b or not winner_name: continue

            winner_key = "team_a" if winner_name == team_a else ("team_b" if winner_name == team_b else "draw")

            players_a = [p.strip() for p in team_a.replace('/', '-').replace('&', '-').split('-') if p.strip()]
            players_b = [p.strip() for p in team_b.replace('/', '-').replace('&', '-').split('-') if p.strip()]
            
            def get_avg_stats(p_list):
                valid_players = [p for p in p_list if p in gp_dict]
                if not valid_players: return {"rating": 1500.0, "rd": 350.0, "volatility": 0.06}
                
                avg_r = sum([gp_dict[p]["rating"] for p in valid_players]) / len(valid_players)
                avg_rd = sum([gp_dict[p]["rd"] for p in valid_players]) / len(valid_players)
                avg_v = sum([gp_dict[p]["volatility"] for p in valid_players]) / len(valid_players)
                return {"rating": avg_r, "rd": avg_rd, "volatility": avg_v}

            stats_a = get_avg_stats(players_a)
            stats_b = get_avg_stats(players_b)

            new_a, new_b = calculate_glicko2_match(stats_a, stats_b, winner_key)
            
            delta_a = new_a["rating"] - stats_a["rating"]
            delta_b = new_b["rating"] - stats_b["rating"]

            for p in players_a:
                if p in gp_dict:
                    gp_dict[p]["rating"] += delta_a
                    gp_dict[p]["rd"] = new_a["rd"]
                    gp_dict[p]["volatility"] = new_a["volatility"]

            for p in players_b:
                if p in gp_dict:
                    gp_dict[p]["rating"] += delta_b
                    gp_dict[p]["rd"] = new_b["rd"]
                    gp_dict[p]["volatility"] = new_b["volatility"]
            
            processed_count += 1

        # 4. Prepare the final payload with ALL required Not-Null columns
        updates = []
        for name, data in gp_dict.items():
            if data["rating"] != 1500.0 or data["rd"] != 350.0: 
                updates.append({
                    "id": data["id"],
                    "name": data["name"],           # <--- ADDED NAME
                    "organizer_id": data["org_id"], # <--- ADDED ORG ID
                    "global_elo": round(data["rating"], 2),
                    "global_rd": round(data["rd"], 2),
                    "global_volatility": data["volatility"]
                })

        # 5. Push updates
        if updates:
            supabase.table("global_players").upsert(updates).execute()

        return {
            "status": "Time Machine Successful! ⚡", 
            "matches_processed": processed_count, 
            "players_updated": len(updates)
        }
        
    except Exception as e:
        return {"error": str(e)}
