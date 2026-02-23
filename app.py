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

# --- CUSTOM CSS FOR HIGH-VISIBILITY LIGHT MODE ---
st.markdown("""
    <style>
    /* Light Theme Base */
    .stApp { background-color: #f8fafc; color: #0f172a; }
    
    /* Gradient Title */
    .big-font {
        font-size: 3.5rem !important;
        font-weight: 900;
        background: linear-gradient(135deg, #4f46e5, #2563eb, #0ea5e9);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
        line-height: 1.2;
    }
    .sub-font { color: #64748b; font-size: 1.1rem; font-weight: 700; margin-top: -5px; margin-bottom: 30px; letter-spacing: 2px; text-transform: uppercase;}
    
    /* Crisp Metric Cards */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        color: #0f172a;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border-color: #cbd5e1;
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
    
    /* Team Predictor Boxes */
    .team-box-blue { background-color: #ffffff; padding: 20px; border-radius: 12px; border-top: 4px solid #3b82f6; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); color: #0f172a;}
    .team-box-red { background-color: #ffffff; padding: 20px; border-radius: 12px; border-top: 4px solid #ef4444; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); color: #0f172a;}
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown('<p class="big-font">ShuttleSquads Pro</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-font">Next-Gen Predictive Analytics Engine</p>', unsafe_allow_html=True)

# --- CACHED DATA FETCHING ---
@st.cache_data(ttl=60, show_spinner=False)
def fetch_rankings(t_id):
    api_url = f"https://shuttlesquadspro.onrender.com/api/power-rankings/{t_id}"
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()
    return {"error": f"HTTP {response.status_code}"}

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.image("logo.png", width=150) # Assuming your custom logo is named logo.png
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
                
                df = pd.DataFrame(rankings)
                df.index = df.index + 1
                
                def get_tier(elo):
                    if elo >= 1550: return "🏆 S-Tier (Favorite)"
                    elif elo >= 1515: return "🥇 A-Tier (Contender)"
                    elif elo >= 1485: return "🥈 B-Tier (Mid-Table)"
                    else: return "🥉 C-Tier (Underdog)"
                    
                def get_color(elo):
                    if elo >= 1550: return "#8b5cf6" # Purple
                    elif elo >= 1515: return "#3b82f6" # Blue
                    elif elo >= 1485: return "#10b981" # Green
                    else: return "#ef4444" # Red
                    
                df["Form"] = df["power_rating"].apply(get_tier)
                df["Color"] = df["power_rating"].apply(get_color)
                
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
                
                tab1, tab2, tab3 = st.tabs(["🏟️ Global Leaderboard", "⚔️ Head-to-Head Predictor", "📈 Visual Insights"])
                
                with tab1:
                    display_df = df.drop(columns=["Color"]).rename(columns={"team": "Franchise", "power_rating": "Power Rating (Elo)"})
                    st.dataframe(
                        display_df,
                        column_config={
                            "Franchise": st.column_config.TextColumn("Team Name", width="medium"),
                            "Power Rating (Elo)": st.column_config.ProgressColumn("Live Elo Rating", format="%d ⚡", min_value=1300, max_value=1700),
                            "Form": st.column_config.TextColumn("AI Projection", width="large")
                        },
                        width="stretch",
                        height=400
                    )

                with tab2:
                    st.markdown("### 🤖 Matchup Simulator & Odds")
                    
                    team_names = df["team"].tolist()
                    pred_col1, pred_col2, pred_col3 = st.columns([3, 1, 3])
                    
                    with pred_col1:
                        st.markdown("<div class='team-box-blue'>", unsafe_allow_html=True)
                        team_a_sel = st.selectbox("Select Blue Corner", team_names, index=0)
                        team_a_elo = df[df['team'] == team_a_sel]['power_rating'].values[0]
                        st.markdown(f"**Elo:** {team_a_elo} ⚡")
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                    with pred_col2:
                        st.markdown("<p class='vs-text'>VS</p>", unsafe_allow_html=True)
                        
                    with pred_col3:
                        st.markdown("<div class='team-box-red'>", unsafe_allow_html=True)
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
                            
                        # Crisp Progress Bar for Light Mode
                        st.markdown(f"""
                            <div style="display: flex; justify-content: space-between; margin-top: 25px; margin-bottom: 8px; font-size: 0.9rem; font-weight: 800; color: #334155;">
                                <span style="color: #2563eb;">🔵 {team_a_sel} ({prob_a*100:.1f}%)</span>
                                <span style="color: #dc2626;">🔴 {team_b_sel} ({prob_b*100:.1f}%)</span>
                            </div>
                            <div style="width: 100%; height: 26px; border-radius: 13px; border: 1px solid #cbd5e1; box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
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
                            prob = 0.5 if a == b else expected_win_prob(df[df['team'] == a]['power_rating'].values[0], df[df['team'] == b]['power_rating'].values[0])
                            matrix_data.append({'Team A (Row)': a, 'Team B (Col)': b, 'Win Probability': prob})
                            
                        heatmap = alt.Chart(pd.DataFrame(matrix_data)).mark_rect().encode(
                            y=alt.Y('Team A (Row):N', title="Winner (Row)"),
                            x=alt.X('Team B (Col):N', title="Loser (Col)"),
                            color=alt.Color('Win Probability:Q', scale=alt.Scale(scheme='viridis'), legend=alt.Legend(format=".0%")),
                            tooltip=['Team A (Row):N', 'Team B (Col):N', alt.Tooltip('Win Probability:Q', format='.1%')]
                        ).properties(height=350).configure_view(strokeWidth=0)
                        st.altair_chart(heatmap, width="stretch")

        except Exception as e:
            st.error(f"📡 Connection failed. Error: {e}")
else:
    st.info("👈 Enter your Tournament ID in the sidebar and click 'Initialize 🚀' to begin.")
