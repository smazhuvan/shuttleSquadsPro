# api.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from engine import generate_power_rankings

app = FastAPI(title="ShuttleSquads AI Oracle")

# Allow your Vercel React app to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Change to your vercel domain later for security
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "AI Engine is Online"}

@app.get("/api/power-rankings/{tournament_id}")
def get_rankings(tournament_id: str):
    """
    Endpoint that calculates and returns real-time Power Ratings.
    """
    try:
        rankings = generate_power_rankings(tournament_id)
        return {"tournament_id": tournament_id, "rankings": rankings}
    except Exception as e:
        return {"error": str(e)}