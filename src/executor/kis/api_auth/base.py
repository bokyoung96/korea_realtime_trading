import os
import json
import httpx
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
import re

# TEMP: 패키지 배포시 파이썬 경로추가 코드 제거 후 이하 모듈 임포트에 상대경로 적용
import os
import sys
EXECUTOR_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(EXECUTOR_ROOT)

from services.time_service import TimeService


def setup_exec_logging(config_dir: str):
    """
    일별 로그 파일을 생성하고 관리합니다.
    - 로그 파일은 '.log' 디렉터리에 'kis_exe_YYYYMMDD.log' 형식으로 저장됩니다.
    - 로그 파일은 최대 100개까지 유지되며, 가장 오래된 파일부터 삭제됩니다.
    """
    log_dir = os.path.join(config_dir, ".log")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_files = [f for f in os.listdir(log_dir) if re.match(r"kis_exec_\d{8}\.log", f)]
    log_files.sort()
    while len(log_files) >= 100:
        file_to_delete = log_files.pop(0)
        os.remove(os.path.join(log_dir, file_to_delete))
        logging.info(f"🗑️ Old log file deleted: {file_to_delete}")

    now_kst = TimeService.now_kst_naive()
    today_str = now_kst.date().strftime("%Y%m%d")
    log_name = f"kis_exec_{today_str}.log"
    log_file = os.path.join(log_dir, log_name)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


@dataclass
class KISConfig:
    app_key: str
    app_secret: str
    base_url: str
    account_number: str
    polling_interval: int
    stock_minute_tr_id: str
    deriv_minute_tr_id: str
    option_chain_tr_id: str
    deriv_order_tr_id: str
    deriv_order_rvsecncl_tr_id: str
    deriv_balance_tr_id: str
    deriv_order_list_tr_id: str
    config_dir: str

    def __init__(self, config_path: str):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.base_url = config.get("base_url")
        account_no = config.get("account_no", "")
        account_no_sub = config.get("account_no_sub", "")
        self.account_number = f"{account_no}-{account_no_sub}"
        self.polling_interval = config.get("polling_interval", 2)
        self.stock_minute_tr_id = config.get("tr_id", {}).get("stock_minute", "FHKST03010200")
        self.deriv_minute_tr_id = config.get("tr_id", {}).get("deriv_minute", "FHKIF03020200")
        self.option_chain_tr_id = config.get("tr_id", {}).get("option_chain", "FHPIF05030100")    # ADJ: "FHlkPIF05030100" > "FHPIF05030100"
        self.deriv_order_tr_id = config.get("tr_id", {}).get("deriv_order", "TTTO1101U")
        self.deriv_order_rvsecncl_tr_id = config.get("tr_id", {}).get("deriv_order_rvsecncl", "TTTO1103U")
        self.deriv_balance_tr_id = config.get("tr_id", {}).get("deriv_balance", "CTFO6118R")
        self.deriv_order_list_tr_id = config.get("tr_id", {}).get("deriv_order_list", "TTTO5201R")
        
        self.app_key = config.get("app_key")
        self.app_secret = config.get("app_secret")
        self.config_dir = os.path.dirname(config_path)


class KISAuth:
    def __init__(self, config: KISConfig, client: httpx.Client):   # (HJ) ADJ: 비동기 httpx.AsyncClient -> 동기 httpx.Client
        self._config = config
        self._client = client
        self._token_file = os.path.join(config.config_dir, "access_token-" + config.account_number + ".json") # (HJ) ADJ: 계좌별 OAuth 인증요청 따로 해야됨에 따라 인증토큰 관리파일도 계좌별로 따로 생성. (토큰번호는 동일하게 저장되지만, 계좌별로 OAuth 인증요청을 따로 진행해 주어야 해당 토큰을 이용한 API 접근이 허용됨.)
        self._access_token: str | None = None
        logging.info(f"🔐 Find access token for account: {self._token_file}") # (HJ) DEBUG: 토큰저장경로 확인용
        self._token_expires_at: datetime | None = None
        self._load_token()
        # self._load_token() # __init__ is not async, so we cannot call async methods from here.

    def _load_token(self):
        try:
            if os.path.exists(self._token_file):
                with open(self._token_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._access_token = data.get("access_token")
                    expires_str = data.get("expires_at")
                    if expires_str:
                        self._token_expires_at = datetime.fromisoformat(expires_str)
                        
                        if self._should_refresh_token():
                            self._clear_token()
                            self.get_access_token()
                            logging.info("🔐 Access token has been refreshed (It will expire within 12 hour)")
            # (HJ) ADJ: KISAuth 객체 생성 후, access_token json 파일이 없으면 자동 생성
            else: 
                self.get_access_token()
                logging.info("🔐 Access token file not found - created new access token file for the KisTradingAgent instance.")
                
        except Exception as e:
            logging.warning(f"Failed to load saved token: {e}")

    def _should_refresh_token(self) -> bool:
        if not self._token_expires_at:
            return True
        
        now = datetime.now()
        time_until_expiry = self._token_expires_at - now
        return time_until_expiry <= timedelta(hours=12)

    def _clear_token(self):
        try:
            if os.path.exists(self._token_file):
                os.remove(self._token_file)
                logging.info(f"🗑️ Deleted existing token file: {self._token_file}")
        except Exception as e:
            logging.warning(f"Failed to delete existing token file: {e}")
        
        self._access_token = None
        self._token_expires_at = None

    def _save_token(self):
        try:
            data = {
                "account_number": self._config.account_number,  # (HJ) ADJ: 계좌별 인증토큰 관리 위한 값 추가
                "access_token": self._access_token,
                "expires_at": self._token_expires_at.isoformat() if self._token_expires_at else None
            }
            with open(self._token_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Failed to save token: {e}")

    # (HJ) ADJ: 동기 메서드로 변경 (datafeeding 과정과 다르게 execution 에서는 토큰 선행확인 후 코드 작동이 가능)
    def get_access_token(self) -> str:
        if self._should_refresh_token():
            self._clear_token()
        
        if self._access_token and self._token_expires_at and datetime.now() < self._token_expires_at:
            return self._access_token
        
        logging.info("Requesting new Access Token.")
        url = f"{self._config.base_url}/oauth2/tokenP"
        body = {
            "grant_type": "client_credentials", 
            "appkey": self._config.app_key, 
            "appsecret": self._config.app_secret
        }
        response = self._client.post(url, json=body)
        response.raise_for_status()     # (HJ) 토큰 api 요청에 대한 응답 통신 상탱 확인
        data = response.json()
        
        self._access_token = data.get("access_token")
        expires_in = data.get("expires_in", 0)
        self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 600)
        self._save_token()
        logging.info("Access Token has been successfully renewed.")
        return self._access_token
