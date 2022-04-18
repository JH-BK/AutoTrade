import numpy as np
import matplotlib.pyplot as plt
import datetime

from data.data_tool import (
    check_creon_connection,
    request_recent_n_day_data
)
from stats.moving_average import simple_moving_average
from visualize.chart import draw_stock_chart

STOCK_CODE = 'A122630'  # KODEX 레버리지
INITIAL_SEED = 1000000
STOCK_FEE_RATIO = 0.00015
STOCK_SELL_FEE_RATIO = 0.0023
USE_STOP_LOSS = True
STOP_LOSS_RATIO = 0.005
VOLATILITY_BREAK_K = 0.3

if __name__ == "__main__":

    # API 연결 상태 확인
    check_creon_connection()

    # 지난 365일 종목 정보 불러오기
    data_history_dict = request_recent_n_day_data(STOCK_CODE, 200)

    fig, (plt_chart, plt_seed) = plt.subplots(2, 1, gridspec_kw={'height_ratios': [3, 1]})
    plt_chart = draw_stock_chart(ax=plt_chart, **data_history_dict)

    bought_date_idx_list = []
    bought_price_idx_list = []
    is_profit_flag_list = []
    current_seed = INITIAL_SEED
    total_seed_list = [current_seed]
    print(f"Initial seed: {INITIAL_SEED}")

    for date_idx in range(len(data_history_dict["date"]) - 1):
        today_idx = date_idx + 1
        yesterday_idx = date_idx

        buy_qty = 0

        yesterday_open = data_history_dict["open"][yesterday_idx]
        yesterday_close = data_history_dict["close"][yesterday_idx]

        today_open = data_history_dict["open"][today_idx]
        today_close = data_history_dict["close"][today_idx]
        today_high = data_history_dict["high"][today_idx]
        today_low = data_history_dict["low"][today_idx]

        target_price = today_open + VOLATILITY_BREAK_K * abs(yesterday_open - yesterday_close)
        buy_price = np.ceil(target_price).astype(int)
        sell_price = today_close

        # Algorithm here.
        conditions = [
            today_high > target_price,
            today_high > simple_moving_average(5, today_idx, data_history_dict),
            today_high > simple_moving_average(15, today_idx, data_history_dict),
        ]
        if (all(conditions)):
            buy_qty = np.floor(current_seed / buy_price).astype(int)
            current_seed -= np.ceil(buy_price * (1.0 + STOCK_FEE_RATIO)) * buy_qty
            # print(
            #     f"Bought {buy_qty}EA with price {buy_price}"
            #     f" at {data_history_dict['date'][today_idx]}"
            # )

            bought_date_idx_list.append(today_idx)
            bought_price_idx_list.append(buy_price)

            # Stop loss
            if USE_STOP_LOSS:
                if today_close < buy_price * (1 - STOP_LOSS_RATIO):
                    sell_price = buy_price * (1 - STOP_LOSS_RATIO)
                    # print(f"Stop loss at {data_history_dict['date'][today_idx]}")
                else:
                    sell_price = today_close
                # if today_high > buy_price * 1.05:
                #     sell_price = buy_price * 1.05
            else:
                sell_price = today_close

            if_profit = buy_price < sell_price
            is_profit_flag_list.append(if_profit)

            current_seed += np.floor(
                sell_price * (1.0 - STOCK_FEE_RATIO - STOCK_SELL_FEE_RATIO)
            ) * buy_qty

        total_seed_list.append(current_seed)

    print(f"Remaining seed: {current_seed}")
    col = np.where(is_profit_flag_list, 'r', 'b')

    plt_chart.scatter(
        [data_history_dict["date"][idx] for idx in bought_date_idx_list],
        np.ones_like(bought_date_idx_list) * np.min(bought_price_idx_list) * 0.8,
        marker="|", c=col, s=75,
    )

    plt_seed.axhline(y=1.0, color='r', linestyle='--', alpha=0.7)
    plt_seed.plot(
        data_history_dict["date"],
        np.array(total_seed_list) / INITIAL_SEED,
        label="Balance"
    )
    plt_seed.plot(
        data_history_dict["date"],
        np.array(data_history_dict["open"]) / data_history_dict["open"][0],
        alpha=0.7,
        label="Stock price"
    )
    plt.legend()

    plt_chart.grid()
    plt_chart.set_title(f"Stock chart ({STOCK_CODE})")
    plt_chart.set_xlabel("Date")
    plt_chart.set_ylabel("Price (Won)")

    plt_seed.grid()
    plt_seed.set_title("Seed balance")
    plt_seed.set_xlabel("Date")
    plt_seed.set_ylabel("Price (%)")

    fig.tight_layout()

    plt.show()
