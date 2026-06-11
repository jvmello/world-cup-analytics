from pathlib import Path

import streamlit as st


APP_DIR = Path(__file__).parent
PAGES_DIR = APP_DIR / "pages"


st.set_page_config(
    page_title="World Cup Analytics",
    layout="wide",
)


st.markdown(
    """
    <style>
        .stApp {
            background-color: #050805;
            color: #f2f2f2;
        }

        [data-testid="stSidebarNav"] {
            display: none;
        }

        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"] {
            display: none;
        }

        div[data-testid="stTopNav"] {
            background-color: #050805;
            border-bottom: 1px solid #1d2518;
        }

        div[data-testid="stTopNav"] a {
            border-radius: 8px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            font-size: 12px;
            font-weight: 800;
        }

        div[data-testid="stTopNav"] a[aria-current="page"] {
            background: #9cff00;
            color: #050805;
            box-shadow: 0 0 18px rgba(156, 255, 0, 0.26);
        }
    </style>
    """,
    unsafe_allow_html=True,
)


navigation = st.navigation(
    [
        st.Page(
            PAGES_DIR / "4_Tournament_History.py",
            title="Competition",
            url_path="competition",
            default=True,
        ),
        st.Page(
            PAGES_DIR / "5_Team_Analytics.py",
            title="Teams",
            url_path="teams",
        ),
        st.Page(
            PAGES_DIR / "2_Player_Analytics.py",
            title="Players",
            url_path="players",
        ),
        st.Page(
            PAGES_DIR / "3_Player_Rankings.py",
            title="Rankings",
            url_path="rankings",
        ),
        st.Page(
            PAGES_DIR / "1_Player_Shot_Map.py",
            title="Shot Map",
            url_path="shot-map",
        ),
        st.Page(
            PAGES_DIR / "0_Match_Overview.py",
            title="Match Overview",
            url_path="match-overview",
        ),
    ],
    position="top",
)

navigation.run()
