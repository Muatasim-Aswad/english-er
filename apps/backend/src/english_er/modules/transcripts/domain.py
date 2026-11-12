from enum import StrEnum


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewedState(StrEnum):
    REVIEWED = "reviewed"
    UNREVIEWED = "unreviewed"
