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


inquire_psble_order_metadata = {
    'method': 'GET', 
    'url': '/uapi/domestic-futureoption/v1/trading/inquire-psbl-order', 
    'domain': 'https://openapi.koreainvestment.com:9443', 
    'domain_paper': 'https://openapivts.koreainvestment.com:29443', 
    'tr_id': 'TTTO5105R', 
    'tr_id_paper': 'VTTO5105R'
}


# 선물옵션 주문가능[v1_국내선물-005]
@dataclass
class InquirePossibleOrderParams:    # python 3.11 이상에선 typing.Required 타입힌팅 적용!

    """
    선물옵션 주문가능[v1_국내선물-005]

    Args:
        CANO (str):종합계좌번호
        ACNT_PRDT_CD (str):계좌상품코드

        PDNO (str): 상품번호 \\
                    선물옵션종목코드 \\
                    선물 6자리 (예: 101S03) \\
                    옵션 9자리 (예: 201S03370)
        SLL_BUY_DVSN_CD (str):  매도매수구분코드 \\
                                01 : 매도 \\
                                02 : 매수 \\
        UNIT_PRICE (str):   주문가격1 \\
                            주문가격 '0'일 경우, \\
                            옵션매수 : 현재가 \\
                            그 이외 : 기준가
        ORD_DVSN_CD (str):  주문구분코드 \\
                            01 : 지정가 \\
                            02 : 시장가 \\
                            03 : 조건부 \\
                            04 : 최유리 \\
                            10 : 지정가(IOC) \\
                            11 : 지정가(FOK) \\
                            12 : 시장가(IOC) \\
                            13 : 시장가(FOK) \\
                            14 : 최유리(IOC) \\
                            15 : 최유리(FOK)
    
    Example:
        InquirePossibleOrderParams(CANO='12345678', ACNT_PRDT_CD='01', MGNA_DVSN='01', EXCC_STAT_CD='1', CTX_AREA_FK200='', CTX_AREA_NK200='')
    """

    CANO: str  # 종합계좌번호
    ACNT_PRDT_CD: str  # 계좌상품코드

    PDNO: str    # 상품번호
    SLL_BUY_DVSN_CD: str    # 매도매수구분코드
    UNIT_PRICE: str    # 주문가격1
    ORD_DVSN_CD: str    # 주문구분코드


