from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import httpx


@dataclass
class Response:
    """
    KIS API의 동적 응답 헤더를 처리하기 위한 데이터 클래스입니다.
    __post_init__을 사용하여 딕셔너리에서 동적으로 속성을 설정합니다.
    """
    # httpx 모듈로 요청해 응답받은 Response 객체
    response: httpx.Response
    # dataclass 필드가 아닌 초기화 전용 변수를 선언합니다.
    headers: Optional[Dict] = field(default_factory=dict, init=True, repr=False)
    body: Optional[Dict] = field(default_factory=dict, init=True, repr=False)

    def __post_init__(self):
        for key, value in self.response.headers.items():
            key = key.replace('-', '_')
            self.headers[key] = value
        
        for key, value in self.response.json().items():
            key = key.replace('-', '_')
            self.body[key] = value