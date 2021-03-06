"""Source code from
https://github.com/INVESTAR/StockAnalysisInPython/blob/master/08_Volatility_Breakout/ch08_03_EtfAlgoTrader.py.
"""
import os
import sys
import ctypes
import win32com.client
import pandas as pd
from datetime import datetime
import pymsteams
import time
import calendar
from bs4 import BeautifulSoup
from urllib.request import urlopen
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


with open("./resources/webhook_url.txt", "r") as file:
    WEBHOOK_URL = file.readline()

TeamsMessageManager = pymsteams.connectorcard(WEBHOOK_URL)


def dbgout(message):
    """인자로 받은 문자열을 파이썬 셸과 팀즈로 동시에 출력한다."""
    print(datetime.now().strftime('[%m/%d %H:%M:%S]'), message)
    strbuf = datetime.now().strftime('[%m/%d %H:%M:%S] ') + message
    TeamsMessageManager.text(strbuf)
    TeamsMessageManager.send()


def printlog(message, *args):
    """인자로 받은 문자열을 파이썬 셸에 출력한다."""
    print(datetime.now().strftime('[%m/%d %H:%M:%S]'), message, *args)


# 크레온 플러스 공통 OBJECT
cpCodeMgr = win32com.client.Dispatch('CpUtil.CpStockCode')
cpStatus = win32com.client.Dispatch('CpUtil.CpCybos')
cpTradeUtil = win32com.client.Dispatch('CpTrade.CpTdUtil')
cpStock = win32com.client.Dispatch('DsCbo1.StockMst')
cpOhlc = win32com.client.Dispatch('CpSysDib.StockChart')
cpBalance = win32com.client.Dispatch('CpTrade.CpTd6033')
cpCash = win32com.client.Dispatch('CpTrade.CpTdNew5331A')
cpOrder = win32com.client.Dispatch('CpTrade.CpTd0311')


def check_creon_system():
    """크레온 플러스 시스템 연결 상태를 점검한다."""
    # 관리자 권한으로 프로세스 실행 여부
    if not ctypes.windll.shell32.IsUserAnAdmin():
        printlog('check_creon_system() : admin user -> FAILED')
        return False

    # 연결 여부 체크
    if (cpStatus.IsConnect == 0):
        printlog('check_creon_system() : connect to server -> FAILED')
        return False

    # 주문 관련 초기화 - 계좌 관련 코드가 있을 때만 사용
    if (cpTradeUtil.TradeInit(0) != 0):
        printlog('check_creon_system() : init trade -> FAILED')
        return False
    return True


def get_current_price(code):
    """인자로 받은 종목의 현재가, 매도호가, 매수호가를 반환한다."""
    cpStock.SetInputValue(0, code)  # 종목코드에 대한 가격 정보
    cpStock.BlockRequest()
    item = {}
    item['cur_price'] = cpStock.GetHeaderValue(11)   # 현재가
    item['ask'] = cpStock.GetHeaderValue(16)        # 매도호가
    item['bid'] = cpStock.GetHeaderValue(17)        # 매수호가
    return item['cur_price'], item['ask'], item['bid']


def get_ohlc(code, qty):
    """인자로 받은 종목의 OHLC 가격 정보를 qty 개수만큼 반환한다."""
    cpOhlc.SetInputValue(0, code)           # 종목코드
    cpOhlc.SetInputValue(1, ord('2'))        # 1:기간, 2:개수
    cpOhlc.SetInputValue(4, qty)             # 요청개수
    cpOhlc.SetInputValue(5, [0, 2, 3, 4, 5])  # 0:날짜, 2~5:OHLC
    cpOhlc.SetInputValue(6, ord('D'))        # D:일단위
    cpOhlc.SetInputValue(9, ord('1'))        # 0:무수정주가, 1:수정주가
    cpOhlc.BlockRequest()
    count = cpOhlc.GetHeaderValue(3)   # 3:수신개수
    columns = ['open', 'high', 'low', 'close']
    index = []
    rows = []
    for i in range(count):
        index.append(cpOhlc.GetDataValue(0, i))
        rows.append([cpOhlc.GetDataValue(1, i), cpOhlc.GetDataValue(2, i),
                     cpOhlc.GetDataValue(3, i), cpOhlc.GetDataValue(4, i)])
    df = pd.DataFrame(rows, columns=columns, index=index)
    return df


