from __future__ import annotations
from typing import Protocol
import json


# BasicTradingAgent Protocol
class BasicTradingAgent(Protocol):

    # def auth(self): 
    #     ...
    
    # 계좌잔고 조회 
    def check_balance(self) -> json: 
        ...
    
    # 매매가능 확인 (= 계좌조회 -> 현재가조회 - 매매가능계산)
    def check_possible_order(self) -> json:
        ...
    
    # 매매집행
    def submit_order(self) -> json:
        ...
    
    # 체결상태 확인
    def check_order_state(self) -> json:
        ...
    
    # 일별수익률(매매결과)
    def daily_return(self) -> json:
        ...
