from __future__ import annotations
import logging
from typing import Any, Dict, Optional

import httpx

# TEMP: 패키지 배포시 파이썬 경로추가 코드 제거 후 이하 모듈 임포트에 상대경로 적용
import os
import sys
EXECUTOR_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(EXECUTOR_ROOT)

from kis.api_auth.base import KISAuth, KISConfig, setup_exec_logging
from kis.api_messages.common.request_metadata import RequestMetadata
from kis.api_messages.common.request_header import RequestHeader
from kis.api_messages.common.response import Response
from kis.api_messages.domestic_futures.inquire_balance import InquireBalanceParams, inquire_balance_metadata
from kis.api_messages.domestic_futures.inquire_psbl_order import InquirePossibleOrderParams, inquire_psble_order_metadata
from kis.api_messages.domestic_futures.submit_order import SubmitOrderParams, submit_order_metadata
from kis.api_messages.domestic_futures.inquire_ccnl import InquireOrderStateParams, inquire_order_state_metadata
from services.time_service import TimeService
from exec_protocols import BasicTradingAgent


# httpx 요청 기본함수
def _request(method: str, 
             url: str, 
             header: Dict=None, 
             params: Dict=None, 
             data: Dict=None, 
             json: Dict=None, 
             client: httpx.Client=None):
    
    if method == 'GET':
        request = httpx.Request(method=method, 
                                url=url, 
                                headers=header, 
                                params=params)
    elif method == 'POST':
        request = httpx.Request(method=method, 
                                url=url, 
                                headers=header, 
                                params=params, 
                                data=data, 
                                json=json)      # json: Dict 를 json.dumps() 변환 자동으로 해주는 httpx 인자?

    try:
        if client is None:
            with httpx.Client() as client: 
                response = client.send(request=request)
        elif isinstance(client, httpx.Client):
            response = client.send(request=request)
        else:
            raise TypeError(f"must be httpx.Client for the `client` parameter, not {type(client)}")

    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logging.warning(f"⚠️ Failed to request at {url}: {e}")
        return None

    return response


# httpx 요청 기본함수
async def _async_request(method: str, 
                         url: str, 
                         header: Dict=None, 
                         params: Dict=None, 
                         data: Dict=None, 
                         json: Dict=None, 
                         client: httpx.AsyncClient=None):
    
    if method == 'GET':
        request = httpx.Request(method=method, 
                                url=url, 
                                headers=header, 
                                params=params)
    elif method == 'POST':
        request = httpx.Request(method=method, 
                                url=url, 
                                headers=header, 
                                params=params, 
                                data=data, 
                                json=json)      # json: Dict 를 json.dumps() 변환 자동으로 해주는 httpx 인자?

    try:
        if client is None:
            async with httpx.AsyncClient() as client: 
                response = await client.send(request=request)
        elif isinstance(client, httpx.AsyncClient):
            reponse = await client.sent(request=request)
        else:
            raise TypeError(f"must be httpx.AsyncClient for the `client` parameter, not {type(client)}")

    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logging.warning(f"⚠️ Failed to request at {url}: {e}")
        return None

    return response


### TradingAgent 를 다른 자산 및 거래소의 API 에도 범용적으로 활요하기 위한 기본기능 객체 위주로 작성해보자!
### (기본 매매집행 함수 작성 후, TWAP / VWAP / 등 ... 의 매매 방식들 래핑할 수 있는 함수 추가!)

# 아래 시그널 입력 포맷을 받고, 안정적 매매절차 진행하는 인터페이스만 통일시키면 됨. 
# 각 자산 및 거래소별 REST API 요청 파라미터는 다르지만, 
# (1) HTTP 요청 기본포맷(url, header, params, body)은 동일! 
# (2) 자산별 매매 원칙(티커, 포지션, 수량, 가격(시장가/지정가/..), 등)은 동일! 

#### 시그널 확인 
# -> 매매가능 확인 (= 계좌조회 -> 현재가조회 -> 매매가능계산) 
# -> 매매집행 
# -> 체결상태확인 (+ 필요에 따라 수정주문 or 주문취소 반복수행) 
# -> 계좌조회 (+ 매매결과 출력) 

### 인터페이스 
# 시그널 포맷: 
# {
#     price: 가격, 
#     position: 포지션, 
#     submit_method: 주문=None
# } 