def get_stock_balance(code):
    """인자로 받은 종목의 종목명과 수량을 반환한다."""
    cpTradeUtil.TradeInit()
    acc = cpTradeUtil.AccountNumber[0]      # 계좌번호
    accFlag = cpTradeUtil.GoodsList(acc, 1)  # -1:전체, 1:주식, 2:선물/옵션
    cpBalance.SetInputValue(0, acc)         # 계좌번호
    cpBalance.SetInputValue(1, accFlag[0])  # 상품구분 - 주식 상품 중 첫번째
    cpBalance.SetInputValue(2, 50)          # 요청 건수(최대 50)
    cpBalance.BlockRequest()
    if code == 'ALL':
        dbgout(
            f'계좌명: {cpBalance.GetHeaderValue(0)}\n'
            f'결제잔고수량 : {cpBalance.GetHeaderValue(1)}\n'
            f'평가금액: {cpBalance.GetHeaderValue(3)}\n'
            f'평가손익: {cpBalance.GetHeaderValue(4)}\n'
            f'종목수: {cpBalance.GetHeaderValue(7)}\n'
        )
    stocks = []
    for i in range(cpBalance.GetHeaderValue(7)):
        stock_code = cpBalance.GetDataValue(12, i)  # 종목코드
        stock_name = cpBalance.GetDataValue(0, i)   # 종목명
        stock_qty = cpBalance.GetDataValue(15, i)   # 수량
        if code == 'ALL':
            dbgout(
                f"{i + 1} {stock_code}({stock_name}):{stock_qty}"
            )
            stocks.append({'code': stock_code, 'name': stock_name,
                           'qty': stock_qty})
        if stock_code == code:
            return stock_name, stock_qty
    if code == 'ALL':
        return stocks
    else:
        stock_name = cpCodeMgr.CodeToName(code)
        return stock_name, 0


def get_current_cash():
    """증거금 100% 주문 가능 금액을 반환한다."""
    cpTradeUtil.TradeInit()
    acc = cpTradeUtil.AccountNumber[0]    # 계좌번호
    accFlag = cpTradeUtil.GoodsList(acc, 1)  # -1:전체, 1:주식, 2:선물/옵션
    cpCash.SetInputValue(0, acc)              # 계좌번호
    cpCash.SetInputValue(1, accFlag[0])      # 상품구분 - 주식 상품 중 첫번째
    cpCash.BlockRequest()
    return cpCash.GetHeaderValue(9)  # 증거금 100% 주문 가능 금액


def get_adaptive_kvalue(code):  # 인자로 받은 종목에 대한 20일 average noise ratio.
    try:
        ohlck = get_ohlc(code, 20)
        ohlck['noiseratio'] = 1 - (abs(ohlck['open'] - ohlck['close']) / (ohlck['high'] - ohlck['low']))
        return round(ohlck['noiseratio'].mean(), 2)
    except Exception as ex:
        print('get_kvalue() -> 에러: ' + str(ex))
        return None


def get_target_price(code):
    """매수 목표가를 반환한다."""
    try:
        time_now = datetime.now()
        str_today = time_now.strftime('%Y%m%d')
        ohlc = get_ohlc(code, 10)
        if str_today == str(ohlc.iloc[0].name):
            today_open = ohlc.iloc[0].open
            lastday = ohlc.iloc[1]
        else:
            lastday = ohlc.iloc[0]
            today_open = lastday[3]
        lastday_high = lastday[1]
        lastday_low = lastday[2]

        # k_value = get_adaptive_kvalue(code)
        # if k_value is None:
        #     k_value = 0.5
        k_value = 0.3

        target_price = today_open + (lastday_high - lastday_low) * k_value
        return target_price
    except Exception as ex:
        dbgout("`get_target_price() -> exception! " + str(ex) + "`")
        return None


