from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FundOption:
    key: str
    label: str
    code: str
    matched_from_cmf: str = ""
