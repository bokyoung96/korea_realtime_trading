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


submit_order_metadata = {
    'method': 'POST', 
    'url': '/uapi/domestic-futureoption/v1/trading/order', 
    'domain': 'https://openapi.koreainvestment.com:9443', 
    'domain_paper': 'https://openapivts.koreainvestment.com:29443', 
    'tr_id': 'TTTO1101U', 
    'tr_id_paper': 'VTTO1101U', 
    'format': 'JSON', 
    'content_type': 'application/json; charset=utf-8'
}


# 선물옵션 주문[v1_국내선물-001]
@dataclass
class SubmitOrderParams:    # python 3.11 이상에선 typing.Required 타입힌팅 적용!

    """
    선물옵션 주문[v1_국내선물-001]

    Args:
        CANO (str): 종합계좌번호
        ACNT_PRDT_CD (str): 계좌상품코드

        ORD_PRCS_DVSN_CD (str): 주문처리구분코드 \\
                                02 : 주문전송
        SLL_BUY_DVSN_CD (str):  매도매수구분코드 \\
                                01 : 매도 \\
                                02 : 매수
        SHTN_PDNO (str):단축상품번호
                        선물 종목번호 6자리 (예: 101S03) \\
                        옵션 종목번호 9자리 (예: 201S03370)
        ORD_QTY (str):  주문수량
        UNIT_PRICE (str):   주문가격1 \\
                            시장가나 최유리 지정가인 경우 0으로 입력
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
        NMPR_TYPE_CD (Optional[str]) = None:    호가유형코드 \\
                                                ORD_DVSN_CD(주문구분코드)를 입력한 경우, ""(공란)으로 입력해도 됨 \\
                                                01 : 지정가 \\
                                                02 : 시장가 \\
                                                03 : 조건부 \\
                                                04 : 최유리
        KRX_NMPR_CNDT_CD (Optional[str]) = None:    한국거래소호가조건코드 \\
                                                    ORD_DVSN_CD(주문구분코드)를 입력한 경우 ""(공란)으로 입력해도 됨 \\
                                                    0 : 없음 \\
                                                    3 : IOC \\
                                                    4 : FOK
        CTAC_TLNO (Optional[str]) = None:  연락전화번호
        FUOP_ITEM_DVSN_CD (Optional[str]) = None:   선물옵션종목구분코드 \\
                                                    공란(Default)
    
    Example:
        OrderParams(CANO='12345678', ACNT_PRDT_CD='01', MGNA_DVSN='01', EXCC_STAT_CD='1', CTX_AREA_FK200='', CTX_AREA_NK200='')
    """

    CANO: str  # 종합계좌번호
    ACNT_PRDT_CD: str  # 계좌상품코드

    ORD_PRCS_DVSN_CD: str    # 주문처리구분코드
    SLL_BUY_DVSN_CD: str    # 매도매수구분코드
    SHTN_PDNO: str    # 단축상품번호
    ORD_QTY: str    # 주문수량
    UNIT_PRICE: str    # 주문가격1
    ORD_DVSN_CD: str    # 주문구분코드
    NMPR_TYPE_CD: Optional[str] = ''    # 호가유형코드
    KRX_NMPR_CNDT_CD: Optional[str] = ''    # 한국거래소호가조건코드
    CTAC_TLNO: Optional[str] = ''    # 연락전화번호
    FUOP_ITEM_DVSN_CD: Optional[str] = ''    # 선물옵션종목구분코드
