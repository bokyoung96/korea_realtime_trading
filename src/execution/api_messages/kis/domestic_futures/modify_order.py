from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import httpx

import sys
import os

EXECUTION_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(EXECUTION_ROOT)

from api_messages.kis.common.request_metadata import RequestMetadata
from api_messages.kis.common.request_header import RequestHeader
from api_messages.kis.common.response import Response


modify_order_metadata = {
    'method': 'POST', 
    'url': '/uapi/domestic-futureoption/v1/trading/order-rvsecncl', 
    'domain': 'https://openapi.koreainvestment.com:9443', 
    'domain_paper': 'https://openapivts.koreainvestment.com:29443', 
    'tr_id': 'TTTO1103U', 
    'tr_id_paper': 'VTTO1103U', 
    'format': 'JSON', 
    'content_type': 'application/json; charset=utf-8'
}


# 선물옵션 정정취소주문[v1_국내선물-002]
@dataclass
class ModifyOrderParams:    # python 3.11 이상에선 typing.Required 타입힌팅 적용!

    """
    선물옵션 정정취소주문[v1_국내선물-002]

    Args:
        CANO (str):종합계좌번호
        ACNT_PRDT_CD (str):계좌상품코드

        ORD_PRCS_DVSN_CD (str): 주문처리구분코드 \\
                                02 : 주문전송
        RVSE_CNCL_DVSN_CD (str):정정취소구분코드 \\
                                01 : 정정
                                02 : 취소
        ORGN_ODNO (str):원주문번호 \\
                        정정 혹은 취소할 주문의 번호
        ORD_QTY (str):  주문수량 \\
                        [Header tr_id TTTO1103U(선물옵션 정정취소 주간)] \\
                        전량일경우 0으로 입력 \\
                        [Header tr_id JTCE1002U(선물옵션 정정취소 야간)] \\
                        일부수량 정정 및 취소 불가, 주문수량 반드시 입력 (공백 불가) \\
                        일부 미체결 시 잔량 전체에 대해서 취소 가능 \\
                            EX) 2개 매수주문 후 1개 체결, 1개 미체결인 상태에서  \\
                                취소주문 시 ORD_QTY는 1로 입력 \\
                        모의계좌의 경우, 주문수량 반드시 입력 (공백 불가)
        UNIT_PRICE (str):   주문가격1 \\
                            시장가나 최유리의 경우 0으로 입력 (취소 시에도 0 입력)
        NMPR_TYPE_CD (str): 호가유형코드 \\
                            01 : 지정가 \\
                            02 : 시장가 \\
                            03 : 조건부 \\
                            04 : 최유리
        KRX_NMPR_CNDT_CD (str): 한국거래소호가조건코드 \\
                                취소시 0으로 입력 \\
                                정정시 \\
                                0 : 없음 \\
                                3 : IOC \\
                                4 : FOK
        RMN_QTY_YN (str):   잔여수량여부 \\
                            Y : 전량 \\
                            N : 일부
        ORD_DVSN_CD (str):  주문구분코드 \\
                            [정정] \\
                            01 : 지정가 \\
                            02 : 시장가 \\
                            03 : 조건부 \\
                            04 : 최유리 \\
                            10 : 지정가(IOC) \\
                            11 : 지정가(FOK) \\
                            12 : 시장가(IOC) \\
                            13 : 시장가(FOK) \\
                            14 : 최유리(IOC) \\
                            15 : 최유리(FOK) \\
                            [취소] \\
                            01 로 입력
        FUOP_ITEM_DVSN_CD (Optional[str]) = None:   선물옵션종목구분코드 \\
                                                    [Header tr_id TTTO1103U(선물옵션 정정취소 주간)] \\
                                                    공란(Default) \\
                                                    [Header tr_id JTCE1002U(선물옵션 정정취소 야간)] \\
                                                    01 : 선물 \\
                                                    02 : 콜옵션 \\
                                                    03 : 풋옵션 \\
                                                    04 : 스프레드

    
    Example:
        OrderModifParams(CANO='12345678', ACNT_PRDT_CD='01', MGNA_DVSN='01', EXCC_STAT_CD='1', CTX_AREA_FK200='', CTX_AREA_NK200='')
    """

    CANO: str  # 종합계좌번호
    ACNT_PRDT_CD: str  # 계좌상품코드

    ORD_PRCS_DVSN_CD: str    # 주문처리구분코드
    RVSE_CNCL_DVSN_CD: str    # 정정취소구분코드
    ORGN_ODNO: str    # 원주문번호
    ORD_QTY: str    # 주문수량
    UNIT_PRICE: str    # 주문가격1
    NMPR_TYPE_CD: str    # 호가유형코드
    KRX_NMPR_CNDT_CD: str    # 한국거래소호가조건코드
    RMN_QTY_YN: str    # 잔여수량여부
    ORD_DVSN_CD: str    # 주문구분코드
    FUOP_ITEM_DVSN_CD: Optional[str] = ''    # 선물옵션종목구분코드
