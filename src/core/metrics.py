from dataclasses import dataclass, field, asdict
import time
from typing import Optional


@dataclass
class CrawlMetrics:
    source_id: str
    source_name: str
    connector: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    discovered: int = 0
    raw_saved: int = 0
    new_upserted: int = 0
    updated: int = 0
    unchanged: int = 0
    closed: int = 0
    failed: bool = False
    error: Optional[str] = None

    def finish(self, failed: bool = False, error: Optional[str] = None) -> "CrawlMetrics":
        self.end_time = time.time()
        self.failed = failed
        self.error = error
        return self

    @property
    def duration_ms(self) -> int:
        if self.end_time is None:
            return int((time.time() - self.start_time) * 1000)
        return int((self.end_time - self.start_time) * 1000)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["duration_ms"] = self.duration_ms
        return data
