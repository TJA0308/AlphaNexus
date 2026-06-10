# 🏛️ AlphaNexus: Multi-Asset Quantitative Analytics Suite

[![Streamlit App](https://streamlit.io)](https://alphanexus-quant-suite-bhgxqgycviuhee4y8gh927.streamlit.app/)

An institutional-grade algorithmic backtesting platform evaluating volatility structures and portfolio risk metrics across top tech assets and cryptocurrencies. 

This interactive sandbox replicates a quantitative trading desk environment. It downloads live Wall Street data, executes trend-following breakout rules, and outputs institutional performance metrics—all within a clean web browser workspace.

---

## 🛠️ Tech Stack & Architecture

*   **Language:** Python 3.13
*   **Data Architecture:** Pandas (Vectorized multi-asset timelines), NumPy (Matrix risk optimization)
*   **Financial Pipeline:** Yahoo Finance API (`yfinance`)
*   **Application Interface:** Streamlit Engine (Dynamic state-cached rendering)

---

## 🚀 Key Functional Capabilities

*   **Zero-Lag Data Pipeline:** Connects directly to global market liquidity pools with memory-cached structures to allow instant asset swapping without network bottlenecks.
*   **Adaptive Volatility Engine:** Dynamically maps rolling 20-day Simple Moving Averages and statistical standard deviation channels (Bollinger Bands).
*   **Algorithmic Risk Management:** Simulates real-world execution using cash ledger assets, automated trend breakout entry rules, and trailing baseline stop-liquidations.
*   **Institutional Portfolio Metrics:** Evaluates strategy efficacy using advanced performance metrics including Cumulative Returns, Strategy Alpha, Maximum Drawdown (Risk profile), and the Sharpe Ratio (Capital efficiency).

---

## 🎛️ Dynamic Sandbox Configurations

The interactive control panel gives users the capability to isolate variables and stress-test the algorithm:
1.  **Asset Allocation Selector:** Swap instantaneously between `NVDA`, `AAPL`, `MSFT`, `AMZN`, `GOOGL`, and `BTC-USD`.
2.  **Channel Baseline Slider:** Alter the lookback duration to evaluate short-term vs. macro momentum.
3.  **Band Width Sensitivity Tuner:** Tighten or loosen the statistical standard deviation boundaries to increase or decrease trade execution velocity.

---

## 💻 Local Quickstart Installation

To run this environment locally on your desktop machine, follow these steps:

1. Clone the project files into your local directory.
2. Ensure you have your dependencies installed via your terminal terminal:
   ```bash
   pip install yfinance pandas numpy streamlit
   ```
3. Initialize the local engine server using the Streamlit deployment framework:
   ```bash
   streamlit run app.py
   ```
4. Open your browser environment and navigate to `http://localhost:8501`.
