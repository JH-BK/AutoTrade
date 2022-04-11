"""Source code from
https://github.com/INVESTAR/StockAnalysisInPython/blob/master/08_Volatility_Breakout/ch08_01_AutoConnect.py
"""
from pywinauto import application
import time
import os

os.system('taskkill /IM coStarter* /F /T')
os.system('taskkill /IM CpStart* /F /T')
os.system('taskkill /IM DibServer* /F /T')
os.system('wmic process where "name like \'%coStarter%\'" call terminate')
os.system('wmic process where "name like \'%CpStart%\'" call terminate')
os.system('wmic process where "name like \'%DibServer%\'" call terminate')
time.sleep(5)

with open("app_start_code.txt", "r") as file:
    app_start_code = file.readline()

app = application.Application()
app.start(app_start_code)
time.sleep(60)
