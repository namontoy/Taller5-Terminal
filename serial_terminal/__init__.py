from dataclasses import dataclass, field
import time

# Single source of truth for the app version: shown in About, written to the
# log, and checked against the git tag when a release is pushed (CI).
__version__ = '1.0.0'


@dataclass
class Char:
    code: int       # byte value 0-255
    ts: float = field(default_factory=time.time)
    sent: bool = False
