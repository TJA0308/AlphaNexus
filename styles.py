import streamlit as st


def apply_custom_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #0f141b;
            color: #e8edf5;
        }

        h1 {
            letter-spacing: 0;
            font-size: 2rem;
            margin-bottom: 0.25rem;
        }

        [data-testid="stSidebar"] {
            background: #151b24;
            border-right: 1px solid #273142;
        }

        [data-testid="stMetric"] {
            background: #151b24;
            border: 1px solid #273142;
            border-radius: 8px;
            padding: 1rem;
        }

        [data-testid="stMetricLabel"] {
            color: #9aa4b2;
            font-size: 0.78rem;
            font-weight: 600;
        }

        [data-testid="stMetricValue"] {
            color: #f4f7fb;
            font-size: 1.45rem;
            font-weight: 700;
        }

        .assumption-bar {
            align-items: center;
            background: #151b24;
            border: 1px solid #273142;
            border-radius: 8px;
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin: 1rem 0;
            padding: 0.75rem;
        }

        .assumption-bar span {
            background: #202a38;
            border: 1px solid #334155;
            border-radius: 999px;
            color: #cbd5e1;
            font-size: 0.8rem;
            padding: 0.35rem 0.65rem;
        }

        .stButton > button {
            border-radius: 8px;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
