# engine.py
import os
from supabase import create_client, Client
import math

# 1. CONNECT TO SUPABASE (Replace with your actual keys from Supabase Dashboard)
SUPABASE_URL = 'https://rmdgclazpbkypyhiouqa.supabase.co'
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJtZGdjbGF6cGJreXB5aGlvdXFhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAzNTM2NzIsImV4cCI6MjA4NTkyOTY3Mn0.fA3JNYxszcIuh71L4YlLTGD6obf1RT9KzSKhrubmzJw"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. THE ELO CONFIGURATION
INITIAL_RATING = 1500
K_FACTOR = 32 # Base volatility

def calculate_expected_score(rating_a, rating_b):
    """Calculates the probability (0 to 1) of Team A beating Team B."""
    return 1 / (1 + math.pow(10, (rating_b - rating_a) / 400))

def calculate_mov_multiplier(score_a, score_b):
    """
    Custom 'Fight-Hard' Multiplier. 
    A bigger point difference means a bigger rating swing.
    """
    diff = abs((score_a or 0) - (score_b or 0))
    # Formula: log of point diff increases the multiplier slightly
    return math.log(diff + 1) * 0.8 if diff > 0 else 1

def generate_power_rankings(tournament_id):
    """Fetches matches and runs the Elo algorithm chronologically."""
    
    # Fetch all finished matches for this tournament
    response = supabase.table("matches").select("*").eq("tournament_id", tournament_id).eq("status", "finished").order("match_index").execute()
    matches = response.data
    
    ratings = {}

    for match in matches:
        team_a = match['team_a']
        team_b = match['team_b']
        score_a = match['score_a'] or 0
        score_b = match['score_b'] or 0
        winner = match['winner']
        
        # Ignore placeholders or incomplete data
        if not team_a or not team_b or 'TBD' in team_a or 'TBD' in team_b or not winner:
            continue
            
        # Initialize teams if they don't exist
        if team_a not in ratings: ratings[team_a] = INITIAL_RATING
        if team_b not in ratings: ratings[team_b] = INITIAL_RATING

        rA = ratings[team_a]
        rB = ratings[team_b]

        # Calculate Expected Win Probabilities
        expected_a = calculate_expected_score(rA, rB)
        expected_b = calculate_expected_score(rB, rA)

        # Actual Results (1 for win, 0 for loss)
        actual_a = 1 if winner == team_a else 0
        actual_b = 1 if winner == team_b else 0

        # Apply Fight-Hard Margin of Victory multiplier
        mov = calculate_mov_multiplier(score_a, score_b)
        adjusted_k = K_FACTOR * mov

        # Update Ratings
        ratings[team_a] = round(rA + adjusted_k * (actual_a - expected_a))
        ratings[team_b] = round(rB + adjusted_k * (actual_b - expected_b))

    # Sort teams by their new Power Rating
    ranked_teams = sorted(ratings.items(), key=lambda item: item[1], reverse=True)
    
    return [{"team": t[0], "power_rating": t[1]} for t in ranked_teams]

# --- TEST THE ENGINE ---
if __name__ == "__main__":
    # Replace with a real tournament ID from your database
    TEST_TOURNAMENT_ID = "your-tournament-uuid-here" 
    
    print("🧠 Booting ShuttleSquads AI Engine...")
    rankings = generate_power_rankings(TEST_TOURNAMENT_ID)
    
    print("\n🏆 GLOBAL POWER RANKINGS 🏆")
    for idx, team in enumerate(rankings):
        print(f"#{idx + 1}: {team['team']} (Elo: {team['power_rating']})")