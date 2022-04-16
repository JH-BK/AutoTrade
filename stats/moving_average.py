from typing import Dict, List
import numpy as np


def simple_moving_average(k, today_idx: int, data_dict: Dict[str, List[int]], data_key="open"):
    return np.mean(data_dict[data_key][max(0, today_idx - k):today_idx])