# method: 

# 일괄매매(None), 시간가중가격(TWAP), 거래량가중가격(VWAP) 등 분할매매 방법
# 매매집행 함수는 일괄매매(None) 기준으로 작성 -> 일괄매매 함수 기본으로 TWAP, VWAP 등 wrapping 등으로 적용하는 함수 따로 작성!

    # 참고. 주문전략(방법): (https://securities.miraeasset.com/bbs/board/message/view.do?categoryId=1490&messageId=2277951&vf_headerTitle=%B0%F8%C1%F6%BB%E7%C7%D7)
    # 장중(daily?) 평균가격에 매매를 집행하기 위해 주문수량을 장중에 나누어 (주문)체결시키는 매매 방법
        # VWAP(Volume Weighted Averaged Price, 수량분할) 주문: 
        # 과거 거래량을 분석하여 브로커 자체 기준으로 거래량이 많을 때 많이, 적을 때 적게 배분하여 분할 주문(체결)
        # TWAP(Time Weighted Averaged Price, 시간분할) 주문:
        # 과거 거래시간을 분석하여 브로커 자체 기준으로 장중 분할 주문(체결)


# BasicTradingAgent Protocol 작성으로 범용성 확보 
# 후에 KisTradingAgent Class 작성! 
class KisTradingAgent(BasicTradingAgent):
    def __init__(self, 
                 config: KISConfig, 
                 auth: KISAuth):
        self._config = config   # TODO: 나중에 KISAuth 만 남기고 self._config 제거
        self._auth = auth
        # base.py 에서 logging, config, auth 불러오기
        # logging 주소는 config.json 경로내 .log 폴더 이하로 자동설정 (setup_logging_daily() 함수 사용)
        # Execution 용 config 따로 설정: execution 경로에 config.json 파일 생성!
        # Config 객체생성 (후 불필요) -> Auth 객체생성 (후 생애관리) (후에 auth._config 로 Config 내 정보 활용!)

        # self.price: Optional[float] = price
        # self.position: Optional[int] = position
        # self.submit_method: Optional[str] = submit_method   # None: 일괄매매, TWAP, VWAP 등
        # trading_agent = KisTradingAgent(...) 객체 생성 후 dolpha1.py 실행 중간에 
        # 매매집행 이루어지지만, signal_result(Dict)에서 필요한 값만 뽑아서 전달하자!

    # def auth(self):
    #     # 사용자인증 (OAuth2)
    #     with httpx.Client() as client:
    #         auth = self._auth(self._config, client)


    # 계좌잔고 조회 (선물옵션 잔고현황[v1_국내선물-004])
    def check_balance(self, 
                      margin_type: str='initial'):
        
        if margin_type.lower() == 'initial': 
            marginal_division = '01'
        elif margin_type.lower() == 'maintenance': 
            marginal_division = '02'
        else:
            raise ValueError(f"margin_type은 'initial' 또는 'maintenance'여야 합니다. 현재 값: {margin_type}")

        # [ApiMetadata] 
        balance_metadata = RequestMetadata(**inquire_balance_metadata)

        # tr_id 실전/모의 다르게 설정!
        if self._auth._config.base_url == 'https://openapi.koreainvestment.com:9443': 
            balance_tr_id = balance_metadata.tr_id
        elif self._auth._config.base_url == 'https://openapivts.koreainvestment.com:29443': 
            balance_tr_id = balance_metadata.tr_id_paper
        else:
            raise ValueError(f"base_url은 'https://openapi.koreainvestment.com:9443' 또는 'https://openapivts.koreainvestment.com:29443'여야 합니다. 현재 값: {self._auth._config.base_url}")

        # [ApiRequestHeader] 
        balance_header = RequestHeader(
            authorization=f'Bearer {self._auth._access_token}', 
            appkey=self._auth._config.app_key, 
            appsecret=self._auth._config.app_secret, 
            tr_id=balance_tr_id
        )

        # [ApiRequestParams] 
        balance_params = InquireBalanceParams(
            CANO=self._auth._config.account_number.split(sep='-')[0], 
            ACNT_PRDT_CD=self._auth._config.account_number.split(sep='-')[1], 
            MGNA_DVSN=marginal_division, 
            EXCC_STAT_CD='1',   # TODO: 나중에 정산/본정산 차이 확인 후 메서드 파라미터 수정
            CTX_AREA_FK200='', 
            CTX_AREA_NK200=''
        )

        # domain 실전/모의 다르게 설정!
        if self._auth._config.base_url == 'https://openapi.koreainvestment.com:9443': 
            balance_domain = balance_metadata.domain
        elif self._auth._config.base_url == 'https://openapivts.koreainvestment.com:29443': 
            balance_domain = balance_metadata.domain_paper
        else: 
            raise ValueError(f"base_url은 'https://openapi.koreainvestment.com:9443' 또는 'https://openapivts.koreainvestment.com:29443'여야 합니다. 현재 값: {self._auth._config.base_url}")
        
        # TODO: HTTP 요청결과 에러처리 필요!
        response = _request(
            method=balance_metadata.method, 
            url=balance_domain + balance_metadata.url, 
            header=balance_header.__dict__, 
            params=balance_params.__dict__
        )

        return Response(response=response)  # response.json() 대신 Response 객체 반환


    # 매매가능 확인 (선물옵션 주문가능[v1_국내선물-005])
    def check_possible_order(self, 
                             ticker: str, 
                             position: int, 
                             order_method: str='market', 
                             price: float=None):
        
        if position == 1:       # for 'long'
            sell_buy_division_code = '02'
        elif position == -1:    # for 'short'
            sell_buy_division_code = '01'
        else:
            raise ValueError(f"position 값은 1(매수) 또는 -1(매도)이어야 합니다. 현재 값: {position}")

        if order_method == 'market':
            order_division_code = '02'
        elif order_method == 'limit': 
            if price is None:
                raise ValueError("For limit order, price must be specified.")
            order_division_code = '01'
        else:
            raise ValueError(f"order_method는 'market' 또는 'limit'여야 합니다. 현재 값: {order_method}")

        # [ApiMetadata] 
        psbl_order_metadata = RequestMetadata(**inquire_psble_order_metadata)

        # tr_id 실전/모의 다르게 설정!
        if self._auth._config.base_url == 'https://openapi.koreainvestment.com:9443': 
            psbl_order_tr_id = psbl_order_metadata.tr_id
        elif self._auth._config.base_url == 'https://openapivts.koreainvestment.com:29443': 
            psbl_order_tr_id = psbl_order_metadata.tr_id_paper
        else:
            raise ValueError(f"base_url은 'https://openapi.koreainvestment.com:9443' 또는 'https://openapivts.koreainvestment.com:29443'여야 합니다. 현재 값: {self._auth._config.base_url}")

        # [ApiRequestHeader] 
        psbl_order_header = RequestHeader(
            authorization=f'Bearer {self._auth._access_token}', 
            appkey=self._auth._config.app_key, 
            appsecret=self._auth._config.app_secret, 
            tr_id=psbl_order_tr_id
        )

        # [ApiRequestParams]
        price = price if isinstance(price, str) else str(price)
        psbl_order_params = InquirePossibleOrderParams(
            CANO=self._auth._config.account_number.split(sep='-')[0], 
            ACNT_PRDT_CD=self._auth._config.account_number.split(sep='-')[1], 
            PDNO=ticker, 
            SLL_BUY_DVSN_CD=sell_buy_division_code, 
            UNIT_PRICE=price, 
            ORD_DVSN_CD=order_division_code
        )

        # domain 실전/모의 다르게 설정!
        if self._auth._config.base_url == 'https://openapi.koreainvestment.com:9443': 
            psbl_order_domain = psbl_order_metadata.domain
        elif self._auth._config.base_url == 'https://openapivts.koreainvestment.com:29443': 
            psbl_order_domain = psbl_order_metadata.domain_paper
        else:
            raise ValueError(f"base_url은 'https://openapi.koreainvestment.com:9443' 또는 'https://openapivts.koreainvestment.com:29443'여야 합니다. 현재 값: {self._auth._config.base_url}")
        
        # TODO: HTTP 요청결과 에러처리 필요!
        response = _request(
            method=psbl_order_metadata.method, 
            url=psbl_order_domain + psbl_order_metadata.url, 
            header=psbl_order_header.__dict__, 
            params=psbl_order_params.__dict__
        )

        return Response(response=response)  # response.json() 대신 Response 객체 반환
    

    # 매매집행 (선물옵션 주문[v1_국내선물-001])
    def submit_order(self, 
                     ticker: str, 
                     position: int, 
                     volume: int, 
                     price: float=None, 
                     order_method: str='market'): 

        if position == 1:       # for 'long'
            sell_buy_division_code = '02'
        elif position == -1:    # for 'short'
            sell_buy_division_code = '01'
        else:
            raise ValueError(f"position 값은 1(매수) 또는 -1(매도)이어야 합니다. 현재 값: {position}")

        if order_method == 'market':
            order_division_code = '02'
        elif order_method == 'limit': 
            if price is None:
                raise ValueError("For limit order, price must be specified.")
            order_division_code = '01'
        else:
            raise ValueError(f"order_method는 'market' 또는 'limit'여야 합니다. 현재 값: {order_method}")
        
        # [ApiMetadata] 
        order_metadata = RequestMetadata(**submit_order_metadata)

        # tr_id 실전/모의 다르게 설정!
        if self._auth._config.base_url == 'https://openapi.koreainvestment.com:9443': 
            order_tr_id = order_metadata.tr_id
        elif self._auth._config.base_url == 'https://openapivts.koreainvestment.com:29443': 
            order_tr_id = order_metadata.tr_id_paper
        else: 
            raise ValueError(f"base_url은 'https://openapi.koreainvestment.com:9443' 또는 'https://openapivts.koreainvestment.com:29443'여야 합니다. 현재 값: {self._auth._config.base_url}")

        # [ApiRequestHeader] 
        order_header = RequestHeader(
            authorization=f'Bearer {self._auth._access_token}', 
            appkey=self._auth._config.app_key, 
            appsecret=self._auth._config.app_secret, 
            tr_id=order_tr_id
        )
        
        # [ApiRequestParams] 
        # TODO: 파라미터 고민!
        # volume = volume if isinstance(volume, str) else str(volume)
        # price = price if isinstance(price, str) else str(price)
        order_data = SubmitOrderParams(
            CANO=self._auth._config.account_number.split(sep='-')[0], 
            ACNT_PRDT_CD=self._auth._config.account_number.split(sep='-')[1], 
            ORD_PRCS_DVSN_CD='02',  # 주문처리구분코드: 02: 주문전송
            SLL_BUY_DVSN_CD=sell_buy_division_code,    # 안전빵으로 '매도' 코드 우선 전송! 
            SHTN_PDNO=ticker, 
            ORD_QTY=str(volume),
            UNIT_PRICE=str(price) if order_method == 'limit' else '0',   # TODO: 주문 에러시, order_division_code 가 시장가('02') or 최유리('04')인 경우 "0" 처리!
            ORD_DVSN_CD=order_division_code, 
            NMPR_TYPE_CD='',        # 임시: 에러 디버깅용 (Exec. step 2-1. 주문 제출 에러: 주문처리구분코드를 확인해주세요. (IGW00026))
            KRX_NMPR_CNDT_CD='',    # 임시: 에러 디버깅용 (Exec. step 2-1. 주문 제출 에러: 주문처리구분코드를 확인해주세요. (IGW00026))
            CTAC_TLNO='',           # 임시: 에러 디버깅용 (Exec. step 2-1. 주문 제출 에러: 주문처리구분코드를 확인해주세요. (IGW00026))
            FUOP_ITEM_DVSN_CD=''    # 임시: 에러 디버깅용 (Exec. step 2-1. 주문 제출 에러: 주문처리구분코드를 확인해주세요. (IGW00026))
        )

        # domain 실전/모의 다르게 설정!
        if self._auth._config.base_url == 'https://openapi.koreainvestment.com:9443': 
            order_domain = order_metadata.domain
        elif self._auth._config.base_url == 'https://openapivts.koreainvestment.com:29443': 
            order_domain = order_metadata.domain_paper
        else:
            raise ValueError(f"base_url은 'https://openapi.koreainvestment.com:9443' 또는 'https://openapivts.koreainvestment.com:29443'여야 합니다. 현재 값: {self._auth._config.base_url}")

        # TODO: HTTP 요청결과 에러처리 필요!
        response = _request(method=order_metadata.method, 
                            url=order_domain + order_metadata.url, 
                            header=order_header.__dict__, 
                            json=order_data.__dict__)   # (HJ) TODO: post 요청은 params 대신 body 또는 json 으로 보내야 하는지 확인!
                            # data=json.dumps(asdict(sell_order_params)) 와 동일
        return Response(response=response)  # response.json() 대신 Response 객체 반환
    

    # 체결상태 확인 (선물옵션 주문체결내역조회[v1_국내선물-003])
    def check_order_state(self, 
                          ticker: str, 
                          position: int, 
                          start_date: str='', 
                          end_date: str='', 
                          ascending: bool=True):

        if position == 0:   # for 'all' position
            sell_buy_division_code = '00'
        elif position == 1:     # for 'long'
            sell_buy_division_code = '02'
        elif position == -1:    # for 'short'
            sell_buy_division_code = '01'
        else:
            raise ValueError(f"position 값은 0(전체), 1(매수) 또는 -1(매도)이어야 합니다. 현재 값: {position}")
        
        if end_date == '':
            now_kst = TimeService.now_kst_naive()
            end_date = now_kst.date().strftime("%Y%m%d")
            if start_date == '':
                start_date = end_date
        else:
            if start_date == '':
                start_date = end_date
        
        if ascending == True:
            sort_sqn = 'AS'
        elif ascending == False:
            sort_sqn = 'DS'
        else:
            raise ValueError(f"ascending 값은 True 또는 False이어야 합니다. 현재 값: {ascending}")

        # [ApiMetadata] 
        order_state_metadata = RequestMetadata(**inquire_order_state_metadata)

        # tr_id 실전/모의 다르게 설정!
        if self._auth._config.base_url == 'https://openapi.koreainvestment.com:9443': 
            order_state_tr_id = order_state_metadata.tr_id
        elif self._auth._config.base_url == 'https://openapivts.koreainvestment.com:29443': 
            order_state_tr_id = order_state_metadata.tr_id_paper
        else:
            raise ValueError(f"base_url은 'https://openapi.koreainvestment.com:9443' 또는 'https://openapivts.koreainvestment.com:29443'여야 합니다. 현재 값: {self._auth._config.base_url}")

        # [ApiRequestHeader] 
        order_state_header = RequestHeader(
            authorization=f'Bearer {self._auth._access_token}',    # 임시: access_tocken 값
            appkey=self._auth._config.app_key, 
            appsecret=self._auth._config.app_secret, 
            tr_id=order_state_tr_id
        )  # 실전/모의 다르게 설정!

        # [ApiRequestParams] 
        order_state_params = InquireOrderStateParams(
            CANO=self._auth._config.account_number.split(sep='-')[0], 
            ACNT_PRDT_CD=self._auth._config.account_number.split(sep='-')[1], 
            STRT_ORD_DT=start_date, 
            END_ORD_DT=end_date, 
            SLL_BUY_DVSN_CD=sell_buy_division_code, 
            CCLD_NCCS_DVSN='00',    # TODO: 체결 내역만: '01'/미체결 내역만: '02' 반영 필요한지 및 방법 고민
            SORT_SQN=sort_sqn, 
            STRT_ODNO='', 
            PDNO=ticker, # 선물티커 KRX 정보시스템에서 가져와도 되는지 확인 
            MKET_ID_CD='', 
            CTX_AREA_FK200='', 
            CTX_AREA_NK200=''
        )

        # domain 실전/모의 다르게 설정!
        if self._auth._config.base_url == 'https://openapi.koreainvestment.com:9443': 
            order_state_domain = order_state_metadata.domain
        elif self._auth._config.base_url == 'https://openapivts.koreainvestment.com:29443': 
            order_state_domain = order_state_metadata.domain_paper
        else:
            raise ValueError(f"base_url은 'https://openapi.koreainvestment.com:9443' 또는 'https://openapivts.koreainvestment.com:29443'여야 합니다. 현재 값: {self._auth._config.base_url}")
    
        # TODO: HTTP 요청결과 에러처리 필요!
        response = _request(method=order_state_metadata.method, 
                            url=order_state_domain + order_state_metadata.url, 
                            header=order_state_header.__dict__, 
                            params=order_state_params.__dict__)
        
        return Response(response=response)  # response.json() 대신 Response 객체 반환

    # 일별수익률(매매결과)
    # TODO: 매매손익 관련 API 종류 너무 많음 -> 각 API 별 차이 확인 필요!
    def daily_return(self):
        ...
