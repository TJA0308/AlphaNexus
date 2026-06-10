import pandas as pd
import numpy as np

def run_bollinger_breakout(df, ma_window, dev_multiplier):
    """Calculates a volatility breakout strategy using Bollinger Bands."""
    df['Center_Line'] = df['Close'].rolling(window=ma_window).mean()
    df['Rolling_Std'] = df['Close'].rolling(window=ma_window).std()
    df['Upper_Band'] = df['Center_Line'] + (df['Rolling_Std'] * dev_multiplier)
    df['Lower_Band'] = df['Center_Line'] - (df['Rolling_Std'] * dev_multiplier)
    df = df.dropna().reset_index(drop=True)
    
    # Vectorized execution signals
    df['Buy_Signal'] = np.where(df['Close'] > df['Upper_Band'], 1, 0)
    df['Sell_Signal'] = np.where(df['Close'] < df['Center_Line'], 1, 0)
    return df

def run_rsi_momentum(df, rsi_window=14, oversold=30, overbought=70):
    """Calculates an RSI momentum strategy."""
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=rsi_window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_window).mean()
    
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    df = df.dropna().reset_index(drop=True)
    
    # Vectorized signals: Buy when oversold, Sell when overbought
    df['Buy_Signal'] = np.where(df['RSI'] < oversold, 1, 0)
    df['Sell_Signal'] = np.where(df['RSI'] > overbought, 1, 0)
    
    # Placeholders to keep charting layout identical
    df['Upper_Band'] = overbought
    df['Lower_Band'] = oversold
    return df
