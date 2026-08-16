from pydantic import BaseModel


class ClaimStatusCard(BaseModel):
    claim_id: str
    status: str
    amount: float
    date: str


class CoverageSummaryCard(BaseModel):
    plan_name: str
    deductible: float
    copay: float
    covered: bool