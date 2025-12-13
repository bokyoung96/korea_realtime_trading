import asyncio
import argparse
import logging
import warnings
from datetime import datetime, time, timedelta
from typing import Any, Dict

import numpy as np

import os
import sys

warnings.filterwarnings('ignore', category=UserWarning, module='pandas_market_calendars')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from base import KISConfig, setup_logging
from services.time_service import TimeService
from feeder import RealTimeDataFeeder
from signals import SignalGenerator, SignalDatabase
from telebot import send_tele   # (HJ) ADJ: 텔레그램 메시지 전송 함수

from executor.execution import execute_order    # (HJ) FEAT: KIS 매매집행 함수
from executor.exec_models import TradingSignal   # (HJ) FEAT: KIS 매매집행 함수의 signal 파라미터 인자 전달에 필요한 자료형
from executor.kis.api_auth.base import KISAuth, KISConfig, setup_exec_logging
from executor.kis.client.domestic_futures.client import KisTradingAgent

from consts import Constants


class Dolpha1Strategy:
    def __init__(
        self,
        symbol: str,     # A06603: 코스닥150선물 26년 3월물  # 106W12: 코스닥150선물 25년 12월물
        atr_period: int = 10,
        rolling_move: int = 5,
        band_multiplier: float = 1.0,
        use_vwap: bool = True,
        observe_interval_minutes: int = 15,     # (HJ) ADJ: trading_signal 생성주기 5 에서 15 로 변경
        is_real: bool = True,                   # (HJ) ADJ: 실제계좌 여부 플래그 (False 면 모의계좌)
        order_method: str = 'market',           # (HJ) ADJ: 매매집행 방식 ('market', 'limit' 등)
        leverage_ratio: float = 1.0,            # (HJ) ADJ: 레버리지 비율 속성 추가 (default=1배)
    ):
        self.symbol = symbol

        config_path = os.path.join(PROJECT_ROOT, "config-futures.json")
        self.config = KISConfig(config_path=config_path)

        self.feeder = RealTimeDataFeeder(symbol)
        self.signal_generator = SignalGenerator(
            atr_period=atr_period,
            rolling_move=rolling_move,
            band_multiplier=band_multiplier,
            use_vwap=use_vwap,
            observe_interval_minutes=observe_interval_minutes,
        )
        self.signal_database = SignalDatabase()

        self.last_signal_time = None
        self.observe_interval_minutes = observe_interval_minutes
        self.leverage_ratio = leverage_ratio
        
        # self.open_trading_time = time(hour=9, minute=1)
        # self.close_trading_time = time(hour=15, minute=29)

        # self.current_datetime = TimeService.now_kst_naive()       # TODO: 코드삭제예정
        # self.current_date = self.current_datetime.date()      # TODO: 코드삭제예정
        self.futures_market_open_time = Constants.MARKET_HOURS_DERIV_START
        # self.market_open_datetime = datetime.combine(self.current_date, self.futures_market_open_time)        # TODO: 코드삭제예정
        self.futures_market_close_time = Constants.MARKET_HOURS_DERIV_END
        # self.market_close_datetime = datetime.combine(self.current_date, self.futures_market_close_time)      # TODO: 코드삭제예정
        # self.first_trading_datetime = self.market_open_datetime + timedelta(minutes=self.observe_interval_minutes)        # TODO: 코드삭제예정
        # self.first_trading_time = self.first_trading_datetime.time()      # TODO: 코드삭제예정
        self.stock_market_open_time = Constants.MARKET_HOURS_STOCK_START
        self.liquidation_hour_min = time(hour=15, minute=29)    # 임시: 청산시간은 넌파라매트릭하게 임시로 지정하여 사용

        self.is_real = is_real                     # (HJ) ADJ: 실제계좌 여부 플래그 클래스변수 추가
        self.order_method = order_method           # (HJ) ADJ: 매매집행 방식 클래스변수 추가
        self.chat_title = "alphawave_dolpha1" if self.is_real else "alphawave_test" # (HJ) ADJ: (임시) 텔레그램 채팅방 구분용 클래스변수 추가
                        
        # (HJ) FEAT: KIS 매매집행
        self.rate_limit = 5 if self.is_real else 2   # (HJ) ADJ: KIS API 호출량 제한 규정에 따름

    async def initialize(self):
        await self.feeder.initialize()
        await self.signal_database.initialize()
        logging.info("🚀 dolpha1 system initialization complete")

    async def start_realtime_feed(self):
        await self.feeder.start_realtime_feed(data_handler=self._on_realtime_data)
        
    async def _on_realtime_data(self, candle_data):
        await self._check_signal()
            
    async def _check_signal(self):
        current_datetime = TimeService.now_kst_naive()
        current_date = current_datetime.date()
        currnet_time = current_datetime.time()  # 주의: 시, 분, 초 정보까지 찍힘
        currnet_hour_min = time(hour=currnet_time.hour, minute=currnet_time.minute)

        # 코스닥 선물 주간 정규거래시간 외 시그널 체크 스킵
        if (currnet_time < self.futures_market_open_time) or (currnet_time >= self.futures_market_close_time):
            logging.debug(f"🕐 Signal check skipped - outside trading hours: {currnet_time.strftime('%H:%M')}")
            return
        
        # 코스닥 선물 주간 정규거래시간 내 시그널 체크
        # (HJ) ADJ: if True 문 대신 if current_hour_min
        else:
            logging.debug(f"🔍 Checking for signals at {current_datetime.strftime('%H:%M:%S')}")
            recent_data = await self._get_recent_data()
            
            if len(recent_data) >= 100:
                signal_result = self.signal_generator.get_latest_signal(df=recent_data, 
                                                                        leverage_ratio=self.leverage_ratio)
                
                monitor_signal = signal_result['monitor_signal']
                trade_signal = signal_result['trade_signal']    # (HJ) TODO: 여기만 (current_hour_min == '15:29') 면 기존 포지션 0 만드는 청상 코드 / (current_hour_min > '15:29') 면 무조건 0 으로 수정필요!
                                                                # (HJ) TODO: 시그널 코드에서는 계좌 포지션 상태 알 수 있는 코드 없는데, 여기서는 closing liquidation 시그널 (e.x. -1 또는 2)만 정해주고 -> 여기서 시그널 받아서 매매집행하는 executor 에서 (1) 계좌잔고 확인 (2) 반대로 올청산 수행하는걸로!
                reason = signal_result['reason']    # (HJ) TODO: 여기도 (current_hour_min == '15:29') 면 'Closing liquidation' 으로 수정필요! 
                ub = signal_result['ub']
                lb = signal_result['lb']
                current_price = signal_result['current_price']
                is_observe_time = signal_result['is_observe_time']

                reason_splited = reason.split(' ')[:2]      # (HJ) FEAT: 텔레그램 메시지 길이 제한 고려한 이유 축약
                reason_shortcut = ' '.join(reason_splited)  # (HJ) FEAT: 텔레그램 메시지 길이 제한 고려한 이유 축약
                
                if ub is not None and lb is not None:
                    observe_mark = "🎯" if is_observe_time else "📊"
                    logging.info(f"{observe_mark} Price: {current_price:.2f} | UB: {ub:.2f} | LB: {lb:.2f} | Monitor: {monitor_signal} | Trade: {trade_signal} | {reason_shortcut}")
                else:
                    logging.info(f"📊 Signal check - Data points: {len(recent_data)}, Reason: {reason}")
                
                if not reason.startswith("insufficient_data"):
                    latest_day = recent_data.iloc[-1]['timestamp'].date()
                    today_day = TimeService.now_kst_naive().date()
                    if latest_day != today_day:
                        return
                    latest_row = recent_data.iloc[-1]
                    await self.signal_database.save_signal(
                        latest_row['timestamp'], latest_row['symbol'], signal_result
                    )

                    # observe_time 에 trade_singal 발생한 경우 (not liquidation_time)
                    if is_observe_time and (currnet_hour_min != self.liquidation_hour_min) and (trade_signal != 0):
                        
                        # 주간 정규거래시간 내 첫 거래인 경우
                            # 첫거래(first_trading) trading_signal 예외처리
                            # (8:45 trading_signal != 0) & (9:00 trading_signal != 0) 경우 
                            # 보유잔고 0 인데 "Enter <UB or LB or VWAP>" 시그널 발생
                            # -> reason_shortcut 이 "Enter" 로 시작하지 않는 경우에만 
                            # -> 아래 코드 실행
                                # 유의. abs(monitor_signal - previous_monitor_signal) == 2 인 경우,
                                # 유의. signals.py 에서 trading_signal 산정시 1 처리 -> 나중에 보완 필요
                        if (currnet_time < self.stock_market_open_time):
                            logging.info(f"ℹ️ TRADE SIGNAL! (EXCEPTION) {trade_signal} at {current_price:.2f} - {reason}")

                        # (HJ) ADJ: Trading signal logging 및 Trade execution 작동시간 제약조건 추가 ('08:59' < current_hour_min < '15:29')
                        # (HJ) ADJ: current_hour_min 이 logging 찍히는 TRADE SIGNAL 시간보다 앞서는 것 같아서, '09:00' <= 에서 '08:59' < 으로 조건문 변경
                        elif self.stock_market_open_time <= currnet_time < self.liquidation_hour_min: 
                            logging.info(f"🚨 TRADE SIGNAL! {trade_signal} at {current_price:.2f} - {reason}")

                            # (HJ) FEAT: 텔레그램 메시지 전송
                            signal_time = latest_row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                            signal_tele_msg = (
                                f"🚨 *DOLPHA1 TRADE SIGNAL*\n"
                                f"• Symbol: {self.symbol}\n"
                                f"• Time: {signal_time}\n"
                                f"• Current Price: {current_price:.2f}\n"
                                f"• Upper Band: {ub:.2f}\n"
                                f"• Lower Band: {lb:.2f}\n"
                                f"• Monitor Signal: {monitor_signal}\n"
                                f"• Trade Signal: {trade_signal}\n"
                                f"• Reason: {reason_shortcut}"
                            )
                            await send_tele(msg=signal_tele_msg, chat_title=self.chat_title)

                            exec_signal = TradingSignal(ticker=self.symbol, 
                                                        position=np.sign(trade_signal), 
                                                        volume=abs(trade_signal), 
                                                        target_price=current_price, 
                                                        message=reason_shortcut, 
                                                        target_position=int(monitor_signal), 
                                                        timestamp=signal_time)
                            await execute_order(exec_signal, 
                                                is_real=self.is_real, 
                                                order_method=self.order_method, 
                                                rate_limit=self.rate_limit, 
                                                logging=logging)
                            # (HJ) 참고. logging.info(<매매결과_로그>) 와 send_tele(<매매결과_메시지>) 는 execute_order() 함수 내에서 실행됨! 

                    # liquidation_time 에 도달한 경우
                    # (HJ) ADJ: 청산용 Trade execution 조건분기 추가 (current_hour_min == '15:29')
                    elif (currnet_hour_min == self.liquidation_hour_min):
                        logging.info(f"🚨 LIQUIDATE SIGNAL! liquidate position at {current_price:.2f}")

                        # (HJ) FEAT: 텔레그램 메시지 전송
                        signal_time = latest_row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                        signal_tele_msg = (
                            f"🚨 *DOLPHA1 LIQUIDATE SIGNAL*\n"
                            f"• Symbol: {self.symbol}\n"
                            f"• Time: {signal_time}\n"
                            f"• Current Price: {current_price:.2f}\n"
                            f"• Upper Band: {ub:.2f}\n"
                            f"• Lower Band: {lb:.2f}\n"
                            f"• Monitor Signal: {monitor_signal}\n"
                            f"• Trade Signal: - \n"
                            f"• Reason: Liquidate position"
                        )
                        await send_tele(msg=signal_tele_msg, chat_title=self.chat_title)

                        # (HJ) FEAT: KIS 매매집행
                        exec_signal = TradingSignal(ticker=self.symbol, 
                                                    position=None, 
                                                    volume=None, 
                                                    target_price=current_price, 
                                                    message=reason_shortcut, 
                                                    target_position='liquidation', 
                                                    timestamp=signal_time)
                        await execute_order(exec_signal, 
                                            is_real=self.is_real, 
                                            order_method=self.order_method, 
                                            rate_limit=self.rate_limit, 
                                            logging=logging)
            
            else:
                logging.warning(f"⚠️ Insufficient data for signal generation: {len(recent_data)}/100")
            
            self.last_signal_time = current_datetime


    async def _get_recent_data(self):
        try:
            async with self.feeder.db_connection.pool.acquire() as conn:
                query = f"""
                    SELECT timestamp, symbol, open, high, low, close, volume
                    FROM {self.feeder.table_name}
                    WHERE symbol = $1
                      AND timestamp >= NOW() - INTERVAL '30 days'
                    ORDER BY timestamp
                """
                records = await conn.fetch(query, self.symbol)
                
                if records:
                    import pandas as pd
                    df = pd.DataFrame([dict(record) for record in records])
                    return df
                    
        except Exception as e:
            logging.error(f"❌ Failed to retrieve data: {e}")
            
        import pandas as pd
        return pd.DataFrame()
        
    async def close_connections(self):
        await self.feeder.close()
        await self.signal_database.close()

