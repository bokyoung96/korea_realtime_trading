from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import httpx

import sys
import os


inquire_order_state_metadata = {
    'method': 'GET', 
    'url': '/uapi/domestic-futureoption/v1/trading/inquire-ccnl', 
    'domain': 'https://openapi.koreainvestment.com:9443', 
    'domain_paper': 'https://openapivts.koreainvestment.com:29443', 
    'tr_id': 'TTTO5201R', 
    'tr_id_paper': 'VTTO5201R', 
    'format': 'JSON', 
    'content_type': 'application/json; charset=utf-8'
}


# 선물옵션 주문체결내역조회[v1_국내선물-003]
@dataclass
class InquireOrderStateParams:    # python 3.11 이상에선 typing.Required 타입힌팅 적용!

    """
    선물옵션 주문체결내역조회[v1_국내선물-003]

    Args:
        CANO (str):종합계좌번호
        ACNT_PRDT_CD (str):계좌상품코드

        STRT_ORD_DT (str):  시작주문일자 \\
                            주문내역 조회 시작 일자, YYYYMMDD
        END_ORD_DT (str):   종료주문일자 \\
                            주문내역 조회 마지막 일자, YYYYMMDD
        SLL_BUY_DVSN_CD (str):  매도매수구분코드 \\
                                00 : 전체 \\
                                01 : 매도 \\
                                02 : 매수
        CCLD_NCCS_DVSN (str):   체결미체결구분 \\
                                00 : 전체 \\
                                01 : 체결 \\
                                02 : 미체결
        SORT_SQN (str): 정렬순서 \\
                        AS : 정순 \\
                        DS : 역순
        STRT_ODNO (str):시작주문번호 \\
                        조회 시작 번호 입력 \\
                        지정하지 않으면 : 가장 최신 주문 체결내역부터 조회
                        특정 주문번호 지정 : 해당 주문부터 이후에 생성된 주문들의 체결내역 조회
        PDNO (str): 상품번호 \\
                    공란 시, 전체 조회 \\
                    선물 6자리 (예: 101S03) \\
                    옵션 9자리 (예: 201S03370)
        MKET_ID_CD (str):   시장ID코드 \\
                            공란(Default)
        CTX_AREA_FK200 (str):   연속조회검색조건200 \\
                                공란 : 최초 조회시 \\
                                이전 Output CTX_AREA_FK200 값 : 다음페이지 조회시
        CTX_AREA_NK200 (str):   연속조회키200 \\
                                공란 : 최초 조회시 \\
                                이전 Output CTX_AREA_NK200 값 : 다음페이지 조회시
    
    Example:
        InquireOrderStateParams(CANO='12345678', ACNT_PRDT_CD='01', MGNA_DVSN='01', EXCC_STAT_CD='1', CTX_AREA_FK200='', CTX_AREA_NK200='')
    """

    CANO: str  # 종합계좌번호
    ACNT_PRDT_CD: str  # 계좌상품코드

    STRT_ORD_DT: str    # 시작주문일자
    END_ORD_DT: str    # 종료주문일자
    SLL_BUY_DVSN_CD: str    # 매도매수구분코드
    CCLD_NCCS_DVSN: str    # 체결미체결구분
    SORT_SQN: str    # 정렬순서
    STRT_ODNO: str    # 시작주문번호
    PDNO: str    # 상품번호
    MKET_ID_CD: str    # 시장ID코드
    CTX_AREA_FK200: str    # 연속조회검색조건200
    CTX_AREA_NK200: str    # 연속조회키200
