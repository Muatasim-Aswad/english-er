from english_er.shared.errors import Code
from english_er.shared.schema import ContractModel


class ValidationIssue(ContractModel):
    location: list[str | int]
    code: str


class ErrorBody(ContractModel):
    status: int
    code: Code
    message: str
    request_id: str
    details: dict[str, str | int] | None = None
    issues: list[ValidationIssue] | None = None


class ErrorResponse(ContractModel):
    error: ErrorBody
