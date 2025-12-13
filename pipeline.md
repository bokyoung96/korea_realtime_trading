### korea_realtime_trading 시스템 파이프라인 문서

본 문서는 HT_API 코드베이스의 전체 구조, 데이터 플로우, 시간/DB 정책, 실행 방법, 확장 방법을 상세히 설명합니다. 운영/개발/테스트에 필요한 기준을 한 파일에서 참조할 수 있도록 구성했습니다.

---

### 1) 목표와 설계 원칙
- 실시간·분봉 데이터(주식/파생/옵션체인) 수집 → 가공(매트릭스) → 저장 → 전략 신호 생성까지의 안정적 파이프라인
- 원칙: SOLID, 클래스 중심, 타입 힌트, 비동기 I/O, 사이드이펙트 최소화, KST 기준 일관성 유지

---

### 2) 디렉터리 구조와 역할

```
src/
  base.py                 # KIS 설정/인증 (KISConfig, KISAuth, setup_logging)
  core/                   # 폴링/큐/피드 오케스트레이션
    feed.py               # KISDataFeed (PollingManager를 사용해 fetchers 스케줄링)
    polling.py            # PollingManager (주기적 fetch 루프)
    subscription.py       # SubscriptionManager (구독 리스트 보관)
  fetchers/               # 외부 API 수집기 (종목/파생/옵션 체인)
    base_fetcher.py       # PriceFetcher 추상 클래스
    stock_fetcher.py      # 주식 분봉 수집
    deriv_fetcher.py      # 선물 분봉 수집
    option_chain_fetcher.py # 옵션 체인 수집
    factory.py            # FetcherFactory (구독 타입→fetcher 매핑)
  processing/             # 데이터 처리(매트릭스 등)
    processors.py         # DataProcessor (큐→라이터 저장/매트릭스 집계)
    matrix_processor.py   # OptionMatrixProcessor (체인→매트릭스 변환)
  database/               # DB 접속/스키마/쓰기
    config.py             # DatabaseConfig (Postgres URL, Pool 설정)
    connection.py         # DatabaseConnection (asyncpg pool)
    data_writer.py        # DataWriter (캔들/매트릭스 저장)
    schemas.py            # 스키마/DDL
  services/               # 공통 서비스
    time_service.py       # TimeService (KST aware/naive 유틸)
  strategies/
    dolpha1/              # 전략: 실시간/과거 수집, 검증, 신호 생성
      feeder.py           # RealtimeDataCollector/HistoricalDataCollector
      signals.py          # SignalGenerator/SignalDatabase
      dolpha1.py          # 전략 진입점(배치에서 실행)
  models/
    dataclasses.py        # CandleData, OptionChainData 등 DTO
    enums.py              # DataType, MarketType
  consts.py               # 장 시간/매직넘버 상수(Constants)
  utils.py                # is_market_open (TimeService+Constants 기반)
  orchestration.py        # DataFeedBuilder/Orchestrator
  main.py                 # 일반 실행 진입점
```

특징
- 절대 임포트 고정(`from database.connection import ...`). 패키지 `__init__.py`에서는 상대 임포트로 공개 API 재노출
- 배치 실행이 `src`를 루트로 보장하므로 임포트 충돌 없음

---

### 3) 시간(Time) 정책: KST 기준 일관화

- 저장/비교는 모두 KST-naive(datetime, tzinfo=None)로 통일
- 외부 입력이나 시스템 생성 시각이 tz-aware일 경우, DB 쓰기/비교 전에 `TimeService.to_kst_naive(dt)`로 정규화
- 장 시간 판단·폴링 기준 시각·UI 출력은 `TimeService.now_kst()` 또는 `now_kst_naive()` 사용

핵심 API
```python
from services.time_service import TimeService

aware_kst = TimeService.now_kst()            # tz-aware KST (tzinfo=+09:00)
naive_kst = TimeService.now_kst_naive()      # tzinfo=None, 값은 KST 벽시각
floored   = TimeService.floor_minute_kst()   # 현재 시각 분 단위 바닥 내림(KST naive)
normalized = TimeService.to_kst_naive(dt)    # 임의 dt를 KST naive로 변환
```

주의
- tz-aware와 tz-naive 혼합 비교는 파이썬에서 TypeError를 유발
- Postgres 컬럼이 TIMESTAMP(타임존 없음)이므로 tz-aware를 그대로 넣지 않음

---