def get_movingaverage(code, window):
    """인자로 받은 종목에 대한 이동평균가격을 반환한다."""
    try:
        time_now = datetime.now()
        str_today = time_now.strftime('%Y%m%d')
        ohlc = get_ohlc(code, 20)
        if str_today == str(ohlc.iloc[0].name):
            lastday = ohlc.iloc[1].name
        else:
            lastday = ohlc.iloc[0].name
        closes = ohlc['close'].sort_index()
        ma = closes.rolling(window=window).mean()
        return ma.loc[lastday]
    except Exception as ex:
        dbgout('get_movingavrg(' + str(window) + ') -> exception! ' + str(ex))
        return None


def check_loss_and_sell_etf(code, loss: float = 0.005):
    """Check loss condition and sell all when the condition is met."""

    try:
        global bought_list
        if code not in bought_list:
            return False

        stock_name, stock_qty = get_stock_balance(code)
        current_price, ask_price, bid_price = get_current_price(code)
        target_price = get_target_price(code)    # 매수 목표가

        if current_price < target_price * (1.0 - loss):
            printlog(
                f"{stock_name}({code}){stock_qty}EA : {current_price} meets the stop loss condition!`"
            )
            sell_etf(code)

            # Additional check
            if code not in bought_list:
                printlog(
                    f"{stock_name}({code}){stock_qty}EA : {current_price}"
                    " sold out due to the loss condition!`"
                )
            else:
                stock_name, remaining_stock_qty = get_stock_balance(code)
                printlog(
                    f"{stock_name}({code}){stock_qty}EA : {current_price}"
                    f" did not sold out clearly. Total {remaining_stock_qty}EA remaining.`"
                )
            return True
        else:
            return False

    except Exception as ex:
        dbgout("`check_etf(" + str(code) + ") -> exception! " + str(ex) + "`")
        return False


def buy_etf(code):
    """인자로 받은 종목을 시장가 FOK 조건으로 매수한다."""
    try:
        global bought_list      # 함수 내에서 값 변경을 하기 위해 global로 지정
        if code in bought_list:  # 매수 완료 종목이면 더 이상 안 사도록 함수 종료
            return False
        time_now = datetime.now()
        current_price, ask_price, bid_price = get_current_price(code)
        target_price = get_target_price(code)    # 매수 목표가
        ma5_price = get_movingaverage(code, 5)   # 5일 이동평균가
        ma10_price = get_movingaverage(code, 15)  # 15일 이동평균가
        buy_qty = 0        # 매수할 수량 초기화
        if ask_price > 0:  # 매도호가가 존재하면
            buy_qty = buy_amount // ask_price
        stock_name, stock_qty = get_stock_balance(code)  # 종목명과 보유수량 조회

        if current_price > target_price and current_price > ma5_price \
                and current_price > ma10_price:
            printlog(
                f"{stock_name}({code}){buy_qty}EA : {current_price} meets the buy condition!`"
            )
            cpTradeUtil.TradeInit()
            acc = cpTradeUtil.AccountNumber[0]      # 계좌번호
            accFlag = cpTradeUtil.GoodsList(acc, 1)  # -1:전체,1:주식,2:선물/옵션
            # 지정가 FOK 매수 주문 설정
            cpOrder.SetInputValue(0, "2")        # 2: 매수
            cpOrder.SetInputValue(1, acc)        # 계좌번호
            cpOrder.SetInputValue(2, accFlag[0])  # 상품구분 - 주식 상품 중 첫번째
            cpOrder.SetInputValue(3, code)       # 종목코드
            cpOrder.SetInputValue(4, buy_qty)    # 매수할 수량
            cpOrder.SetInputValue(5, target_price)  # 주문단가
            cpOrder.SetInputValue(7, "2")        # 주문조건 0:기본, 1:IOC, 2:FOK
            cpOrder.SetInputValue(8, "05")  # 주문호가 01:보통, 03:시장가, 05:지정가, 12:최유리, 13:최우선
            # 매수 주문 요청
            ret = cpOrder.BlockRequest()
            printlog('지정가 FoK 매수 ->', stock_name, code, buy_qty, '->', ret)
            if ret == 4:
                remain_time = cpStatus.LimitRequestRemainTime
                printlog('주의: 연속 주문 제한에 걸림. 대기 시간:', remain_time / 1000)
                time.sleep(remain_time / 1000)
                return False
            time.sleep(2)
            printlog('현금주문 가능금액 :', buy_amount)
            stock_name, bought_qty = get_stock_balance(code)
            printlog('get_stock_balance :', stock_name, stock_qty)
            if bought_qty > 0:
                bought_list.append(code)
                dbgout(
                    f"`buy_etf({stock_name} : {code}"
                    f") -> {bought_qty}EA bought!`"
                )
    except Exception as ex:
        dbgout("`buy_etf(" + str(code) + ") -> exception! " + str(ex) + "`")


