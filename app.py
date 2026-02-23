# app.py
import streamlit as st
import requests
import pandas as pd
import altair as alt
import math
import itertools

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="ShuttleSquads Pro | AI Analytics", 
    page_icon="🔮", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS FOR PREMIUM UI (Glassmorphism & Gradients) ---
st.markdown("""
    <style>
    /* Dark Theme Base */
    .stApp { background-color: #0f172a; color: #f8fafc; }
    
    /* Gradient Title */
    .big-font {
        font-size: 3.5rem !important;
        font-weight: 900;
        background: linear-gradient(135deg, #a855f7, #6366f1, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
        line-height: 1.2;
    }
    .sub-font { color: #94a3b8; font-size: 1.1rem; font-weight: 600; margin-top: -5px; margin-bottom: 30px; letter-spacing: 2px; text-transform: uppercase;}
    
    /* Stylized Metric Cards */
    div[data-testid="metric-container"] {
        background: linear-gradient(145deg, #1e293b, #0f172a);
        border: 1px solid #334155;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
        transition: transform 0.3s ease, border-color 0.3s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-5px);
        border-color: #6366f1;
        box-shadow: 0 15px 25px -5px rgba(99, 102, 241, 0.4);
    }
    
    /* VS Text Styling */
    .vs-text {
        text-align: center;
        font-size: 2.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #ef4444, #f59e0b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-top: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown('<p class="big-font">ShuttleSquads Pro</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-font">Next-Gen Predictive Analytics Engine</p>', unsafe_allow_html=True)

# --- CACHED DATA FETCHING ---
@st.cache_data(ttl=60, show_spinner=False)
def fetch_rankings(t_id):
    api_url = f"http://localhost:8000/api/power-rankings/{t_id}"
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()
    return {"error": f"HTTP {response.status_code}"}

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    # Reliable Image Link for the Logo
    st.image("logo.png", width=200)
    
    st.header("⚡ Oracle Link")
    st.caption("Connect to a live tournament database.")
    
    tournament_id = st.text_input("Tournament ID:", value="f9fe49db-5ba4-466f-ad1f-a833e1618b09")
    
    colA, colB = st.columns(2)
    with colA:
        run_analysis = st.button("Initialize 🚀", type="primary", width="stretch")
    with colB:
        if st.button("Refresh 🔄", width="stretch"):
            st.cache_data.clear()
            st.toast("Cache cleared! Pulling fresh live data.", icon="🔥")
            st.session_state["data_loaded"] = True
    
    st.markdown("---")
    with st.expander("📖 How the AI Works", expanded=False):
        st.markdown("""
            **The Architecture:**
            * Reads live scores from Supabase.
            * Applies the **'Fight-Hard' MoV** (Margin of Victory) multiplier.
            * Punishes teams who drop easy points.
            * Baseline Elo starts at **1500**.
        """)

# --- HELPER FUNCTIONS ---
def expected_win_prob(rating_a, rating_b):
    return 1 / (1 + math.pow(10, (rating_b - rating_a) / 400))

def predict_scoreline(prob_a):
    if prob_a > 0.5:
        loser_score = int(21 * (1 - prob_a) * 1.8)
        return 21, min(max(loser_score, 0), 19)
    else:
        loser_score = int(21 * prob_a * 1.8)
        return min(max(loser_score, 0), 19), 21

# --- MAIN APP LOGIC ---
if run_analysis or "data_loaded" in st.session_state:
    st.session_state["data_loaded"] = True
    
    with st.spinner("🧠 Querying Supabase & Crunching AI Models..."):
        try:
            data = fetch_rankings(tournament_id)
            
            if "error" in data:
                st.error(f"Database Error: {data['error']}")
            elif not data.get("rankings"):
                st.warning("Awaiting data. No finished matches found in this tournament yet.")
            else:
                rankings = data["rankings"]
                
                # --- DATA PREP ---
                df = pd.DataFrame(rankings)
                df.index = df.index + 1
                
                def get_tier(elo):
                    if elo >= 1550: return "🏆 S-Tier (Favorite)"
                    elif elo >= 1515: return "🥇 A-Tier (Contender)"
                    elif elo >= 1485: return "🥈 B-Tier (Mid-Table)"
                    else: return "🥉 C-Tier (Underdog)"
                    
                def get_color(elo):
                    if elo >= 1550: return "#a855f7" 
                    elif elo >= 1515: return "#3b82f6" 
                    elif elo >= 1485: return "#10b981" 
                    else: return "#ef4444" 
                    
                df["Form"] = df["power_rating"].apply(get_tier)
                df["Color"] = df["power_rating"].apply(get_color)
                
                # --- TOP METRICS ROW ---
                col1, col2, col3 = st.columns(3)
                
                top_team = df.iloc[0]["team"]
                top_elo = df.iloc[0]["power_rating"]
                avg_elo = int(df["power_rating"].mean())
                lowest_team = df.iloc[-1]["team"]
                lowest_elo = df.iloc[-1]["power_rating"]
                
                with col1:
                    st.metric(label="👑 Apex Franchise", value=top_team, delta=f"{top_elo} ELO")
                with col2:
                    st.metric(label="📊 Global Baseline", value=f"{avg_elo} ELO", delta="Tournament Average", delta_color="off")
                with col3:
                    st.metric(label="🔥 Prime Underdog", value=lowest_team, delta=f"{lowest_elo} ELO (Upset Potential)", delta_color="inverse")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # --- INTERACTIVE TABS ---
                tab1, tab2, tab3 = st.tabs(["🏟️ Global Leaderboard", "⚔️ Head-to-Head Predictor", "📈 Visual Insights"])
                
                with tab1:
                    display_df = df.drop(columns=["Color"]).rename(columns={"team": "Franchise", "power_rating": "Power Rating (Elo)"})
                    
                    st.dataframe(
                        display_df,
                        column_config={
                            "Franchise": st.column_config.TextColumn("Team Name", width="medium"),
                            "Power Rating (Elo)": st.column_config.ProgressColumn(
                                "Live Elo Rating",
                                help="Statistically derived strength. 1500 is the starting baseline.",
                                format="%d ⚡",
                                min_value=1300, 
                                max_value=1700,
                            ),
                            "Form": st.column_config.TextColumn("AI Projection", width="large")
                        },
                        width="stretch",
                        height=400
                    )

                with tab2:
                    st.markdown("### 🤖 Matchup Simulator & Odds")
                    st.caption("Select any two teams to view the AI's predicted outcome, expected scoreline, and implied betting odds.")
                    
                    team_names = df["team"].tolist()
                    
                    pred_col1, pred_col2, pred_col3 = st.columns([3, 1, 3])
                    
                    with pred_col1:
                        st.markdown("<div style='background-color: #1e293b; padding: 20px; border-radius: 15px; border-top: 4px solid #3b82f6;'>", unsafe_allow_html=True)
                        team_a_sel = st.selectbox("Select Blue Corner", team_names, index=0)
                        team_a_elo = df[df['team'] == team_a_sel]['power_rating'].values[0]
                        st.markdown(f"**Elo:** {team_a_elo} ⚡")
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                    with pred_col2:
                        st.markdown("<p class='vs-text'>VS</p>", unsafe_allow_html=True)
                        
                    with pred_col3:
                        st.markdown("<div style='background-color: #1e293b; padding: 20px; border-radius: 15px; border-top: 4px solid #ef4444;'>", unsafe_allow_html=True)
                        team_b_sel = st.selectbox("Select Red Corner", team_names, index=len(team_names)-1)
                        team_b_elo = df[df['team'] == team_b_sel]['power_rating'].values[0]
                        st.markdown(f"**Elo:** {team_b_elo} ⚡")
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                    if team_a_sel != team_b_sel:
                        prob_a = expected_win_prob(team_a_elo, team_b_elo)
                        prob_b = 1 - prob_a
                        
                        odds_a = round(1 / prob_a, 2)
                        odds_b = round(1 / prob_b, 2)
                        
                        score_a, score_b = predict_scoreline(prob_a)
                        
                        st.markdown("---")
                        st.markdown("#### 🔮 AI Telemetry Report")
                        
                        res_col1, res_col2, res_col3 = st.columns(3)
                        
                        with res_col1:
                            st.metric(label=f"Win Prob ({team_a_sel})", value=f"{prob_a*100:.1f}%", delta=f"{odds_a}x Payout")
                        with res_col2:
                            st.metric(label="Expected Scoreline", value=f"{score_a} - {score_b}", delta="BWF 21-Pt Format", delta_color="off")
                        with res_col3:
                            st.metric(label=f"Win Prob ({team_b_sel})", value=f"{prob_b*100:.1f}%", delta=f"{odds_b}x Payout", delta_color="inverse")
                            
                        # BULLETPROOF HTML PROGRESS BAR (Using CSS Linear Gradient)
                        st.markdown(f"""
                            <div style="display: flex; justify-content: space-between; margin-top: 25px; margin-bottom: 8px; font-size: 0.9rem; font-weight: bold;">
                                <span style="color: #60a5fa;">🔵 {team_a_sel} ({prob_a*100:.1f}%)</span>
                                <span style="color: #f87171;">🔴 {team_b_sel} ({prob_b*100:.1f}%)</span>
                            </div>
                            <div style="width: 100%; height: 26px; border-radius: 13px; border: 2px solid #1e293b; 
                                 background: linear-gradient(to right, #3b82f6 {prob_a*100}%, #ef4444 {prob_a*100}%);">
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ Please select two different teams for the simulation.")

                with tab3:
                    st.markdown("### 📊 Distribution & Heatmap")
                    
                    chart_col1, chart_col2 = st.columns(2)
                    
                    with chart_col1:
                        st.markdown("**Elo Distribution Tracker**")
                        
                        # ALTAIR FIX: Single un-layered chart. 'zero=False' prevents axis zooming bugs.
                        dots = alt.Chart(df).mark_circle(size=400, opacity=1).encode(
                            x=alt.X('power_rating:Q', scale=alt.Scale(domain=[1300, int(df['power_rating'].max()) + 50], zero=False), title='Live Elo Rating'),
                            y=alt.Y('team:N', sort='-x', title=None),
                            color=alt.Color('Color:N', scale=None), 
                            tooltip=['team', 'power_rating', 'Form']
                        ).properties(height=350).configure_view(strokeWidth=0)
                        
                        st.altair_chart(dots, width="stretch")
                    
                    with chart_col2:
                        st.markdown("**All-vs-All Win Probability Matrix**")
                        matrix_data = []
                        for a, b in itertools.product(team_names, repeat=2):
                            if a == b:
                                prob = 0.5
                            else:
                                e_a = df[df['team'] == a]['power_rating'].values[0]
                                e_b = df[df['team'] == b]['power_rating'].values[0]
                                prob = expected_win_prob(e_a, e_b)
                            matrix_data.append({'Team A (Row)': a, 'Team B (Col)': b, 'Win Probability': prob})
                            
                        matrix_df = pd.DataFrame(matrix_data)
                        
                        heatmap = alt.Chart(matrix_df).mark_rect().encode(
                            y=alt.Y('Team A (Row):N', title="Simulated Winner (Row)"),
                            x=alt.X('Team B (Col):N', title="Simulated Loser (Col)"),
                            color=alt.Color('Win Probability:Q', scale=alt.Scale(scheme='viridis'), legend=alt.Legend(format=".0%")),
                            tooltip=[
                                alt.Tooltip('Team A (Row):N', title='If Team A'),
                                alt.Tooltip('Team B (Col):N', title='Plays Team B'),
                                alt.Tooltip('Win Probability:Q', title='Team A Win Prob', format='.1%')
                            ]
                        ).properties(height=350).configure_view(strokeWidth=0)
                        
                        st.altair_chart(heatmap, width="stretch")

        except Exception as e:
            st.error(f"📡 Connection failed. Ensure your FastAPI Oracle server is running on port 8000. Error: {e}")
else:
    st.info("👈 Enter your Tournament ID in the sidebar and click 'Initialize Engine' to begin.")