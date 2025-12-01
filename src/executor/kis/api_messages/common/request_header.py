from dataclasses import dataclass
from typing import Any, Dict, Optional

# KIS API header 담는 모델 (거의 모든 API에서 tr_id 제외하면 값이 동일?) 
@dataclass
class RequestHeader:
    authorization: str  # 접근토큰
    appkey: str # 앱키
    appsecret: str  # 앱시크릿키
    tr_id: str  # 거래ID
    tr_cont: Optional[str] = ''   # 연속 거래 여부
    custtype: Optional[str] = ''  # 고객타입
    personalseckey: Optional[str] = ''    # 고객식별키
    seq_no: Optional[str] = ''    # 일련번호
    mac_address: Optional[str] = ''   # 맥주소
    phone_number: Optional[str] = ''  # 핸드폰번호
    ip_addr: Optional[str] = ''   # 접속 단말 공인 IP
    gt_uid: Optional[str] = ''    # Global UID
    content_type: Optional[str] = '' # 컨텐츠타입   # application/json; charset=utf-8

    ### 원래 dataclass to dict 는 파이썬 기본함수 asdict( dataclass ) 로 변환되는데, 
    ### KIS API 의 헤더 중, content-type 이름에 hyphen 이 포함되서 파이썬 변수명으로 못 씀.
    ### 'content-type' 하나 때문에 to_dict() 메서드 정의하기 너무 길어지는데, 대안 고민!!!
    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorization": self.authorization, 
            "appkey": self.appkey, 
            "appsecret": self.appsecret, 
            "tr_id": self.tr_id, 
            "tr_cont": self.tr_cont, 
            "custtype": self.custtype, 
            "personalseckey": self.personalseckey, 
            "seq_no": self.seq_no, 
            "mac_address": self.mac_address, 
            "phone_number": self.phone_number, 
            "ip_addr": self.ip_addr, 
            "gt_uid": self.gt_uid, 
            "content-type": self.content_type
        }