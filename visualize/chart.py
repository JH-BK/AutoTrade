import numpy as np
import matplotlib.pyplot as plt

from typing import Optional


def draw_stock_chart(
        date: np.ndarray,
        open: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    if ax is None:
        _, ax = plt.subplots(figsize=(12, 7))

    price_bar_bot = np.minimum(open, close)
    price_bar_dif = np.abs(open - close)
    is_red = open < close

    ax.errorbar(
        date, low,
        yerr=(high - low),
        fmt='none',
        elinewidth=1,
        ecolor=np.where(is_red, 'r', 'b')
    )
    ax.bar(
        date, price_bar_dif,
        bottom=price_bar_bot,
        width=1,
        color=np.where(is_red, 'r', 'b')
    )

    return ax
