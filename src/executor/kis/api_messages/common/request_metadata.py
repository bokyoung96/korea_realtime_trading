from dataclasses import dataclass
from typing import Any, Dict, Optional


# KIS API basic information 담는 모델
@dataclass
class RequestMetadata:
    method: str
    url: str
    domain: str
    tr_id: str
    domain_paper: Optional[str] = ''
    tr_id_paper: Optional[str] = ''
    format: Optional[str] = ''
    content_type: Optional[str] = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "url": self.url,
            "domain": self.domain,
            "domain_paper": self.domain_paper,
            "tr_id": self.tr_id,
            "tr_id_paper": self.tr_id_paper,
            "format": self.format,
            "content-type": self.content_type
        }