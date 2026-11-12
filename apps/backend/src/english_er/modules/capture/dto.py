from english_er.shared.schema import ContractModel


class CaptureState(ContractModel):
    enabled: bool


class CaptureUpdate(ContractModel):
    enabled: bool
