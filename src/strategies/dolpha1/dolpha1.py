import asyncio
import argparse
import logging
import warnings
from datetime import datetime
from typing import Any, Dict

import os
import sys

warnings.filterwarnings('ignore', category=UserWarning, module='pandas_market_calendars')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from base import KISConfig, setup_logging
from services.time_service import TimeService
from feeder import RealTimeDataFeeder
from signals import SignalGenerator, SignalDatabase

class Dolpha1Strategy:
    def __init__(
        self,
        symbol: str = "106W12",
        atr_period: int = 10,
        rolling_move: int = 5,
        band_multiplier: float = 1.0,
        use_vwap: bool = True,
        observe_interval_minutes: int = 5,
    ):
        self.symbol = symbol

        config_path = os.path.join(PROJECT_ROOT, "config.json")
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

    async def initialize(self):
        await self.feeder.initialize()
        await self.signal_database.initialize()
        logging.info("🚀 dolpha1 system initialization complete")

    async def start_realtime_feed(self):
        await self.feeder.start_realtime_feed(data_handler=self._on_realtime_data)
        
    async def _on_realtime_data(self, candle_data):
        await self._check_signal()
            
    async def _check_signal(self):
        current_time = TimeService.now_kst_naive()
        current_hour_min = current_time.strftime('%H:%M')
        
        if current_hour_min < '08:45' or current_hour_min >= '15:47':
            logging.debug(f"🕐 Signal check skipped - outside trading hours: {current_hour_min}")
            return
        
        if True:
            
            logging.debug(f"🔍 Checking for signals at {current_time.strftime('%H:%M:%S')}")
            recent_data = await self._get_recent_data()
            
            if len(recent_data) >= 100:
                signal_result = self.signal_generator.get_latest_signal(recent_data)
                
                monitor_signal = signal_result['monitor_signal']
                trade_signal = signal_result['trade_signal'] 
                reason = signal_result['reason']
                ub = signal_result['ub']
                lb = signal_result['lb']
                current_price = signal_result['current_price']
                is_observe_time = signal_result['is_observe_time']
                
                if ub is not None and lb is not None:
                    observe_mark = "🎯" if is_observe_time else "📊"
                    logging.info(f"{observe_mark} Price: {current_price:.2f} | UB: {ub:.2f} | LB: {lb:.2f} | Monitor: {monitor_signal} | Trade: {trade_signal} | {reason}")
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
                    
                    if is_observe_time and trade_signal != 0:
                        logging.info(f"🚨 TRADE SIGNAL! {trade_signal} at {current_price:.2f} - {reason}")
            else:
                logging.warning(f"⚠️ Insufficient data for signal generation: {len(recent_data)}/100")
            
            self.last_signal_time = current_time
            
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
        config_path = os.path.join(PROJECT_ROOT, "config.json")
        config = KISConfig(config_path)
        setup_logging(config.config_dir)

        parser = argparse.ArgumentParser(prog="dolpha1", add_help=True)
        parser.add_argument("--symbol", type=str, default="106W12")
        parser.add_argument("--atr-period", type=int, default=10)
        parser.add_argument("--rolling-move", type=int, default=5)
        parser.add_argument("--band-multiplier", type=float, default=1.0)
        parser.add_argument("--use-vwap", type=str, choices=["true", "false"], default="true")
        parser.add_argument("--observe-interval", type=int, default=5)
        args = parser.parse_args()
        use_vwap_flag = args.use_vwap.lower() == "true"

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
        )
        
        try:
            await system.initialize()
            
            current_time = TimeService.now_kst_naive().strftime('%H:%M')
            if current_time >= '08:45':
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