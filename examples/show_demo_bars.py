# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.2
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

import sys
import os
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.utils.data_generation.bars import create_bar, create_bar_series
from suite_trading.utils.data_generation.price_patterns import linear_function, sine_wave_function, zig_zag_function
import plotly.graph_objects as go
import pandas as pd

# %%

# %%

# Add the src directory to the Python path
this_notebook_dir = os.getcwd()  # Get current working directory
sys.path.append(os.path.abspath(os.path.join(this_notebook_dir, "..", "src")))


# %%


# %%


def candlestick_chart(bars: list[Bar]):
    # Extract data from bars for visualization
    data = {
        "date": [bar.end_dt for bar in bars],
        "open": [float(bar.open) for bar in bars],
        "high": [float(bar.high) for bar in bars],
        "low": [float(bar.low) for bar in bars],
        "close": [float(bar.close) for bar in bars],
        "volume": [float(bar.volume) for bar in bars],
    }

    # Create a pandas DataFrame
    df = pd.DataFrame(data)

    # Create chart
    fig = (
        # Candlestick chart
        go.Figure(data=[go.Candlestick(x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"])])
        # Tune chart settings
        .update_layout(
            title="Demo Bars Visualization",
            xaxis_title="Date",
            yaxis_title="Price",
            xaxis_rangeslider_visible=False,
            height=600,
        )
    )

    return fig


# %%


def downtrend_function(x):
    return linear_function(x=x, start_price=1.0, trend_rate=-0.01)  # (0.01 = 1% increase per bar)


bars = create_bar_series(
    first_bar=create_bar(is_bullish=True),
    num_bars=20,
    price_pattern_func=downtrend_function,
)

candlestick_chart(bars).show()


# %%


bars = create_bar_series(first_bar=create_bar(is_bullish=True), num_bars=100, price_pattern_func=sine_wave_function)

candlestick_chart(bars).show()


# %%


def custom_sine_function(x):
    return sine_wave_function(x, amplitude=0.02, frequency=0.2)


bars = create_bar_series(
    first_bar=create_bar(is_bullish=True),
    num_bars=100,
    price_pattern_func=custom_sine_function,
)

candlestick_chart(bars).show()


# %%


# Note: We subtract 1.0 because sine_wave_function returns values centered around start_price (default 1.0)
def combined_pattern_function(x, **kwargs):
    return linear_function(x, trend_rate=-0.0001) + sine_wave_function(x, amplitude=0.01, frequency=0.1) - 1.0


bars = create_bar_series(first_bar=create_bar(is_bullish=True), num_bars=500, price_pattern_func=combined_pattern_function)

candlestick_chart(bars).show()


# %%


bars = create_bar_series(first_bar=create_bar(is_bullish=True), num_bars=100, price_pattern_func=zig_zag_function)

candlestick_chart(bars).show()
