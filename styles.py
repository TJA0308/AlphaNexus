import streamlit as st

def apply_custom_theme():
    """Injects professional dark-mode CSS overrides to kill the generic Streamlit look."""
    st.markdown("""
        <style>
        div[data-testid="stMetricValue"] {
            font-size: 32px;
            font-weight: 700;
            color: #00ffcc !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #a3a8b4 !important;
        }
        .stButton>button {
            border-radius: 4px;
            background-color: #1e293b;
            color: white;
            border: 1px solid #334155;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            border-color: #00ffcc;
            color: #00ffcc;
            box-shadow: 0px 0px 10px rgba(0, 255, 204, 0.2);
        }
        </style>
    """, unsafe_allow_html=True)
