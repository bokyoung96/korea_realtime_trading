from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from typing import Any, List, Optional
from datetime import datetime

_SRC_DIR = str(Path(__file__).resolve().parents[1])
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from database.config import DatabaseConfig
from database.connection import DatabaseConnection
from read.candles_reader import CandlesReader
from read.option_matrices_reader import OptionMatricesReader
from read.signals_reader import SignalsReader
from services.time_service import TimeService


class Reader:
    def __init__(self, db: DatabaseConnection):
        self._db = db
        self._candles = CandlesReader(db)
        self._matrices = OptionMatricesReader(db)
        self._signals = SignalsReader(db)

    async def initialize(self) -> None:
        if not self._db.pool:
            await self._db.initialize()

    async def close(self) -> None:
        await self._db.close()

    async def read_candles(
        self,
        table: str,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = 100,
    ) -> List[dict[str, Any]]:
        return await self._candles.fetch_range(table, symbol, start, end, limit)

    async def read_option_matrices(
        self,
        underlying_symbol: str,
        metrics: Optional[List[str]] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = 100,
    ) -> List[dict[str, Any]]:
        return await self._matrices.fetch_metrics(underlying_symbol, metrics, start, end, limit)

    async def read_signals(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = 200,
        latest_only: bool = False,
    ) -> List[dict[str, Any]] | dict[str, Any] | None:
        if latest_only:
            return await self._signals.latest(symbol)
        return await self._signals.fetch_range(symbol, start, end, limit)


class ReaderFactory:
    @classmethod
    def from_config(cls, db_config_path: str = "config_db.json") -> Reader:
        db_config = DatabaseConfig.from_json(db_config_path)
        db = DatabaseConnection(db_config)
        return Reader(db)

