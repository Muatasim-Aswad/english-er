from enum import StrEnum
from typing import Literal

from english_er.shared.schema import ContractModel


class DatabaseHealth(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"


class HealthResponse(ContractModel):
    api: Literal["ok"] = "ok"
    database: DatabaseHealth
