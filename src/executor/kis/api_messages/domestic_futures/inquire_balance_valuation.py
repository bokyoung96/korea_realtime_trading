from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import httpx

import sys
import os


inquire_balance_valuation_metadata = {
    'method': 'GET', 
    'url': '/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl', 
    'domain': 'https://openapi.koreainvestment.com:9443', 
    'domain_paper': 'https://openapivts.koreainvestment.com:29443', 
    'tr_id': 'CTFO6159R', 
    'tr_id_paper': ''     # 모의투자 미지원 (null 처리할지 키-값 쌍 없앨지 고민)
}


# 선물옵션 잔고평가손익내역[v1_국내선물-015]
@dataclass
class InquireBalanceValuationParams:    # python 3.11 이상에선 typing.Required 타입힌팅 적용!

    """
    선물옵션 잔고평가손익내역[v1_국내선물-015]
    일일정산 미완료된 계좌잔고의 평가손익내역 조회 (장중 해당일자만 조회 가능)

    Args:
        CANO (str): 종합계좌번호
        ACNT_PRDT_CD (str): 계좌상품코드

        MGNA_DVSN (str):증거금 구분 \\
                        01 : 개시 \\
                        02 : 유지 
        EXCC_STAT_CD (str): 정산상태코드 \\
                            1 : 정산 (정산가격으로 잔고 조회) \\
                            2 : 본정산 (매입가격으로 잔고 조회)
        CTX_AREA_FK200 (str):   연속조회검색조건200 \\
                                공란 : 최초 조회시 \\
                                이전 Output CTX_AREA_FK200 값 : 다음페이지 조회시
        CTX_AREA_NK200 (str):   연속조회키200 \\
                                공란 : 최초 조회시 \\
                                이전 Output CTX_AREA_NK200 값 : 다음페이지 조회시
    
    Example:
        InquireBalanceParams(CANO='12345678', ACNT_PRDT_CD='01', MGNA_DVSN='01', EXCC_STAT_CD='1', CTX_AREA_FK200='', CTX_AREA_NK200='')
    """

    CANO: str  # 종합계좌번호
    ACNT_PRDT_CD: str  # 계좌상품코드

    MGNA_DVSN: str    # 증거금 구분
    EXCC_STAT_CD: str    # 정산상태코드
    CTX_AREA_FK200: str    # 연속조회검색조건200
    CTX_AREA_NK200: str    # 연속조회키200
