import win32com.client

import datetime
import numpy as np

from typing import Dict, List, Optional

DATA_KEYS = {"date": 0, "open": 1, "high": 2, "low": 3, "close": 4}


def check_creon_connection():
    objCpCybos = win32com.client.Dispatch("CpUtil.CpCybos")
    bConnect = objCpCybos.IsConnect
    if (bConnect == 0):
        raise RuntimeError("PLUS가 정상적으로 연결되지 않음.")


def _get_stockweek_object(code: str):
    objStockWeek = win32com.client.Dispatch("DsCbo1.StockWeek")
    objStockWeek.SetInputValue(0, code)
    return objStockWeek


def _request_and_append_data(obj, input_data_dict: Dict[str, List[int]]) -> int:

    # 데이터 요청
    obj.BlockRequest()

    # 통신 결과 확인
    rqStatus = obj.GetDibStatus()
    rqRet = obj.GetDibMsg1()
    # print("통신상태", rqStatus, rqRet)
    if rqStatus != 0:
        return 0

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
    return count


def _preprocess_data_dict(
    data_history_dict: Dict[str, List[int]],
    n_data_recent: Optional[int] = None,
    reverse_order: bool = True,
):
    slice_step = -1 if reverse_order else 1
    if n_data_recent is None:
        n_data_recent = -1
    else:
        assert n_data_recent > 0

    for k, v in data_history_dict.items():
        if k in "date":
            data_history_dict[k] = [
                datetime.datetime.strptime(str(d), "%Y%m%d").date() for d in v
            ][:n_data_recent][::slice_step]
        else:
            data_history_dict[k] = np.array(v[:n_data_recent][::slice_step])

    return data_history_dict


def request_recent_n_day_data(code, n):

    objStockWeek = _get_stockweek_object(code)
    data_history_dict = {}
    total_data_count = 0

    # 최초 데이터 요청
    new_data_count = _request_and_append_data(objStockWeek, data_history_dict)
    if not new_data_count:
        raise RuntimeError
    total_data_count += new_data_count

    # 연속 데이터 요청
    while objStockWeek.Continue and total_data_count < n:  # 연속 조회처리
        new_data_count = _request_and_append_data(objStockWeek, data_history_dict)
        if not new_data_count:
            raise RuntimeError
        total_data_count += new_data_count

    data_history_dict = _preprocess_data_dict(data_history_dict, n)

    return data_history_dict
