# engine.py
import os
from supabase import create_client, Client
import math

# 1. CONNECT TO SUPABASE (Replace with your actual keys from Supabase Dashboard)
SUPABASE_URL = 'https://rmdgclazpbkypyhiouqa.supabase.co'
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJtZGdjbGF6cGJreXB5aGlvdXFhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAzNTM2NzIsImV4cCI6MjA4NTkyOTY3Mn0.fA3JNYxszcIuh71L4YlLTGD6obf1RT9KzSKhrubmzJw"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. GLICKO-2 MATH ENGINE
class Glicko2Team:
    def __init__(self, rating=1500, rd=350, vol=0.06):
        # Convert to Glicko-2 scale
        self.rating = (rating - 1500) / 173.7178
        self.rd = rd / 173.7178
        self.vol = vol

    def _g(self, rd):
        return 1 / math.sqrt(1 + 3 * (rd ** 2) / (math.pi ** 2))

    def _E(self, rating, other_rating, other_rd):
        return 1 / (1 + math.exp(-self._g(other_rd) * (rating - other_rating)))

    def update(self, opponent_rating, opponent_rd, outcome):
        # outcome: 1 for win, 0 for loss
        opp_g_rating = (opponent_rating - 1500) / 173.7178
        opp_g_rd = opponent_rd / 173.7178

        g_phi = self._g(opp_g_rd)
        E = self._E(self.rating, opp_g_rating, opp_g_rd)

        # Prevent division by zero if E is exactly 1 or 0
        v_denominator = (g_phi ** 2) * E * (1 - E)
        v = 1 / v_denominator if v_denominator > 0 else 9999
        
        new_vol = self.vol # Simplified volatility for webhook speed
        
        # Update Rating Deviation (RD)
        rd_star = math.sqrt(self.rd ** 2 + new_vol ** 2)
        new_rd = 1 / math.sqrt((1 / rd_star ** 2) + (1 / v))

        # Update Rating
        new_rating = self.rating + (new_rd ** 2) * g_phi * (outcome - E)

        # Convert back to standard Elo-style scale
        return {
            "rating": round(new_rating * 173.7178 + 1500, 2),
            "rd": round(new_rd * 173.7178, 2),
            "volatility": new_vol
        }

def calculate_glicko2_match(team_a_stats, team_b_stats, winner):
    """Takes current stats and winner, returns updated stats for both."""
    team_a = Glicko2Team(team_a_stats['rating'], team_a_stats['rd'], team_a_stats['volatility'])
    team_b = Glicko2Team(team_b_stats['rating'], team_b_stats['rd'], team_b_stats['volatility'])
    
    outcome_a = 1 if winner == "team_a" else 0
    outcome_b = 1 if winner == "team_b" else 0

    new_a = team_a.update(team_b_stats['rating'], team_b_stats['rd'], outcome_a)
    new_b = team_b.update(team_a_stats['rating'], team_a_stats['rd'], outcome_b)
    
    return new_a, new_b

# 3. REFACTORED O(1) POWER RANKINGS GENERATOR
def generate_power_rankings(tournament_id):
    """
    Lightning-fast read! No more looping through history. 
    Just grabs the pre-calculated numbers from the database.
    """
    response = supabase.table("team_ratings").select("*").eq("tournament_id", tournament_id).order("rating", desc=True).execute()
    
    # Format exactly as your frontend expects
    return [{"team": row["team_name"], "power_rating": round(row["rating"])} for row in response.data]
