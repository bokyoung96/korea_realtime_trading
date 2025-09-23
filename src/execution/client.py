import os
import sys
import logging
from typing import Any, Dict, Optional

import httpx

# from models.info import ApiInfo
# from models.header import RequestHeader
# from models.params import *

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from base import KISAuth, KISConfig, setup_logging


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

### 고민: ApiInfo, RequestHeader, <ApiName>Param 인스턴스 생성및 관리 방법
### 현재 dataclass 객체로 작성된 것을들 @property Class 로 작성해 getter 와 setter 활용할지 고민!

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
# 시그널 포맷: {quantity: 수량, price: 가격, position: 포지션=None, position_flag: Bool=False, method=None}
# 수량에 + or - 로 position 표현되는 경우 position=None
# method 는 일괄매매(None), 시간가중가격(TWAP), 거래량가중가격(VWAP) 등 분할매매 방법
# 매매집행 함수는 일괄매매(None) 기준으로 작성 -> 일괄매매 함수 기본으로 TWAP, VWAP 등 wrapping 등으로 적용하는 함수 따로 작성!

# BasicTradingAgent Protocol 작성으로 범용성 확보 
# 후에 KisTradingAgent Class 작성! 

# KisTradingAgent Class 작성시, method 의 입력/출력 타입체크에 models dataclass 필요한데, 
# models 경로 내엣 dataclass 모듈 그룹핑 기준을 Info, Header, Params 로 구분할지 ,
# API 종류별로 구분할지 고민 <- API 종류별 구분이 더 사후관리 및 API 변경시 유리!!!
# (1) Request: 
# 모든 API 공통인 Info, GET / POST API 따라 그룹공통인 Header, 각 API 다른 Params (클래스명) 처리 고민!
# (2) Response: 
# (참고. Info 는 없음!) GET / POST API 따라 그룹공통인 Header, 각 API 다른 Params (클래스명) 처리 고민!


class TradingAgent:
    def __init__(self, config: KISConfig, auth: KISAuth):
        self._config = config
        self._auth = auth