def sell_all():
    """보유한 모든 종목을 시장가 IOC 조건으로 매도한다."""
    try:
        cpTradeUtil.TradeInit()
        acc = cpTradeUtil.AccountNumber[0]       # 계좌번호
        accFlag = cpTradeUtil.GoodsList(acc, 1)  # -1:전체, 1:주식, 2:선물/옵션
        while True:
            stocks = get_stock_balance('ALL')
            total_qty = 0
            for s in stocks:
                total_qty += s['qty']
            if total_qty == 0:
                return True
            for s in stocks:
                if s['qty'] != 0:
                    cpOrder.SetInputValue(0, "1")         # 1:매도, 2:매수
                    cpOrder.SetInputValue(1, acc)         # 계좌번호
                    cpOrder.SetInputValue(2, accFlag[0])  # 주식상품 중 첫번째
                    cpOrder.SetInputValue(3, s['code'])   # 종목코드
                    cpOrder.SetInputValue(4, s['qty'])    # 매도수량
                    cpOrder.SetInputValue(7, "1")   # 조건 0:기본, 1:IOC, 2:FOK
                    cpOrder.SetInputValue(8, "3")  # 주문호가 1:보통, 3:시장가, 5:지정가, 12:최유리, 13:최우선
                    # 시장가 IOC 매도 주문 요청
                    ret = cpOrder.BlockRequest()
                    printlog('시장가 IOC 매도', s['code'], s['name'], s['qty'],
                             '-> cpOrder.BlockRequest() -> returned', ret)
                    if ret == 4:
                        remain_time = cpStatus.LimitRequestRemainTime
                        printlog('주의: 연속 주문 제한, 대기시간:', remain_time / 1000)
                time.sleep(1)
            time.sleep(30)
    except Exception as ex:
        dbgout("sell_all() -> exception! " + str(ex))


