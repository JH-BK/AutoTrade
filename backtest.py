import numpy as np
import matplotlib.pyplot as plt
import datetime

from data.data_tool import (
    check_creon_connection,
    get_stockweek_object,
    request_and_append_data,
)
from stats.moving_average import simple_moving_average
from visualize.chart import draw_stock_chart

STOCK_CODE = 'A123310'
INITIAL_SEED = 1000000
STOCK_FEE_RATIO = 0.00015
STOCK_SELL_FEE_RATIO = 0.0023
USE_STOP_LOSS = False
VOLATILITY_BREAK_K = 0.5

if __name__ == "__main__":

    # API 연결 상태 확인
    check_creon_connection()

    # 일자별 object 구하기
    objStockWeek = get_stockweek_object(code=STOCK_CODE)

    data_history_dict = {}

    # 최초 데이터 요청
    ret = request_and_append_data(objStockWeek, data_history_dict)
    if not ret:
        exit()

    # 연속 데이터 요청
    request_count = 0
    while objStockWeek.Continue:  # 연속 조회처리
        request_count += 1
        if request_count > 5:
            break
        ret = request_and_append_data(objStockWeek, data_history_dict)
        if not ret:
            exit()

    # 데이터 전처리
    for k, v in data_history_dict.items():
        if k in "date":
            data_history_dict[k] = [
                datetime.datetime.strptime(str(d), "%Y%m%d").date() for d in v
            ]
        else:
            data_history_dict[k] = np.array(v[::-1])

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
            today_high > simple_moving_average(10, today_idx, data_history_dict),
            today_high > simple_moving_average(30, today_idx, data_history_dict)
        ]
        if (all(conditions)):
            buy_qty = np.floor(current_seed / buy_price).astype(int)
            current_seed -= (buy_price * (1.0 + STOCK_FEE_RATIO)) * buy_qty
            # print(
            #     f"Bought {buy_qty}EA with price {buy_price}"
            #     f" at {data_history_dict['date'][today_idx]}"
            # )

            bought_date_idx_list.append(today_idx)
            bought_price_idx_list.append(buy_price)

            # Stop loss
            if USE_STOP_LOSS:
                if today_close < buy_price * 0.995:
                    sell_price = buy_price * 0.995
                    # print(f"Stop loss at {data_history_dict['date'][today_idx]}")
                    is_profit_flag_list.append(False)
                else:
                    sell_price = today_close
                    is_profit_flag_list.append(True)
            else:
                sell_price = today_close
                if_profit = buy_price > sell_price
                is_profit_flag_list.append(if_profit)

            current_seed += (sell_price * (1.0 - STOCK_FEE_RATIO - STOCK_SELL_FEE_RATIO)) * buy_qty

        total_seed_list.append(current_seed)

    print(f"Remaining seed: {current_seed}")
    col = np.where(is_profit_flag_list, 'r', 'b')

    plt_chart.scatter(
        [data_history_dict["date"][idx] for idx in bought_date_idx_list],
        np.ones_like(bought_date_idx_list) * np.min(bought_price_idx_list) * 0.8,
        marker="|", c=col, s=75,
    )

    plt_seed.plot(data_history_dict["date"], np.array(total_seed_list) / INITIAL_SEED)

    fig.tight_layout()
    plt_chart.grid()
    plt_chart.set_title("Stock chart")
    plt_chart.set_xlabel("Date")
    plt_chart.set_ylabel("Price (Won)")

    plt_seed.grid()
    plt_seed.set_title("Seed balance")
    plt_seed.set_xlabel("Date")
    plt_seed.set_ylabel("Price (%)")

    plt.show()
