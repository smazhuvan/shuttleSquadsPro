# monte_carlo.py
import random

def get_win_prob(rating_a, rating_b):
    """Calculates win probability using the standard logistic curve."""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

def run_tournament_simulation(teams, iterations=10000):
    """
    Takes the Top 8 teams and simulates a standard knockout bracket 10,000 times.
    Seed matchups: 
    Upper Bracket: (1 vs 8) vs (4 vs 5)
    Lower Bracket: (2 vs 7) vs (3 vs 6)
    """
    # Ensure we only take the top 8
    bracket_teams = teams[:8]
    
    if len(bracket_teams) < 8:
        raise ValueError("Need at least 8 teams to run the Quarter-Finals Monte Carlo.")
    
    # Initialize the tracking dictionary
    results = {
        team['team']: {'power_rating': team['power_rating'], 'semis': 0, 'finals': 0, 'championships': 0}
        for team in bracket_teams
    }
    
    for _ in range(iterations):
        # --- QUARTER FINALS ---
        # Returns the winner of each matchup based on a weighted random roll
        sf1 = bracket_teams[0] if random.random() < get_win_prob(bracket_teams[0]['power_rating'], bracket_teams[7]['power_rating']) else bracket_teams[7]
        sf2 = bracket_teams[3] if random.random() < get_win_prob(bracket_teams[3]['power_rating'], bracket_teams[4]['power_rating']) else bracket_teams[4]
        sf3 = bracket_teams[1] if random.random() < get_win_prob(bracket_teams[1]['power_rating'], bracket_teams[6]['power_rating']) else bracket_teams[6]
        sf4 = bracket_teams[2] if random.random() < get_win_prob(bracket_teams[2]['power_rating'], bracket_teams[5]['power_rating']) else bracket_teams[5]
        
        # Log semi-final appearances
        results[sf1['team']]['semis'] += 1
        results[sf2['team']]['semis'] += 1
        results[sf3['team']]['semis'] += 1
        results[sf4['team']]['semis'] += 1

        # --- SEMI FINALS ---
        f1 = sf1 if random.random() < get_win_prob(sf1['power_rating'], sf2['power_rating']) else sf2
        f2 = sf3 if random.random() < get_win_prob(sf3['power_rating'], sf4['power_rating']) else sf4
        
        # Log final appearances
        results[f1['team']]['finals'] += 1
        results[f2['team']]['finals'] += 1

        # --- CHAMPIONSHIP FINAL ---
        champ = f1 if random.random() < get_win_prob(f1['power_rating'], f2['power_rating']) else f2
        
        # Log championship rings!
        results[champ['team']]['championships'] += 1
        
    # Format the final telemetry report into percentages
    final_forecast = []
    for team, stats in results.items():
        final_forecast.append({
            "team": team,
            "power_rating": stats['power_rating'],
            "make_semis": round((stats['semis'] / iterations) * 100, 1),
            "make_finals": round((stats['finals'] / iterations) * 100, 1),
            "win_championship": round((stats['championships'] / iterations) * 100, 1)
        })
        
    # Sort by who is most likely to win the whole thing
    return sorted(final_forecast, key=lambda x: x['win_championship'], reverse=True)
