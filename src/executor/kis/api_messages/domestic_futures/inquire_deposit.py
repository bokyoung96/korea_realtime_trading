from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import httpx

import sys
import os


inquire_deposit_metadata = {
    'method': 'GET', 
    'url': '/uapi/domestic-futureoption/v1/trading/inquire-deposit', 
    'domain': 'https://openapi.koreainvestment.com:9443', 
    'domain_paper': 'https://openapivts.koreainvestment.com:29443', 
    'tr_id': 'CTRP6550R', 
    'tr_id_paper': None     # 모의투자 미지원 (null 처리할지 키-값 쌍 없앨지 고민)
}


# 선물옵션 총자산현황[v1_국내선물-014]
@dataclass
class InquireDepositParams:    # python 3.11 이상에선 typing.Required 타입힌팅 적용!

    """
    선물옵션 총자산현황[v1_국내선물-014]

    Args:
        CANO (str): 종합계좌번호
        ACNT_PRDT_CD (str): 계좌상품코드

    Example:
        InquireBalanceParams(CANO='12345678', ACNT_PRDT_CD='01', MGNA_DVSN='01', EXCC_STAT_CD='1', CTX_AREA_FK200='', CTX_AREA_NK200='')
    """

    CANO: str  # 종합계좌번호
    ACNT_PRDT_CD: str  # 계좌상품코드

    MGNA_DVSN: str    # 증거금 구분
    EXCC_STAT_CD: str    # 정산상태코드
    CTX_AREA_FK200: str    # 연속조회검색조건200
    CTX_AREA_NK200: str    # 연속조회키200