### 4) 데이터 플로우

1) 진입(main)
- `main.py`에서 시장 개시 대기(파생 `Constants.MARKET_HOURS_DERIV_START`), DB 초기화
- `DataFeedBuilder`로 구독 추가 → `build()` → `DataFeedOrchestrator.start()`

2) 구독/오케스트레이션(orchestration)
- `SubscriptionManager`가 구독 리스트 보관
- `FetcherFactory`가 구독 타입에 맞는 fetcher 인스턴스 생성
- `KISDataFeed.start_feed()`가 `PollingManager`로 fetchers 스케줄링
- 공유 큐로 데이터를 `DataProcessor`에 전달

3) 수집(fetchers)
- `PriceFetcher`(추상): 공통 헤더 생성, 장 시간 체크, 캔들 핸들링 엔트리
- `StockPriceFetcher`/`DerivPriceFetcher`: 분봉 API 호출 → 완결 캔들 선택 → DTO 변환
- `OptionChainFetcher`: 옵션체인 호출/파싱 → `OptionChainData` 발행

4) 처리(processing)
- `DataProcessor`: 큐 데이터 타입에 따라 분기
  - 캔들: 배치 큐에 추가(라이터가 모아서 저장)
  - 옵션 체인: `OptionMatrixProcessor.update()` → 최신 매트릭스 획득 → 라이터에 저장 위임

5) 저장(database)
- `DatabaseConnection`: asyncpg 풀, 동적 테이블 생성
- `DataWriter`: 
  - 캔들: `executemany`로 bulk upsert
  - 매트릭스: 메트릭별 행으로 upsert (timestamp, underlying_symbol, metric_type 유니크)
  - 모든 timestamp 인수는 KST-naive로 정규화 후 저장

6) 전략(strategies/dolpha1)
- `RealtimeDataCollector`: 실시간 폴링 → 테이블(`dolpha1`) upsert
- `HistoricalDataCollector`: 과거 일자별 수집/검증/자동 보완
- `SignalGenerator`: 피처(VWAP/ATR/밴드 등) 생성, 모니터/트레이드 신호 산출
- `SignalDatabase`: 신호 테이블(`dolpha1_signal`) upsert

---

### 5) 주요 클래스와 책임

- 설정/인증
  - `KISConfig`: 설정 로드(app key/secret, polling interval 등)
  - `KISAuth`: 토큰 캐시/갱신, 파일 저장/로딩

- 오케스트레이션
  - `DataFeedBuilder`: 구독 DSL (`add_stock`, `add_deriv`, `add_option_chain`)
  - `DataFeedOrchestrator`: fetchers/processor/writer 실행을 총괄
  - `PollingManager`: 분 주기 fetch 루프와 재시도 로직

- 수집(Fetchers)
  - `PriceFetcher`: 공통 인터페이스, `fetch_data()` 추상
  - `StockPriceFetcher`/`DerivPriceFetcher`/`OptionChainFetcher`: 시장별 구현
  - `FetcherFactory`: DataType→구체 fetcher 매핑

- 처리/매트릭스
  - `DataProcessor`: 큐→저장/매트릭스 업데이트
  - `OptionMatrixProcessor`: 옵션 체인 → ATM/ITM/OTM 기준 매트릭스 산출

- 데이터 계층
  - `DatabaseConnection`: 풀/쿼리/동적 테이블 생성
  - `DataWriter`: 캔들/매트릭스 upsert, 배치 쓰기

- 전략(dolpha1)
  - `RealtimeDataCollector`/`HistoricalDataCollector`: 실시간/과거 수집
  - `SignalGenerator`: 피처/밴드/신호
  - `SignalDatabase`: 신호 저장

- 공통 서비스
  - `TimeService`: KST aware/naive 변환, 분 바닥 내림
  - `Constants`: 장시간, 기대 캔들 수, 재시도 상수

---

### 6) 시간 처리 패턴 (예시)

```python
from services.time_service import TimeService
from database.data_writer import DataWriter

# tz-aware 입력이 올 수 있는 경우
dt_input = TimeService.now_kst()            # aware
dt_for_db = TimeService.to_kst_naive(dt_input)  # naive KST로 정규화

# 분 바닥 내림 비교 기준
now_floor = TimeService.floor_minute_kst()
if record_timestamp < now_floor:
    pass  # 안전 비교 (둘 다 naive-KST)
```

---

### 7) DB 스키마 개요

