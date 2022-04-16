import win32com.client

from typing import Dict, List

DATA_KEYS = {"date": 0, "open": 1, "high": 2, "low": 3, "close": 4}


def check_creon_connection():
    objCpCybos = win32com.client.Dispatch("CpUtil.CpCybos")
    bConnect = objCpCybos.IsConnect
    if (bConnect == 0):
        raise RuntimeError("PLUS가 정상적으로 연결되지 않음.")


def get_stockweek_object(code: str):
    objStockWeek = win32com.client.Dispatch("DsCbo1.StockWeek")
    objStockWeek.SetInputValue(0, code)
    return objStockWeek


def request_and_append_data(obj, input_data_dict: Dict[str, List[int]]) -> bool:

    # 데이터 요청
    obj.BlockRequest()

    # 통신 결과 확인
    rqStatus = obj.GetDibStatus()
    rqRet = obj.GetDibMsg1()
    # print("통신상태", rqStatus, rqRet)
    if rqStatus != 0:
        return False

    # 일자별 정보 데이터 처리
    count = obj.GetHeaderValue(1)  # 데이터 개수

    new_data_dict = {}
    for key in DATA_KEYS.keys():
        new_data_dict[key] = input_data_dict.get(key, [])

    for i in range(count):
        for key, value in DATA_KEYS.items():
            new_data_dict[key].append(
                obj.GetDataValue(value, i)
            )

    input_data_dict.update(new_data_dict)
    return True
