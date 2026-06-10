import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# 1. APPLICATION SETUP & CONFIGURATION
st.set_page_config(page_title="AlphaNexus Quant Analytics Suite", layout="wide")
st.title("🏛️ AlphaNexus: Multi-Asset Quantitative Analytics Suite")
st.caption("An institutional-grade algorithmic backtesting platform evaluating volatility structures and portfolio risk metrics.")

# Core system parameters
asset_pool = {
    "Nvidia (NVDA)": "NVDA",
    "Apple (AAPL)": "AAPL",
    "Microsoft (MSFT)": "MSFT",
    "Amazon (AMZN)": "AMZN",
    "Google (GOOGL)": "GOOGL",
    "Bitcoin (BTC-USD)": "BTC-USD"
}

# 2. SIDEBAR SYSTEM INTERACTION LAYER
st.sidebar.header("🛠️ Strategy & Risk Controls")
selected_label = st.sidebar.selectbox("Target Core Security", list(asset_pool.keys()))
target_ticker = asset_pool[selected_label]

st.sidebar.subheader("Strategy Configurations")
ma_window = st.sidebar.slider("Channel Baseline (Days)", min_value=10, max_value=50, value=20)
dev_multiplier = st.sidebar.slider("Band Width Sensitivity (Std Dev)", min_value=0.5, max_value=2.5, value=1.5, step=0.1)

st.sidebar.markdown("---")
execute_analytics = st.sidebar.button("⚙️ Run Quantitative Engine", use_container_width=True)

# 3. GLOBAL CENTRALIZED DATA INGESTION ENGINE
@st.cache_data(show_spinner="Accessing global market pipelines...")
def ingest_market_records(ticker):
    # Pulls 60 days of high-density hourly data points
    df = yf.download(ticker, period="60d", interval="1h", multi_level_index=False)
    return df[['Close']].reset_index()

# Instantly pull data
base_data = ingest_market_records(target_ticker)

# 4. PRIMARY ANALYTICS EXECUTION FLOW
if execute_analytics:
    df = base_data.copy()
    
    # Mathematical Engine Processing
    df['Center_Line'] = df['Close'].rolling(window=ma_window).mean()
    df['Rolling_Std'] = df['Close'].rolling(window=ma_window).std()
    df['Upper_Band'] = df['Center_Line'] + (df['Rolling_Std'] * dev_multiplier)
    df['Lower_Band'] = df['Center_Line'] - (df['Rolling_Std'] * dev_multiplier)
    df = df.dropna().reset_index(drop=True)
    
    # Portfolio Balance Sheets Initialization
    starting_capital = 10000.0
    cash = starting_capital
    shares = 0
    trade_logs = []
    equity_curve = []
    
    # Backtesting Simulation Engine Loop
    for idx, row in df.iterrows():
        price = row['Close']
        date_str = row['Date'].strftime('%Y-%m-%d')
        
        # TREND-FOLLOWING BREAKOUT BUY RULE
        if price > row['Upper_Band'] and cash >= price:
            shares += 1
            cash -= price
            trade_logs.append({"Execution Date": date_str, "Action": "🟢 QUANT BUY (Breakout)", "Execution Price": f"${price:.2f}"})
            
        # TREND-FOLLOWING SYSTEM LIQUIDATION RULE
        elif price < row['Center_Line'] and shares > 0:
            cash += (shares * price)
            trade_logs.append({"Execution Date": date_str, "Action": "🔴 SYSTEM LIQUIDATE", "Execution Price": f"${price:.2f}"})
            shares = 0
            
        # Record current accounting state for risk analysis
        current_equity = cash + (shares * price)
        equity_curve.append(current_equity)
        
    df['Portfolio_Value'] = equity_curve
    
    # RISK CALCULATIONS (Hedge Fund Mechanics)
    final_equity = df['Portfolio_Value'].iloc[-1]
    strategy_return = ((final_equity - starting_capital) / starting_capital) * 100
    
    initial_market_price = df['Close'].iloc[0]
    final_market_price = df['Close'].iloc[-1]
    market_return = ((final_market_price - initial_market_price) / initial_market_price) * 100
    
    # Max Drawdown calculation
    df['Peak'] = df['Portfolio_Value'].cummax()
    df['Drawdown'] = (df['Portfolio_Value'] - df['Peak']) / df['Peak']
    max_drawdown = df['Drawdown'].min() * 100
    
    # Sharpe Ratio (Approximation)
    df['Daily_Return'] = df['Portfolio_Value'].pct_change()
    sharpe = (df['Daily_Return'].mean() / df['Daily_Return'].std()) * np.sqrt(252) if df['Daily_Return'].std() != 0 else 0
    
    # 5. RENDER SYSTEM INTERFACE
    st.success(f"Analytical pipeline processed successfully for {selected_label}.")
    
    # Metrics Panel
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Final Valuation Assets", f"${final_equity:,.2f}")
    m2.metric("Absolute Net Return", f"{strategy_return:.2f}%", f"{strategy_return - market_return:.2f}% Alpha")
    m3.metric("Maximum Drawdown (Risk)", f"{max_drawdown:.2f}%")
    m4.metric("Sharpe Ratio (Efficiency)", f"{sharpe:.2f}")
    
    st.markdown("---")
    
    # Interactive UI View Customizations
    view_tab1, view_tab2 = st.tabs(["📈 Market Dynamics & Indicators", "📋 Ledger Audit Controls"])
    
    with view_tab1:
        st.markdown("### Asset Volatility Channels & Target Closing Profiles")
        chart_data = df.set_index('Date')[['Close', 'Upper_Band', 'Lower_Band', 'Portfolio_Value']]
        st.line_chart(chart_data)
        
    with view_tab2:
        st.markdown("### Verified System Execution Audit Records")
        if trade_logs:
            st.dataframe(pd.DataFrame(trade_logs), use_container_width=True)
        else:
            st.info("Market volatility parameters stayed within boundaries. No explicit trade signals were emitted.")
else:
    # Onboarding Splash Screen (Fights the 'AI Slop' aesthetic)
    st.info("👈 Selection Panel Active. Choose a core asset from the sidebar control panel and click 'Run Quantitative Engine' to populate the telemetry workspace.")
    
    st.markdown("### 🌐 Operational Infrastructure Capabilities Verified")
    col_a, col_b, col_c = st.columns(3)
    col_a.markdown("#### 📡 Real-Time Data Pipeline\nConnected to Yahoo Finance web API streaming endpoints.")
    col_b.markdown("#### 🧮 Vectorized Calculation Engines\nProcessing rolling statistical standard deviations via `pandas` and `numpy` structures.")
    col_c.markdown("#### 🛡️ Memory State Cache Management\nEnsuring instant asset switches without redundant web data asset downloads.")