- 캔들(동적)
  - `futures_{sym3}`: timestamp, symbol, open/high/low/close, volume, UNIQUE(timestamp, symbol)
  - `stocks_1m`: timestamp, symbol, timeframe, open/high/low/close, volume

- 옵션 체인 원시(`option_chain_raw`)
  - 체인 시점별 옵션 행 데이터

- 옵션 매트릭스(동적)
  - `option_matrices_{underlying}`: (timestamp, underlying_symbol, metric_type) + c_/p_ (itm…atm…otm…)

- 시스템 상태(`system_status`)
  - component/status/message/data_count/last_data_time

모든 timestamp는 TIMESTAMP(타임존 없음)이며, KST-naive로 저장

---

### 8) 오류/재시도/안정성

- `PollingManager`: 실패 시 지수 증가형에 가까운 대기 재시도 (간단한 backoff)
- fetchers: HTTP 에러/응답 오류 시 경고 로그 후 재시도
- writer: 배치 큐 기반으로 쓰기; 예외는 로깅

---

### 9) 구성/실행

- 실행
  - 루트 `HT_API/run.bat` 또는 전략 배치 `strategies/dolpha1/dolpha1.bat`
  - 배치는 `src`를 실행 루트로 보장, `PYTHONPATH` 설정

- 설정 파일
  - `src/config.json`: KIS API 설정, 트랜잭션 ID, 폴링 간격 등
  - `src/config_db.json`: Postgres 접속/풀 설정

---

### 10) 확장 가이드

- 새 Fetcher 추가
  1) `PriceFetcher` 상속, `fetch_data()` 구현
  2) `FetcherFactory`에 등록

- 새 매트릭스/지표 추가
  1) `OptionMatrixProcessor`에 컬럼/산출 로직 추가
  2) `DataWriter.save_option_matrices` 컬럼 매핑 확장

- 새 전략 추가
  1) `strategies/<name>` 디렉터리 생성
  2) 실시간/과거 수집기, 신호 제너레이터/DB 구성

---

### 11) 테스트/디버깅 팁

- 시간 의존 로직: `TimeService`만 모킹/주입하면 대다수 커버 가능
- DB 의존: `DatabaseConnection`을 테스트 컨피그 또는 테스트 더블로 대체
- 로깅: 레벨 INFO/DEBUG 조절로 잡음 제어

---

### 12) 용어

- KST aware: tzinfo=+09:00이 포함된 datetime
- KST naive: KST 벽시각이지만 tzinfo=None인 datetime (DB/비교용)
- 매트릭스: 옵션 체인을 ATM/ITM/OTM 구간으로 집계한 단면 데이터 테이블

---

### 13) 운영 체크리스트

- 배치로 실행(루트 위치/`PYTHONPATH` 보장)
- DB 연결/테이블 생성 로그 확인
- 옵션 매트릭스 저장 시 타임존 에러가 없고, 분 단위 갱신이 지속되는지 확인
- dolpha1 검증 로그: 각 일자 캔들 수가 기대치(`Constants.EXPECTED_CANDLES_PER_DAY`)와 일치하는지 확인


---

### 14) 클래스 계층/상속 개요

- Fetchers
  - PriceFetcher(ABC)
    - StockPriceFetcher
    - DerivPriceFetcher
    - OptionChainFetcher

- Processing
  - OptionMatrixProcessor (단독)
  - DataProcessor (큐 컨슈머)

- Orchestration
  - DataFeedBuilder (DSL)
  - DataFeedOrchestrator (런타임 조립)
  - KISDataFeed (PollingManager 관리)
  - PollingManager (주기적 실행)
  - SubscriptionManager (상태 보관)

- Database
  - DatabaseConnection (풀/쿼리)
  - DataWriter (upsert/배치)

- Strategy: dolpha1
  - DataFeeder (공통)
    - RealtimeDataCollector
    - HistoricalDataCollector
  - SignalGenerator
  - SignalDatabase

---

### 15) 런타임 시퀀스(요약)

```mermaid
sequenceDiagram
  autonumber
  participant Main as main.py
  participant Orchestrator as DataFeedOrchestrator
  participant Feed as KISDataFeed
  participant Poll as PollingManager
  participant Fetcher as PriceFetcher*
  participant Proc as DataProcessor
  participant Writer as DataWriter

  Main->>Orchestrator: build() & start()
  Orchestrator->>Feed: start_feed()
  Orchestrator->>Proc: process_data()
  Feed->>Poll: start_polling()
  loop every minute + interval
    Poll->>Fetcher: fetch_data()
    Fetcher-->>Proc: queue.put(processed)
    Proc->>Writer: save_candle_data/save_option_matrices
  end
```

