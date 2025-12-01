# from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Literal, Union


@dataclass
class TradingSignal:
    ticker: str     # e.g. '106W12'
    position: Optional[int]   # {0, 1, -1}    # 자료형이 str 일 경우 {'all', 'long', 'short'}
    volume: Optional[int]     # e.g. 2
    target_price: Optional[float] = None
    message: Optional[str] = None

    target_position: Union[int, Literal['liquidation'], None] = None
    # previous_target_position: int = None
    
    timestamp: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__