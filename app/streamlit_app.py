from pathlib import Path

import streamlit as st

from edition_context import (
    get_data_coverage,
    render_coverage_notice,
    render_edition_selector,
)
from fifa_pdf_data import FifaPdfData


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


control_col, source_col = st.columns([1, 4])
with control_col:
    selected_edition = render_edition_selector(st)
with source_col:
    fifa_data = FifaPdfData.load() if selected_edition == 2026 else None
    coverage = get_data_coverage(
        selected_edition,
        fifa_data_available=bool(fifa_data and fifa_data.available),
    )
    render_coverage_notice(st, coverage)


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
