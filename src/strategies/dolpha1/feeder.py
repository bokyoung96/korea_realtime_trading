import asyncio
import logging
from datetime import datetime, timezone, timedelta, time
from typing import Dict, Any, List, Optional
import os
import sys
import httpx
import pandas as pd
import pandas_market_calendars as mcal

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from base import KISAuth, KISConfig
from services.time_service import TimeService
from consts import Constants
from database.connection import DatabaseConnection
from database.config import DatabaseConfig


class DataFeeder:
    def __init__(self, symbol: str = "106W09", table_name: str = "dolpha1"):
        self.symbol = symbol
        self.table_name = table_name
        self.config = KISConfig(config_path=os.path.join(PROJECT_ROOT, "config-futures.json"))
        db_config = DatabaseConfig.from_json(config_path=os.path.join(PROJECT_ROOT, "config_db.json"))
        self.db_connection = DatabaseConnection(db_config)
        self._polling_task: Optional[asyncio.Task] = None
        self._last_processed_time: Optional[str] = None
        
    async def initialize(self):
        if not self.db_connection.pool:
            await self.db_connection.initialize()
        await self._ensure_table_exists()
        logging.info(f"✅ {self.table_name} initialized")
        
    async def _ensure_table_exists(self):
        async with self.db_connection.pool.acquire() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    timestamp TIMESTAMP NOT NULL,
                    symbol TEXT NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume BIGINT,
                    PRIMARY KEY (timestamp, symbol)
                );
            """)
            
    async def close(self):
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        if self.db_connection.pool:
            try:
                await asyncio.wait_for(self.db_connection.close(), timeout=5.0)
            except asyncio.TimeoutError:
                logging.warning("⚠️ Database connection close timed out after 5 seconds")
                await self.db_connection.pool.close()


class RealtimeDataCollector(DataFeeder):
    def __init__(self, symbol: str = "106W09", table_name: str = "dolpha1"):
        super().__init__(symbol, table_name)
        self.polling_interval = 2
        
    async def start_realtime_feed(self, data_handler=None):
        self._polling_task = asyncio.create_task(
            self._poll_realtime_data(data_handler)
        )
        await self._polling_task
        
    async def _poll_realtime_data(self, data_handler):
        async with httpx.AsyncClient(timeout=10.0) as client:
            auth = KISAuth(self.config, client)
            
            while True:
                try:
                    if not self._is_trading_hours():
                        await asyncio.sleep(60)
                        continue
                    
                    # (HJ) TODO: Q. 반복문 안에서 비동기 wait 데이터 호출 반복하면, 데이터 호출 안되는 정규장 이외시간에 호출대기 task 계속 쌓이는 문제 없나?
                    # (HJ) TODO: (물론 위에서 if not self._is_trading_hours(): 조건문으로 정규장 시간확인 하기는 하지만, 방어적 프로그래밍 관점에서!)
                    candle_data = await self._fetch_latest_candle(client, auth)
                    if candle_data:
                        await self.save_data(candle_data)
                        if data_handler:
                            await data_handler(candle_data)
                            
                    await asyncio.sleep(self.polling_interval)
                    
                except Exception as e:
                    logging.error(f"❌ Realtime feed error: {e}")
                    await asyncio.sleep(5)
                    
    def _is_trading_hours(self) -> bool:
        now = TimeService.now_kst()
        current_time = now.time()
        return Constants.MARKET_HOURS_DERIV_START <= current_time <= Constants.MARKET_HOURS_DERIV_END
        
    async def _fetch_latest_candle(self, client: httpx.AsyncClient, auth: KISAuth) -> Optional[Dict[str, Any]]:
        url = f"{self.config.base_url}/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {await auth.get_access_token()}",
            "appKey": self.config.app_key,
            "appSecret": self.config.app_secret,
            "tr_id": self.config.deriv_minute_tr_id,
        }
        
        params = {
            "fid_cond_mrkt_div_code": "F",
            "fid_input_iscd": self.symbol,
            "fid_hour_cls_code": "60",
            "fid_pw_data_incu_yn": "Y",
            "fid_fake_tick_incu_yn": "N",
            "fid_input_date_1": "",
            "fid_input_hour_1": TimeService.now_kst_naive().strftime("%H%M%S"),
        }
        
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logging.warning(f"⚠️ Failed to fetch realtime data: {e}")
            return None
        
        if data.get("rt_cd") != "0" or not data.get("output2"):
            return None
            
        candles = data["output2"]
        current_time = candles[0].get("stck_cntg_hour")
        
        if self._last_processed_time and self._last_processed_time >= current_time:
            return None
            
        if not self._last_processed_time:
            logging.info(f"⏳ [{self.symbol}] First run - processing first available candle...")
            
        self._last_processed_time = current_time
        
        completed_candle = self._select_completed_candle(candles, current_time)
        if completed_candle:
            date_str = completed_candle.get("stck_bsop_date")
            today_str = TimeService.now_kst_naive().strftime("%Y%m%d")
            if date_str != today_str:
                return None
            return self._process_candle(completed_candle)
            
        return None
        
    def _select_completed_candle(self, candles: List[Dict], current_time: str) -> Optional[Dict]:
        if not candles:
            return None
        
        # (HJ) ADJ: 기존에 응답결과에서 하나 직전 분봉 가져오던 candles[1] 코드를 응답결과 최신 분봉 가져오는 candles[0] 코드로 수정
        return candles[0]
        # if current_time.startswith("1545"):
        #     return candles[0]
        # ### TODO: 원래 candles[0] 이었는데 candles[1] 로 바꿔서 확인 예정
        # return candles[1] if len(candles) > 1 else candles[0]   # (HJ) TODO: return candels[0] 되야할 듯 (log_msg 에 "🕐" 시작으로 찍히는 OHLCV 결과가 log 찍히는 시간보다 1분 이전 분봉과 일치)
        
    def _process_candle(self, candle: Dict) -> Dict[str, Any]:
        date_str = candle.get("stck_bsop_date")
        time_str = candle.get("stck_cntg_hour")
        
        timestamp_dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
        if time_str != "154500":
            timestamp_dt += timedelta(minutes=1)
            
        candle_data = {
            "timestamp": timestamp_dt,
            "symbol": self.symbol,
            "open": float(candle.get("futs_oprc", 0)),
            "high": float(candle.get("futs_hgpr", 0)),
            "low": float(candle.get("futs_lwpr", 0)),
            "close": float(candle.get("futs_prpr", 0)),
            "volume": int(candle.get("cntg_vol", 0)),
        }
        
        log_msg = f"🕐 [{self.symbol}] 1m: OHLCV {candle_data['open']:.2f}/{candle_data['high']:.2f}/{candle_data['low']:.2f}/{candle_data['close']:.2f} Vol: {candle_data['volume']:,}"
        logging.info(log_msg)
        
        return candle_data
        
    async def save_data(self, candle_data: Dict[str, Any]):
        try:
            timestamp = candle_data['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            if isinstance(timestamp, datetime) and timestamp.tzinfo is not None:
                timestamp = TimeService.to_kst_naive(timestamp)
                
            async with self.db_connection.pool.acquire() as conn:
                await conn.execute(f"""
                    INSERT INTO {self.table_name} (timestamp, symbol, open, high, low, close, volume)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (timestamp, symbol) DO UPDATE SET
                        open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                        close = EXCLUDED.close, volume = EXCLUDED.volume;
                """, 
                    timestamp, candle_data['symbol'], candle_data['open'],
                    candle_data['high'], candle_data['low'], candle_data['close'], candle_data['volume']
                )
        except Exception as e:
            logging.error(f"❌ Failed to save data: {e}")


class HistoricalDataCollector(DataFeeder):
    def __init__(self, symbol: str = "106W09", table_name: str = "dolpha1"):
        super().__init__(symbol, table_name)
        
    def get_trading_days(self, days_back: int = 30) -> List[str]:
        krx = mcal.get_calendar("XKRX")
        end_date = TimeService.now_kst()
        start_date = end_date - timedelta(days=days_back * 2)
        
        schedule = krx.schedule(start_date=start_date.date(), end_date=end_date.date())
        trading_days = schedule[schedule.index < pd.to_datetime(end_date.date())].index[-days_back:]
        
        return [day.strftime("%Y%m%d") for day in trading_days]
        
    async def _get_existing_data_status(self) -> Dict[str, int]:
        async with self.db_connection.pool.acquire() as conn:
            query = f"""
                SELECT 
                    TO_CHAR(timestamp, 'YYYYMMDD') as date_str,
                    COUNT(*) as count
                FROM {self.table_name}
                WHERE symbol = $1
                GROUP BY date_str
            """
            records = await conn.fetch(query, self.symbol)
            return {rec['date_str']: rec['count'] for rec in records}
        
    async def collect_historical_data(self, days_back: int = 15):
        await self.initialize()
        trading_days = self.get_trading_days(days_back)
        logging.info(f"📅 Starting {len(trading_days)} days historical data collection")
        
        existing_data = await self._get_existing_data_status()
        
        total_records = 0
        for i, date_str in enumerate(trading_days, 1):
            if date_str in existing_data and existing_data[date_str] >= 411: 
                logging.info(f"📅 [{i}/{len(trading_days)}] {date_str}: Already has {existing_data[date_str]} records - skipping")
                continue
                
            logging.info(f"📅 [{i}/{len(trading_days)}] Processing {date_str}...")
            try:
                raw_candles = await self._fetch_day_data(date_str)
                if raw_candles:
                    processed_records = self._process_historical_candles(raw_candles)
                    await self._save_batch(processed_records)
                    total_records += len(processed_records)
                    logging.info(f"✅ {date_str}: {len(processed_records)} saved")
            except Exception as e:
                logging.error(f"❌ {date_str} Processing failed: {e}")
                
        logging.info(f"🎉 Historical data collection complete! Total {total_records} new records")
        
    async def collect_today_missing_data(self):
        now = TimeService.now_kst()
        
        if now.time() < Constants.MARKET_HOURS_DERIV_START:
            logging.info("📅 Market not started yet")
            return
            
        today_str = now.strftime("%Y%m%d")
        logging.info(f"📅 Collecting today's missing data for {today_str}")
        
        try:
            raw_candles = await self._fetch_day_data(today_str)
            if raw_candles:
                processed_records = self._process_historical_candles(raw_candles)
                current_minute_naive = TimeService.floor_minute_kst(now)
                filtered = [r for r in processed_records if r['timestamp'] < current_minute_naive]
                
                if filtered:
                    await self._save_batch(filtered)
                    logging.info(f"✅ Today's missing data: {len(filtered)} records saved")
        except Exception as e:
            logging.error(f"❌ Failed to collect today's missing data: {e}")
            
    async def _fetch_day_data(self, date_str: str) -> List[Dict[str, Any]]:
        all_candles = []
        url = f"{self.config.base_url}/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            auth = KISAuth(self.config, client)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {await auth.get_access_token()}",
                "appKey": self.config.app_key,
                "appSecret": self.config.app_secret,
                "tr_id": self.config.deriv_minute_tr_id,
            }
            
            next_query_time = "154500"
            market_start = datetime.strptime(f"{date_str}084500", "%Y%m%d%H%M%S")
            
            for _ in range(10):
                params = {
                    "fid_cond_mrkt_div_code": "F",
                    "fid_input_iscd": self.symbol,
                    "fid_hour_cls_code": "60",
                    "fid_pw_data_incu_yn": "Y",
                    "fid_fake_tick_incu_yn": "N",
                    "fid_input_date_1": date_str,
                    "fid_input_hour_1": next_query_time,
                }
                
                data = None
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = await client.get(url, headers=headers, params=params)
                        response.raise_for_status()
                        data = response.json()
                        break
                    except (httpx.RequestError, httpx.HTTPStatusError) as e:
                        logging.warning(f"❌ Retry {attempt + 1}/{max_retries} for {next_query_time}: {e}")
                        if attempt + 1 == max_retries:
                            logging.error(f"❌ {date_str} {next_query_time} failed")
                            return []
                        await asyncio.sleep(1)
                
                if not data or data.get("rt_cd") != "0" or not data.get("output2"):
                    break
                    
                candles = data["output2"]
                all_candles.extend(candles)
                logging.info(f"📊 {len(candles)} candles collected")
                
                earliest = candles[-1]
                earliest_time = earliest.get("stck_cntg_hour")
                earliest_dt = datetime.strptime(f"{date_str}{earliest_time}", "%Y%m%d%H%M%S")
                
                if earliest_dt <= market_start:
                    break
                    
                next_query_time = earliest_time
                await asyncio.sleep(0.2)
                    
        df = pd.DataFrame(all_candles)
        unique_candles = df.drop_duplicates(subset=['stck_bsop_date', 'stck_cntg_hour']).to_dict('records')
        logging.info(f"📈 {date_str}: Total {len(unique_candles)} unique candles")
        return unique_candles
        
    def _process_historical_candles(self, candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        records = []
        
        for candle in candles:
            try:
                date_str = candle.get("stck_bsop_date")
                time_str = candle.get("stck_cntg_hour")
                if not date_str or not time_str:
                    continue
                    
                dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
                hour_min = dt.hour * 100 + dt.minute
                
                if not (845 <= hour_min <= 1545):
                    continue
                    
                # (HJ) ADJ: 기존에 응답결과에서 하나씩 직전 분봉 저저장하도록 시간 수정하는 timedelta(minutes=1) 코드 제거
                # if hour_min != 1545:
                #     dt += timedelta(minutes=1)
                    
                records.append({
                    "timestamp": dt,
                    "symbol": self.symbol,
                    "open": float(candle.get("futs_oprc", 0)),
                    "high": float(candle.get("futs_hgpr", 0)),
                    "low": float(candle.get("futs_lwpr", 0)),
                    "close": float(candle.get("futs_prpr", 0)),
                    "volume": int(candle.get("cntg_vol", 0)),
                })
            except Exception as e:
                logging.warning(f"⚠️ Failed to process candle: {e}")
                
        return records
        
    async def _save_batch(self, records: List[Dict[str, Any]]):
        if not records:
            return
            
        async with self.db_connection.pool.acquire() as conn:
            await conn.executemany(f"""
                INSERT INTO {self.table_name} (timestamp, symbol, open, high, low, close, volume)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (timestamp, symbol) DO UPDATE SET
                    open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                    close = EXCLUDED.close, volume = EXCLUDED.volume;
            """, [(r['timestamp'], r['symbol'], r['open'], r['high'], r['low'], r['close'], r['volume']) for r in records])
            
    async def verify_historical_data(self, days_back: int = 15, auto_fix: bool = False):
        logging.info("🔍 Starting data verification...")
        trading_days_list = self.get_trading_days(days_back)
        trading_days_set = set(trading_days_list)
        oldest_day = min(trading_days_list) if trading_days_list else None
        all_days_ok = True
        expected_per_day = 411
        incomplete_days = []
        
        async with self.db_connection.pool.acquire() as conn:
            query = f"""
                SELECT 
                    DATE(timestamp AT TIME ZONE 'Asia/Seoul') as trade_date, 
                    COUNT(*) as count
                FROM {self.table_name} 
                WHERE symbol = $1
                GROUP BY trade_date 
                ORDER BY trade_date;
            """
            daily_counts = await conn.fetch(query, self.symbol)
            
            db_days = {rec['trade_date'].strftime("%Y%m%d"): rec['count'] for rec in daily_counts}
            missing_days = trading_days_set - set(db_days.keys())
            
            if missing_days:
                for day in sorted(missing_days):
                    if day == oldest_day:
                        logging.warning(f"⚠️ {day}: Missing from database (oldest day - API limitation)")
                    else:
                        all_days_ok = False
                        logging.error(f"❌ {day}: Missing from database!")
                        incomplete_days.append(day)
                    
            for date_str in sorted(trading_days_set):
                if date_str in db_days:
                    count = db_days[date_str]
                    if count == expected_per_day:
                        logging.info(f"✅ {date_str}: OK ({count}/{expected_per_day})")
                    else:
                        if date_str == oldest_day:
                            logging.warning(f"⚠️ {date_str}: Incomplete ({count}/{expected_per_day}) - oldest day, API limitation")
                        else:
                            all_days_ok = False
                            logging.warning(f"❌ {date_str}: Incomplete! ({count}/{expected_per_day})")
                            if count < 411:
                                incomplete_days.append(date_str)
                        
        if all_days_ok:
            logging.info("🎉 Verification successful! All data complete")
        else:
            logging.warning(f"⚠️ Some data incomplete: {incomplete_days}")
            if auto_fix and incomplete_days:
                logging.info("🔧 Auto-fixing incomplete days...")
                for day in incomplete_days:
                    if day == oldest_day:
                        continue
                    try:
                        logging.info(f"📅 Fixing {day}...")
                        raw_candles = await self._fetch_day_data(day)
                        if raw_candles:
                            processed_records = self._process_historical_candles(raw_candles)
                            await self._save_batch(processed_records)
                            logging.info(f"✅ {day}: Fixed with {len(processed_records)} records")
                    except Exception as e:
                        logging.error(f"❌ Failed to fix {day}: {e}")


class RealTimeDataFeeder(RealtimeDataCollector, HistoricalDataCollector):
    pass