async def main():
    try:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        config_path = os.path.join(PROJECT_ROOT, "config-futures.json")
        config = KISConfig(config_path)
        setup_logging(config.config_dir)

        # (HJ) FEAT: argparse 에 두 가지 타입힌팅 적용하기 위한 객체
        def int_or_float(arg_string):
            try:
                return int(arg_string)
            except ValueError:
                try:
                    return float(arg_string)
                except ValueError:
                    raise argparse.ArgumentTypeError(f"argument must be an integer or a float: '{arg_string}'")

        parser = argparse.ArgumentParser(prog="dolpha1", add_help=True)
        parser.add_argument("--symbol", type=str,  
                            help="symbol(ticker) given by exchange")
        parser.add_argument("--atr_period", type=int, default=10, 
                            help=" - ")
        parser.add_argument("--rolling-move", type=int, default=5, 
                            help=" - ")
        parser.add_argument("--band_multiplier", type=float, default=1.0, 
                            help="multiplier to calculate upper and lower band")
        parser.add_argument("--use-vwap", type=str, choices=["true", "false"], default="true", 
                            help="whether to use vwap to generate signal")
        parser.add_argument("--observe_interval", type=int, default=15, 
                            help="interval to check trading signal and execute order")
        # (HJ) ADJ: 아래 옵션들 추가
        parser.add_argument("--is_real", type=str, choices=["y", "n"], default="y", 
                            help="y: real account, n: paper account")   # (HJ) ADJ: 실제계좌 여부
        parser.add_argument("--order_method", type=str, choices=["market", "limit"], default="market", 
                            help="bid/ask type to submit order to exchange")   # (HJ) ADJ: 매매집행 방식
        parser.add_argument("--leverage_ratio", type=int_or_float, default=1.0, 
                            help="leverage ratio multiplying to trading signal")   # (HJ) ADJ: 레버리지 비율
        # parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO")   # (HJ) TODO: 로그레벨 옵션 추후 구현 (디버깅 위해)

        args = parser.parse_args()
        use_vwap_flag = args.use_vwap.lower() == "true"
        real_flag = True if (args.is_real == 'y') else False
        leverage_ratio = float(args.leverage_ratio) if args.leverage_ratio else 1.0


        print(f"""
═══════════════════════════════════════════
            DOLPHA1 SYSTEM                
                                          
  🎯 Target: {args.symbol}   
  📊 Realtime Data → dolpha1 table        
  🚨 Signal Generation → dolpha1_signal   
                                          
  ⏱️ Current Time: {TimeService.now_kst_naive().strftime('%H:%M:%S'):<15}
  📈 Band Breakout Strategy               
═══════════════════════════════════════════
        """)

        # (HJ) ADJ: 실제계좌 여부 입력 받기
        # is_real_input = input("💰 Execute real trades? (y/n): ").lower().strip()
        # real_flag = True if is_real_input == 'y' else False

        # leverage_ratio_input = input("⬆ How much leverage ratio to use? (default: 1.0): ").lower().strip()
        # leverage_ratio = float(leverage_ratio_input) if leverage_ratio_input else 1.0
        # argparse 로 처리함

        user_input = input("📅 Do you want to collect historical data first? (y/n): ").lower().strip()
        if user_input == 'y':
            days = input("📅 How many days of data to collect? (default: 15): ").strip()
            days_back = int(days) if days.isdigit() else 15
            
            feeder = RealTimeDataFeeder(symbol=args.symbol)
            try:
                await feeder.collect_historical_data(days_back=days_back)
                await feeder.verify_historical_data(days_back=days_back, auto_fix=True)
            except Exception as e:
                print(f"❌ Historical data collection failed: {e}")
                logging.error(f"Historical data collection failed: {e}", exc_info=True)
            finally:
                await feeder.close()
            
            print("━" * 50)
        
        system = Dolpha1Strategy(
            symbol=args.symbol,
            atr_period=args.atr_period,
            rolling_move=args.rolling_move,
            band_multiplier=args.band_multiplier,
            use_vwap=use_vwap_flag,
            observe_interval_minutes=args.observe_interval,
            is_real=real_flag,
            order_method='market', 
            leverage_ratio=leverage_ratio
        )
        
        try:
            logging.info(f"Dolpha1 system monitoring interval: {args.observe_interval} minutes")
            logging.info("💰 Starting dolpha1 system for real trading" if real_flag \
                         else "🧾 Starting dolpha1 system for paper trading")
            logging.info(f"⬆ Using leverage ratio: {leverage_ratio}x")

            await system.initialize()
            
            current_hour_min = TimeService.now_kst_naive().strftime('%H:%M')
            if current_hour_min >= '08:45':
                print("📅 Checking for missing data today...")
                print("━" * 50)
                await system.feeder.collect_today_missing_data()
                print("━" * 50)
            
            print("📡 Starting realtime data feed...")
            print("🔄 Press Ctrl+C to exit")
            print("=" * 50)
            
            await system.start_realtime_feed()
            
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")
        except Exception as e:
            print(f"\n❌ System error: {e}")
            logging.error(f"System error: {e}", exc_info=True)
            raise
        finally:
            await system.close_connections()
            print("👋 System shutdown")
            
    except Exception as e:
        print(f"\n❌ Critical error in main: {e}")
        logging.error(f"Critical error in main: {e}", exc_info=True)
        input("\n⚠️ Press Enter to exit...")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Program terminated")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        print("👋 Goodbye!")