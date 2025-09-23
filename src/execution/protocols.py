from typing import Protocol


# BasicTradingAgent Protocol
class BasicTradingAgent(Protocol):

    # 매매가능 확인 (= 계좌조회 -> 현재가조회 - 매매가능계산)
    # 선행필요1: 메서드 내부에서 사용할 kis_request_<API_NAME>() 함수들 정의
    # 선행필요2: kis_request_<API_NAME>() 작성에 필요한 REQ, RES dataclasses 작성 필요!
    def check_possible_order():
        ...
    
    # 매매집행
    def order():
        ...
    
    # 체결상태 확인
    def check_order_state():
        ...
    
    # 계좌조회 
    def check_account(): 
        ...