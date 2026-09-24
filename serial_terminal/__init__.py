from dataclasses import dataclass, field
import time


@dataclass
class Char:
    code: int       # byte value 0-255
    ts: float = field(default_factory=time.time)
    sent: bool = False