옵션 체인→매트릭스 흐름

```mermaid
flowchart LR
  A[OptionChainFetcher
  OptionChainData] --> B[OptionMatrixProcessor.update]
  B --> C[get_current_matrices]
  C --> D[DataWriter.save_option_matrices]
  D --> E[(option_matrices_*)]
```

---

### 16) 설정 파일 레퍼런스

- config.json
```json
{
  "base_url": "https://openapi.example.com", 
  "account_no": "12345678",
  "account_no_sub": "01",
  "polling_interval": 2,
  "tr_id": {
    "stock_minute": "FHKST03010200",
    "deriv_minute": "FHKIF03020200",
    "option_chain": "FHlkPIF05030100"
  },
  "app_key": "...",
  "app_secret": "..."
}
```

- config_db.json
```json
{
  "postgres_url": "postgresql://user:pass@host:5432/db",
  "pool_settings": {
    "min_size": 1,
    "max_size": 10,
    "server_settings": { "jit": "off" }
  }
}
```

---

### 17) 에러 처리 정책

- 네트워크/HTTP
  - fetchers: Request/HTTPStatus 예외 로깅 후 재시도 (기본 3회), 실패 시 스킵 및 다음 주기
- 폴링 루프
  - 개별 fetch 실패 시 모아서 재시도 루프(점진적 대기), 10회 후 에러 로그
- DB
  - INSERT/UPSERT 예외 시 에러 로그, 다음 배치로 진행 (중단 최소화)
- 처리
  - 큐 컨슈밍에서 예외 캡처 후 로깅, 루프 지속

---

### 18) 로깅 컨벤션

- 이모지 유지, 사용자 가독성 우선
- 레벨: INFO(주요 이벤트)/WARNING(회복 가능)/ERROR(실패)/DEBUG(상세)
- 예:
  - 시작/정상 완료: ✅ 🚀 🎉
  - 재시도/대기: 🔄 ⏱️
  - 경고/주의: ⚠️
  - 실패: ❌

---

### 19) 성능·확장성

- asyncpg 풀: max_size 적절히 조정 (기본 10)
- 배치 쓰기: 캔들은 이미 executemany 사용
- 매트릭스 쓰기: 메트릭별 개별 INSERT → 향후 executemany로 묶는 개선 여지
- 인덱스: timestamp/symbol/metric_type에 적절한 인덱스 존재
- 폴링: 분 바닥+interval 동기화로 잔여 초 최소화

---

### 20) 테스트 전략

- 단위: TimeService, OptionMatrixProcessor, SignalGenerator
- 통합: Fetcher↔Processor↔Writer (테스트 DB)
- E2E: 배치 실행 후 로그/DB 상태 검증

---

### 21) 확장 레시피

- 새 데이터 소스
  - PriceFetcher 상속 → Factory 등록 → SubscriptionManager 추가
- 새 지표/매트릭스
  - matrix_processor에 컬럼/산출 추가 → writer 컬럼 매핑 확장
- 저장 모델 교체
  - schemas/data_writer 조정, 나머지는 동일 API 유지

---

### 22) 보안/시크릿

- 토큰 파일 저장: `access_token.json` (만료 임박 시 자동 갱신/삭제)
- 시크릿은 config.json 외부 보관 권장(환경변수/시크릿 매니저)

---

### 23) 타임존 FAQ

- 왜 KST-naive인가?
  - DB TIMESTAMP가 타임존을 보관하지 않으므로, tz-aware와 혼합 시 TypeError/혼동 발생
  - 정책: 모든 저장/비교 값을 KST-naive로 통일

- aware↔naive 변환은?
  - `TimeService.to_kst_naive(dt)` 사용

---

### 24) 트러블슈팅

- 증상: "can't compare offset-naive and offset-aware datetimes"
  - 원인: tz-aware와 naive 비교/저장 혼합
  - 해결: TimeService로 KST-naive 정규화 후 비교/저장

- 옵션 매트릭스 INSERT 충돌
  - 확인: UNIQUE(timestamp, underlying_symbol, metric_type) 키 중복
  - 조치: ON CONFLICT 업데이트 경로 정상 동작 확인