def sell_etf(code):
    """보유한 종목을 최유리 지정가 IOC 조건으로 매도한다."""
    try:
        global bought_list
        if code not in bought_list:
            return False

        cpTradeUtil.TradeInit()
        acc = cpTradeUtil.AccountNumber[0]       # 계좌번호
        accFlag = cpTradeUtil.GoodsList(acc, 1)  # -1:전체, 1:주식, 2:선물/옵션
        while True:
            stock_name, stock_qty = get_stock_balance(code)
            if stock_qty == 0:
                bought_list.remove(code)
                dbgout(
                    f"`sell_etf({stock_name} : {code}"
                    f") -> All sold out!`"
                )
                return True

            if stock_qty != 0:
                cpOrder.SetInputValue(0, "1")         # 1:매도, 2:매수
                cpOrder.SetInputValue(1, acc)         # 계좌번호
                cpOrder.SetInputValue(2, accFlag[0])  # 주식상품 중 첫번째
                cpOrder.SetInputValue(3, code)   # 종목코드
                cpOrder.SetInputValue(4, stock_qty)    # 매도수량
                cpOrder.SetInputValue(7, "1")   # 조건 0:기본, 1:IOC, 2:FOK
                cpOrder.SetInputValue(8, "12")  # 호가 12:최유리, 13:최우선
                # 최유리 IOC 매도 주문 요청
                ret = cpOrder.BlockRequest()
                printlog('최유리 IOC 매도', code, stock_name, stock_qty,
                         '-> cpOrder.BlockRequest() -> returned', ret)
                if ret == 4:
                    remain_time = cpStatus.LimitRequestRemainTime
                    printlog('주의: 연속 주문 제한, 대기시간:', remain_time / 1000)
            time.sleep(1)
            time.sleep(30)
    except Exception as ex:
        dbgout("sell_etf() -> exception! " + str(ex))


if __name__ == '__main__':
    try:
        symbol_list = []  # 매수 후보 종목 리스트
        bought_list = []  # 매수 완료된 종목 리스트

        with open("./resources/ticker_list.txt", "r") as file:
            while line := file.readline():
                symbol_list.append(str(line).rstrip('\n'))

        target_buy_count = 5  # 매수할 종목 수
        buy_percent = 0.25
        stop_loss = 0.005  # target price에서 stop_loss 이상 손실 시 바로 매도

        printlog('check_creon_system() :', check_creon_system())  # 크레온 접속 점검
        stocks = get_stock_balance('ALL')      # 보유한 모든 종목 조회
        total_cash = int(get_current_cash())   # 100% 증거금 주문 가능 금액 조회
        buy_amount = total_cash * buy_percent  # 종목별 주문 금액 계산
        printlog('100% 증거금 주문 가능 금액 :', total_cash)
        printlog('종목별 주문 비율 :', buy_percent)
        printlog('종목별 주문 금액 :', buy_amount)
        printlog('시작 시간 :', datetime.now().strftime('%m/%d %H:%M:%S'))
        soldout = False

        while True:
            t_now = datetime.now()
            t_9 = t_now.replace(hour=9, minute=0, second=0, microsecond=0)
            t_start = t_now.replace(hour=9, minute=5, second=0, microsecond=0)
            t_sell = t_now.replace(hour=15, minute=15, second=0, microsecond=0)
            t_exit = t_now.replace(hour=15, minute=20, second=0, microsecond=0)
            today = datetime.today().weekday()

            if today == 5 or today == 6:  # 토요일이나 일요일이면 자동 종료
                printlog('Today is', 'Saturday.' if today == 5 else 'Sunday.')
                sys.exit(0)

            if t_9 < t_now < t_start and not soldout:
                soldout = True
                sell_all()

            if t_start < t_now < t_sell:  # AM 09:05 ~ PM 03:15 : 매수
                # 주식 매수
                for sym in symbol_list:
                    if len(bought_list) < target_buy_count:
                        buy_etf(sym)
                        time.sleep(1)

                # Stop loss implementation.
                for sym in symbol_list.copy():
                    is_sold = check_loss_and_sell_etf(sym, stop_loss)
                    # Do not buy again today.
                    if is_sold:
                        symbol_list.remove(sym)

                # 주식 잔고 확인
                if t_now.minute == 30 and 0 <= t_now.second <= 5:
                    get_stock_balance('ALL')
                    time.sleep(5)

            if t_sell < t_now < t_exit:  # PM 03:15 ~ PM 03:20 : 일괄 매도
                if sell_all():
                    dbgout('`sell_all() returned True -> self-destructed!`')
                    sys.exit(0)

            if t_exit < t_now:  # PM 03:20 ~ :프로그램 종료
                dbgout('`self-destructed!`')
                sys.exit(0)

            time.sleep(3)

    except Exception as ex:
        dbgout('`main -> exception! ' + str(ex) + '`')
