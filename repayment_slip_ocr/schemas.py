"""还款/转账凭证信息提取服务的响应模型。

复用 sri_lanka_nic_ocr 项目的 OCR 能力，字段归一化为还款场景统一 schema。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class PartyOut(BaseModel):
    """付款方 / 收款方信息。账号可能脱敏（如 138200******20、****6962）。"""
    name: Optional[str] = None
    account: Optional[str] = None
    account_prefix: Optional[str] = None
    account_last4: Optional[str] = None
    bank: Optional[str] = None


class ReferencesOut(BaseModel):
    """各类交易参考号，不同银行名称不同，统一归入此结构。"""
    transaction_id: Optional[str] = None
    txn_ref: Optional[str] = None
    retrieval_ref: Optional[str] = None
    bank_reference_number: Optional[str] = None
    e_receipt_reference: Optional[str] = None
    my_ref: Optional[str] = None
    receiver_ref: Optional[str] = None
    remarks: Optional[str] = None


class DenominationOut(BaseModel):
    """现金存款凭条的纸币明细（面值 × 张数）。"""
    denomination: float
    quantity: int
    amount: float


class OcrLineOut(BaseModel):
    text: str
    confidence: float
    box: List[List[float]]


class RepaymentResult(BaseModel):
    success: bool
    doc_type: Optional[str] = None      # payment_confirmation | fund_transfer_receipt | cash_deposit_slip | e_receipt
    status: Optional[str] = None        # success | pending | failed
    bank: Optional[str] = None          # 识别到的银行/渠道（peoples_bank | commercial_bank | boc | hnb | ...）
    payer: PartyOut = PartyOut()
    payee: PartyOut = PartyOut()
    amount: Optional[float] = None
    fee: Optional[float] = None
    total_debit: Optional[float] = None
    currency: str = "LKR"
    datetime: Optional[str] = None      # ISO 8601
    references: ReferencesOut = ReferencesOut()
    fields: Dict[str, str] = {}         # 扁平映射：单据原始英文字段名 -> 原文值
    deposit_breakdown: List[DenominationOut] = []
    branch: Optional[str] = None        # 存款凭条网点
    terminal_id: Optional[str] = None   # 存款凭条终端号
    trace_no: Optional[str] = None      # 存款凭条追踪号
    warnings: List[str] = []
    lines: List[OcrLineOut] = []
    elapsed_ms: float = 0.0