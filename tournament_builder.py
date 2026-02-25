import math
import itertools
import uuid

class TournamentGraphGenerator:
    def __init__(self, total_teams, num_groups, advancing_per_group):
        self.total_teams = total_teams
        self.num_groups = num_groups
        self.advancing_per_group = advancing_per_group
        self.total_advancing = num_groups * advancing_per_group

    def _get_next_power_of_2(self, n):
        if n == 0: return 1
        return 2**math.ceil(math.log2(n))

    def generate_groups(self):
        """Generates the round-robin matches for each group."""
        matches = []
        teams_per_group = self.total_teams // self.num_groups
        
        for group_idx in range(self.num_groups):
            group_name = chr(65 + group_idx) # A, B, C...
            # Placeholder names (e.g., "Team A1", "Team A2")
            group_teams = [f"Pool {group_name} - Slot {i+1}" for i in range(teams_per_group)]
            
            # Generate all vs all in this group
            for team_a, team_b in itertools.combinations(group_teams, 2):
                matches.append({
                    "match_id": str(uuid.uuid4())[:8],
                    "stage": "Groups",
                    "group": group_name,
                    "participant_a": team_a,
                    "participant_b": team_b,
                    "next_match_id": None # Group matches don't strictly point to a knockout node yet
                })
        return matches

    def generate_knockout_graph(self, playoff_style="standard"):
        """Generates the DAG for the knockout stage, dynamically injecting IPL at the Final 4."""
        bracket_size = self._get_next_power_of_2(self.total_advancing)
        byes = bracket_size - self.total_advancing
        round_1_teams = self.total_advancing - byes
        
        nodes = []
        
        # 1. Setup Initial Seeds (1 to N)
        seeds = [f"Seed {i}" for i in range(1, self.total_advancing + 1)]
        bye_teams = seeds[:byes] # Top seeds get the byes
        playing_teams = seeds[byes:] 
        
        # 2. Generate Round 1 (Wildcards)
        round_1_matches = []
        for i in range(round_1_teams // 2):
            team_a = playing_teams[i]
            team_b = playing_teams[-(i + 1)]
            match_id = f"R1-M{i+1}"
            node = {
                "match_id": match_id,
                "stage": "Knockouts",
                "round": "Round 1 (Wildcard)",
                "participant_a": team_a,
                "participant_b": team_b,
                "next_match_id": None
            }
            nodes.append(node)
            round_1_matches.append(node)

        # 3. Generate Round 2 (Super 8 / Quarter-Finals)
        round_2_matches = []
        for i in range(bracket_size // 4):
            feeding_match_b = round_1_matches[-(i + 1)] if i < len(round_1_matches) else None
            team_b = f"Winner of {feeding_match_b['match_id']}" if feeding_match_b else "TBD"

            if i < len(bye_teams):
                team_a = bye_teams[i]
            else:
                feeding_match_a = round_1_matches[i - len(bye_teams)]
                team_a = f"Winner of {feeding_match_a['match_id']}"
                feeding_match_a["next_match_id"] = f"R2-M{i+1}"
            
            match_id = f"R2-M{i+1}"
            node = {
                "match_id": match_id,
                "stage": "Knockouts",
                "round": "Round 2",
                "participant_a": team_a,
                "participant_b": team_b,
                "next_match_id": None
            }
            nodes.append(node)
            round_2_matches.append(node)
            
            if feeding_match_b:
                feeding_match_b["next_match_id"] = match_id

        # 4. Generate Remaining Rounds (Semis, Finals, or IPL Page System)
        current_round_matches = round_2_matches
        round_num = 3
        
        while len(current_round_matches) > 1:
            
            # THE MAGIC FIX: If exactly 4 matches remain (Quarter Finals), and IPL is selected, switch tracks!
            if len(current_round_matches) == 4 and playoff_style == "ipl":
                q1 = {
                    "match_id": "Q1",
                    "stage": "Playoffs",
                    "round": "Q1 & Eliminator", # <-- Changed for clarity
                    "participant_a": f"Winner of {current_round_matches[0]['match_id']}",
                    "participant_b": f"Winner of {current_round_matches[1]['match_id']}",
                    "next_match_id": "Final-M1"
                }
                elim = {
                    "match_id": "Elim-1",
                    "stage": "Playoffs",
                    "round": "Q1 & Eliminator", # <-- Grouped together!
                    "participant_a": f"Winner of {current_round_matches[2]['match_id']}",
                    "participant_b": f"Winner of {current_round_matches[3]['match_id']}",
                    "next_match_id": "Q2"
                }
                q2 = {
                    "match_id": "Q2",
                    "stage": "Playoffs",
                    "round": "Qualifier 2", # <-- Proper explicit name
                    "participant_a": "Loser of Q1",
                    "participant_b": "Winner of Elim-1",
                    "next_match_id": "Final-M1"
                }
                final = {
                    "match_id": "Final-M1",
                    "stage": "Playoffs",
                    "round": "Championship Final",
                    "participant_a": "Winner of Q1",
                    "participant_b": "Winner of Q2",
                    "next_match_id": None
                }
                nodes.extend([q1, elim, q2, final])
                
                # Connect the Quarter Finals to the IPL Page System
                current_round_matches[0]["next_match_id"] = "Q1"
                current_round_matches[1]["next_match_id"] = "Q1"
                current_round_matches[2]["next_match_id"] = "Elim-1"
                current_round_matches[3]["next_match_id"] = "Elim-1"
                
                break # We finished the bracket, exit the loop!
            
            # --- STANDARD KNOCKOUT TRACK ---
            next_round_matches = []
            is_final = len(current_round_matches) == 2
            
            for i in range(0, len(current_round_matches), 2):
                if is_final:
                    match_id = "Final-M1"
                    round_title = "Final Match"
                else:
                    match_id = f"R{round_num}-M{i//2 + 1}"
                    round_title = f"Round {round_num}"
                    
                node = {
                    "match_id": match_id,
                    "stage": "Knockouts",
                    "round": round_title,
                    "participant_a": f"Winner of {current_round_matches[i]['match_id']}",
                    "participant_b": f"Winner of {current_round_matches[i+1]['match_id']}",
                    "next_match_id": None
                }
                nodes.append(node)
                next_round_matches.append(node)
                
                current_round_matches[i]["next_match_id"] = match_id
                current_round_matches[i+1]["next_match_id"] = match_id
                
            if is_final and playoff_style != "ipl":
                bronze_match = {
                    "match_id": "Bronze-M1",
                    "stage": "Knockouts",
                    "round": "3rd Place Match",
                    "participant_a": f"Loser of {current_round_matches[0]['match_id']}",
                    "participant_b": f"Loser of {current_round_matches[1]['match_id']}",
                    "next_match_id": None
                }
                nodes.append(bronze_match)
                
            current_round_matches = next_round_matches
            round_num += 1

        return nodes

    def build(self, playoff_style="standard"):
        """Assembles the final JSON payload."""
        return {
            "metadata": {
                "total_teams": self.total_teams,
                "groups": self.num_groups,
                "advancing_total": self.total_advancing,
            },
            "schedule_graph": {
                "group_stage": self.generate_groups() if self.num_groups > 1 else [],
                "knockout_stage": self.generate_knockout_graph(playoff_style) # Pass style dynamically!
            }
        }