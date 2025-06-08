# ---
# jupyter:
#   jupytext:
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
from suite_trading.utils.data_generation import linear_function, sine_wave_function, zig_zag_function
import plotly.graph_objects as go

# %%
# Add the src directory to the Python path
this_notebook_dir = os.getcwd()  # Get current working directory
sys.path.append(os.path.abspath(os.path.join(this_notebook_dir, "..", "src")))

# %%


# %%
def scatter_chart(x, y):
    # Create a simple Plotly scatter chart
    fig = (
        go.Figure()
        .add_trace(
            go.Scatter(x=x, y=y, mode="lines+markers", name="Function Values", line=dict(color="blue", width=1), marker=dict(size=4, color="red")),
        )
        .update_layout(title="Function Visualization", xaxis_title="X Value", yaxis_title="Y Value", template="plotly_white")
    )

    return fig


# %%
x = list(range(150))

# %%
# Generate values
y = [linear_function(x=idx, start_price=1.0, trend_rate=+0.0010) for idx in x]
scatter_chart(x, y).show()

# %%
# Generate values
y = [sine_wave_function(x=idx, start_price=1.0, amplitude=0.5) for idx in x]
scatter_chart(x, y).show()

# %%
# Generate values
y = [linear_function(x=idx, start_price=1.0, trend_rate=0.005) + sine_wave_function(x=idx, start_price=1.0, amplitude=0.3) - 1 for idx in x]

scatter_chart(x, y).show()

# %%
# Generate values
y = [zig_zag_function(x=idx, start_price=1.0, increment=0.2, steps_up=5, steps_down=5) for idx in x]

scatter_chart(x, y).show()

# %%
# Generate values
y = [zig_zag_function(x=idx, start_price=1.0, increment=0.2, steps_up=10, steps_down=8) for idx in x]

scatter_chart(x, y).show()

# %%
# Generate values
y = [
    linear_function(x=idx, start_price=1.0, trend_rate=0.01) + zig_zag_function(x=idx, start_price=1.0, increment=0.2, steps_up=3, steps_down=2) - 1
    for idx in x
]

scatter_chart(x, y).show()

# %%
", ".join([str(i) for i in x])

# %%
", ".join([str(round(i, 4)) for i in y])
