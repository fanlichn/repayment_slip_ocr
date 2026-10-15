"""还款/转账凭证的字段抽取。

从 OCR 行中抽取：单据类型、交易状态、付款方/收款方、金额、手续费、总扣款、
日期时间、各类参考号，以及现金存款凭条的纸币明细。不同银行版式（People's Bank /
Pan Asia Bank / BOC Flex / Commercial Bank）标签措辞不同，故使用多组同义词标签 + 分区
归属（Pay from / Pay to 上下区）来定位字段，识别不到时降级为 null 并写入 warnings。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from .schemas import (
    DenominationOut,
    OcrLineOut,
    PartyOut,
    ReferencesOut,
    RepaymentResult,
)

# ---- 分区锚点：判断某行属于付款方区还是收款方区 ----
# 仅保留明确的「分区标题」，避免与字段行（如 "Sender's Account Number"）混淆；
# Sender / Beneficiary 等方向性字段另用方向性标签与就近定位处理。
_PAYER_SECTION = ["pay from", "payer", "paid using", "paid from", "debit from"]
_PAYEE_SECTION = ["pay to", "payee", "credit to", "credited to"]

# ---- 姓名 ----
_PAYER_NAME_LABELS = [
    "sender's name", "sender name", "account holder name", "card holder name",
    "payer name", "from name", "account name", "from",
]
_PAYEE_NAME_LABELS = [
    "beneficiary name", "beneficiary's name", "receiver name", "payee name",
    "to name", "customer name", "account name",
]

# ---- 账号 ----
_PAYER_ACCOUNT_LABELS = [
    "sender's account", "sender account", "from account", "paid using",
    "account no", "account number", "account",
]
_PAYEE_ACCOUNT_LABELS = [
    "beneficiary account", "beneficiary's account", "to account",
    "credit account", "account no", "account number", "account",
]

# ---- 银行 ----
_PAYER_BANK_LABELS = ["sender's bank", "sender bank", "from bank", "payer bank", "bank"]
_PAYEE_BANK_LABELS = [
    "beneficiary bank", "beneficiary's bank", "to bank", "bank name",
    "payee bank", "bank",
]

# ---- 日期时间 ----
_DATETIME_LABELS = [
    "date & time", "transaction date & time", "transaction date/time",
    "date/time", "date &time", "transaction date", "generated at", "printed on",
]
_DATE_LABELS = ["payment date", "date"]
_TIME_LABELS = ["time"]

# ---- 参考号 ----
_REF_KEYS = [
    ("transaction_id", "transaction id"),
    ("txn_ref", "txn ref"),
    ("txn_ref", "transaction reference"),
    ("retrieval_ref", "retrieval ref"),
    ("bank_reference_number", "bank reference number"),
    ("bank_reference_number", "reference no"),
    ("bank_reference_number", "reference number"),
    ("e_receipt_reference", "e-receipt reference"),
    ("my_ref", "my ref"),
    ("receiver_ref", "receiver ref"),
    ("receiver_ref", "receiver reference"),
    ("remarks", "beneficiary's account narration"),
    ("remarks", "account narration"),
    ("remarks", "remarks"),
    ("remarks", "narration"),
    ("remarks", "description"),
]

_MONTH_SHORT = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_MONEY_RE = re.compile(r"[\d,]+\.\d{1,2}")
_ACCOUNT_RE = re.compile(r"[0-9*Xx]{6,}")

_COMMON_DENOMS = {20, 50, 100, 200, 500, 1000, 2000, 5000, 10000}


def _account_token(s: Optional[str]) -> Optional[str]:
    """从文本提取账号/掩码值（数字、*、X），容忍 "XXXX XXXX 2851" 这类带空格的掩码。"""
    if not s:
        return None
    m = _ACCOUNT_RE.search(re.sub(r"\s+", "", s))
    return m.group(0) if m else None


def _line_center_y(box) -> float:
    ys = [p[1] for p in box]
    return sum(ys) / len(ys)


def _line_center_x(box) -> float:
    xs = [p[0] for p in box]
    return sum(xs) / len(xs)


def _sorted_by_y(lines) -> List:
    return sorted(lines, key=lambda l: _line_center_y(l.box))


def dedup_lines(lines) -> List:
    """按「文本 + 位置」去重 OCR 行。

    多个预处理变体会对同一图像产生近似重复的行（同文本、近似同坐标），需要合并；
    但现金存款凭条的表格里，同文本可能出现在不同单元格 / 不同行（如 NOTES 列多个
    "1"、VALUE 与 AMOUNT 列的 "100.00"），纯文本去重会把它们错误合并成一列。这里用
    (小写文本, y 桶, x 桶) 作为键，既合并变体重复行，又保留不同位置的同文本行。
    """
    dedup: dict = {}
    for ln in lines:
        key = ln.text.strip().lower()
        if not key:
            continue
        pos = (int(_line_center_y(ln.box) // 8), int(_line_center_x(ln.box) // 8))
        k = (key, pos)
        if k not in dedup or ln.confidence > dedup[k].confidence:
            dedup[k] = ln
    return sorted(dedup.values(), key=lambda l: l.confidence, reverse=True)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .:：-[]")


def _parse_money(s: str) -> Optional[float]:
    if not s:
        return None
    # OCR 把币种词 LKR 读成 "1.KR"、"1KR" 等：短数字+点/无点+字母，不是金额
    if re.match(r"^\s*\d{1,2}\.?[A-Za-z]{1,3}\s*$", s):
        return None
    # OCR 常在千分位逗号后插入空格（如 "5, 000.00"），先去掉数字间空格
    s = re.sub(r"(?<=\d)[,\s]+(?=\d)", ",", s)
    s = re.sub(r"(?<=\d)\s+(?=\d)", "", s)
    m = _MONEY_RE.search(s)
    if m:
        # 多个点号说明 OCR 把千分位逗号读成了点（如 "5.000.00"），
        # _MONEY_RE 只匹配到 "5.00"，需用 flexible 解析还原
        if s.count(".") > 1:
            return _parse_flexible_money(s)
        try:
            return float(m.group(0).replace(",", ""))
        except ValueError:
            return None
    # _MONEY_RE 匹配不到（无小数点、或点号混淆），尝试 flexible 解析
    val = _parse_flexible_money(s)
    if val is not None:
        return val
    m = re.search(r"\d[\d,]*", s)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _value_after_label(line_text: str, label: str) -> Optional[str]:
    m = re.search(r"\b" + re.escape(label) + r"\b\s*[:：]?\s*(.+)", line_text, re.IGNORECASE)
    if not m:
        return None
    value = _clean(m.group(1))
    return value or None


def _value_below(idx: int, lines, label_line) -> Optional[str]:
    base_y = _line_center_y(label_line.box)
    base_x = label_line.box[0][0]
    best = None
    for j, other in enumerate(lines):
        if j == idx:
            continue
        y = _line_center_y(other.box)
        x = other.box[0][0]
        if y > base_y + 2 and abs(x - base_x) < 200:
            if best is None or y < best[0]:
                best = (y, other.text.strip())
    return best[1] if best else None


def _value_to_right(idx: int, lines, label_line) -> Optional[str]:
    """左标右值的两栏版式：取与标签行同一水平带、位于其右侧的值行文本。

    用垂直重叠度挑选右侧候选行，避免把相邻标签的值张冠李戴。
    """
    ly0 = min(p[1] for p in label_line.box)
    ly1 = max(p[1] for p in label_line.box)
    label_right_x = max(p[0] for p in label_line.box)
    best = None
    for j, other in enumerate(lines):
        if j == idx:
            continue
        ox0 = min(p[0] for p in other.box)
        oy0 = min(p[1] for p in other.box)
        oy1 = max(p[1] for p in other.box)
        if ox0 < label_right_x - 20:
            continue
        if max(ly0, oy0) >= min(ly1, oy1):
            continue  # 无垂直重叠
        overlap = min(ly1, oy1) - max(ly0, oy0)
        if best is None or overlap > best[0]:
            best = (overlap, other.text)
    return _clean(best[1]) if best else None


def _right_column_value(idx: int, lines, label_line, max_vy: float = 170.0) -> Optional[str]:
    """左标右值两栏版式：取标签行右侧（可略偏下）最近的一条右列值行文本。

    部分电子回单的值比标签略低（如 BOC "Other Charges" 的值在标签下一行），严格按
    垂直重叠会取空，这里用「在标签右侧 + 垂直方向不高于 max_vy」的宽松窗口兜底。
    """
    ly = _line_center_y(label_line.box)
    rx = max(p[0] for p in label_line.box)
    best = None
    for j, other in enumerate(lines):
        if j == idx:
            continue
        ox = min(p[0] for p in other.box)
        oy = _line_center_y(other.box)
        if ox < rx - 15:
            continue
        if oy < ly - 5 or oy - ly > max_vy:
            continue
        if best is None or oy < best[0]:
            best = (oy, other.text)
    return _clean(best[1]) if best else None


def _money_near_label_right(lines, label_line, max_dy: float = 260.0) -> Optional[float]:
    """取标签右侧（含上下偏移）最近的一条含金额的行，跳过纯货币词 "LKR"。

    用于 "DEPOSIT AMOUNT:" 这类标签与值不在同一水平带的凭条：值可能出现在标签
    右上方（如 Commercial Bank CDM），中间还夹杂 "LKR" 币种词。
    """
    ly = _line_center_y(label_line.box)
    rx = max(p[0] for p in label_line.box) - 15
    best = None
    for other in lines:
        if other is label_line:
            continue
        ox = min(p[0] for p in other.box)
        oy = _line_center_y(other.box)
        if ox < rx:
            continue
        dy = abs(oy - ly)
        if dy > max_dy:
            continue
        val = _parse_money(other.text)
        if val is None:
            continue
        # 存款金额通常 ≥ 100，< 100 的纯整数多半是 OCR 噪声
        # （如 "000008" 由 "8,000.00" 读坏而来），跳过
        if val < 100 and val == int(val):
            continue
        if best is None or dy < best[0]:
            best = (dy, val)
    return best[1] if best else None


def _right_column_for(ordered, label_texts) -> Optional[str]:
    """在有序行里找标签独占一行（精确匹配）后取右列值。"""
    wanted = {t.lower().strip(":：. ") for t in label_texts}
    for i, ln in enumerate(ordered):
        t = ln.text.strip().strip(":：. ").lower()
        if t not in wanted:
            continue
        v = _right_column_value(i, ordered, ln)
        if v and not _looks_like_label_text(v):
            return v
    return None


def _match_label_value(lines, labels) -> Optional[str]:
    """按标签（同名多词）定位取值，支持行内值、右侧两栏值与下一行取值。"""
    ordered = _sorted_by_y(lines)
    for ln in ordered:
        for lbl in labels:
            if lbl == "name":
                continue  # 通用 name 用专门的 _match_name 处理，避免 "bank name" 干扰
            value = _value_after_label(ln.text, lbl)
            if value and not _looks_like_label_text(value):
                return value
    # 标签单独一行 -> 先右侧两栏（电子回单），再正下方（纸质上下版式）
    for i, ln in enumerate(ordered):
        t = ln.text.strip().strip(":：. ").lower()
        for lbl in labels:
            if t == lbl.lower():
                side = _value_to_right(i, ordered, ln)
                if side and not _looks_like_label_text(side):
                    return side
                below = _value_below(i, ordered, ln)
                if below and not _looks_like_label_text(below):
                    return below
    return None


_FIELD_WORDS = {
    "no", "no.", "name", "number", "bank", "ref", "reference", "amount",
    "date", "time", "currency", "narration", "status", "account", "code",
    "terminal", "id", "trace", "branch", "mobile", "source", "funds",
    "notes", "value", "customer", "transaction",
}


def _is_transaction_type(low: str) -> bool:
    """判断是否为交易类型描述（如 'cardless deposit'、'cash withdrawal'）。

    这类行不是金额标签，其右侧/下方的值不属于金额，提取主金额时需跳过，
    避免把交易类型后面的无关文本（甚至收据外的噪点）误解析为金额。
    """
    return any(k in low for k in ("cardless", "withdrawal", "transfer", "cheque", "cash "))


def _looks_like_label_text(value: str) -> bool:
    """某些标签后紧跟的其实是另一个标签（如账户行 "Account No 138200..." 里
    "account" 匹配后得到 "no 138200..."）。此处用于剔除明显是标签残留的取值。"""
    low = value.lower()
    words = [w for w in re.split(r"[\s:：.\-]+", low) if w]
    if not words:
        return True
    if all(w in _FIELD_WORDS for w in words):
        return True  # 整值只由字段词组成，如 "Reference Number"
    for token in ("no", "no.", "name", "number", "bank", "ref", "amount", "date"):
        if low == token or low.startswith(token + " "):
            rest = low[len(token):].strip(" .:：")
            if not rest:
                return True
    return False


def _match_name(zone_lines, directional_labels) -> Optional[str]:
    """姓名：先用方向性标签（sender's name / beneficiary name ...），
    再用行首的通用 "Name" 兜底（分区已区分付款/收款，避免歧义）。"""
    v = _match_label_value(zone_lines, directional_labels)
    if v:
        return _clean(v)
    ordered = _sorted_by_y(zone_lines)
    for ln in ordered:
        m = re.match(r"^\s*name\b\s*[:：]?\s*(.+)", ln.text, re.IGNORECASE)
        if m:
            v = _clean(m.group(1))
            if v and not re.match(r"^\d", v):
                return v
    # 标签独占一行 -> 右侧两栏 / 正下方取值（People's Pay 等左标右值版式）
    for i, ln in enumerate(ordered):
        if ln.text.strip().strip(":：. ").lower() != "name":
            continue
        side = _value_to_right(i, ordered, ln)
        if side and not _looks_like_label_text(side) and not re.match(r"^\d", side):
            return side
        below = _value_below(i, ordered, ln)
        if below and not _looks_like_label_text(below) and not re.match(r"^\d", below):
            return below
    return None


def _extract_account(zone_lines, labels) -> Optional[str]:
    """在区域内用账号标签找第一个能提取出数字/掩码的行。

    要求真正的账号数字（至少 6 位数字/星号），避免把 "Account Currency" /
    "Account Name" 这些仅含 "account" 关键词的行误当成账号。
    """
    ordered = _sorted_by_y(zone_lines)
    for ln in ordered:
        for lbl in labels:
            value = _value_after_label(ln.text, lbl)
            if value:
                tok = _account_token(value)
                if tok:
                    return tok
    # 标签独占一行 -> 右侧两栏 / 正下方取值
    for i, ln in enumerate(ordered):
        t = ln.text.strip().strip(":：. ").lower()
        for lbl in labels:
            if t == lbl.lower():
                side = _value_to_right(i, ordered, ln)
                if side:
                    tok = _account_token(side)
                    if tok:
                        return tok
                below = _value_below(i, ordered, ln)
                if below:
                    tok = _account_token(below)
                    if tok:
                        return tok
    return None


def _derive_account_parts(account: Optional[str]):
    if not account:
        return None, None
    prefix = None
    last4 = None
    digits = re.sub(r"[^0-9]", "", account)
    if len(digits) >= 4:
        last4 = digits[-4:]
        prefix = digits[:4] if len(digits) >= 8 else None
    return prefix, last4


def _split_zones(lines):
    """按 Pay from / Pay to 分区锚点把行分成付款方区与收款方区。

    返回 (payer_zone, payee_zone, has_anchor)。无任何锚点时两区为空，
    调用方改用方向性标签在全部行上匹配。
    """
    payer_y = None
    payee_y = None
    for ln in lines:
        t = ln.text.strip().lower()
        if payer_y is None:
            for lbl in _PAYER_SECTION:
                if lbl in t:
                    payer_y = _line_center_y(ln.box)
                    break
        if payee_y is None:
            for lbl in _PAYEE_SECTION:
                if lbl in t:
                    payee_y = _line_center_y(ln.box)
                    break

    payer_zone: List = []
    payee_zone: List = []
    has_anchor = payer_y is not None or payee_y is not None
    if not has_anchor:
        return payer_zone, payee_zone, False

    for ln in lines:
        y = _line_center_y(ln.box)
        if payee_y is not None and y > payee_y:
            payee_zone.append(ln)
        elif payer_y is not None and y > payer_y and (payee_y is None or y < payee_y):
            payer_zone.append(ln)
        elif payee_y is not None and payer_y is None and y < payee_y:
            payer_zone.append(ln)
    return payer_zone, payee_zone, True


def _find_name_anchor(lines, labels):
    """返回第一个含方向性姓名标签的行，供无分区时就近定位账号。

    纯标签行（如两栏里的 "Sender's Name"）本身取不到值，但仍是有效锚点，
    故按标签子串匹配即可。
    """
    for ln in _sorted_by_y(lines):
        t = ln.text.strip().strip(":：. ").lower()
        for lbl in labels:
            if lbl == "name":
                continue
            if lbl in t:
                return ln
    return None


def _account_from_line(text: str) -> Optional[str]:
    """从单行文本提取账号值（数字或掩码）。"""
    for lbl in ("account number", "account no", "account"):
        value = _value_after_label(text, lbl)
        if value:
            tok = _account_token(value)
            if tok:
                return tok
    return None


def _account_near(lines, anchor_line) -> Optional[str]:
    """无分区场景下，取距离姓名锚点行最近的账号标签行。

    账号值可能在标签同行（"Account No 138200..."），也可能在右侧两栏
    （左 "Account Number" / 右 "138200..."）。
    """
    if anchor_line is None:
        return None
    ay = _line_center_y(anchor_line.box)
    best = None
    for idx, ln in enumerate(lines):
        if ln is anchor_line:
            continue
        low = ln.text.lower()
        if "account" not in low and "a/c" not in low:
            continue
        value = _account_from_line(ln.text)
        if not value:
            side = _value_to_right(idx, lines, ln)
            if side:
                value = _account_token(side)
        if not value:
            continue
        gap = abs(_line_center_y(ln.box) - ay)
        if best is None or gap < best[0]:
            best = (gap, value)
    return best[1] if best else None


def _extract_parties(lines, bank: Optional[str] = None) -> tuple[PartyOut, PartyOut]:
    if bank == "peoples_bank":
        return _extract_peoples_bank_parties(lines)
    if _is_boc_app(lines):
        return _extract_boc_app_parties(lines)
    if _is_cash_deposit(lines):
        return _extract_cdm_parties(lines)
    if _is_cash_credit_slip(lines):
        return _extract_cash_credit_slip_parties(lines)
    if _is_hnb_app_receipt(lines):
        return _extract_hnb_app_parties(lines)
    if _is_to_only_receipt(lines):
        return _extract_to_only_parties(lines)

    payer, payee = PartyOut(), PartyOut()
    payer_zone, payee_zone, has_anchor = _split_zones(lines)

    payer_name_anchor = _find_name_anchor(lines, _PAYER_NAME_LABELS)
    payee_name_anchor = _find_name_anchor(lines, _PAYEE_NAME_LABELS)

    # 分区非空时在分区内匹配，否则退回全卡
    payer.name = _match_name(payer_zone or lines, _PAYER_NAME_LABELS)
    payee.name = _match_name(payee_zone or lines, _PAYEE_NAME_LABELS)

    if has_anchor:
        payer.account = _extract_account(payer_zone, _PAYER_ACCOUNT_LABELS) or _account_near(lines, payer_name_anchor)
        payee.account = _extract_account(payee_zone, _PAYEE_ACCOUNT_LABELS) or _account_near(lines, payee_name_anchor)
        payer.bank = _match_label_value(payer_zone, _PAYER_BANK_LABELS)
        payee.bank = _match_label_value(payee_zone, _PAYEE_BANK_LABELS)
    else:
        # 方向性账户标签优先，其次按姓名锚点就近定位（如 BOC 两个 "Account Number"）
        payer.account = _extract_account(lines, _PAYER_ACCOUNT_LABELS[:4]) or _account_near(lines, payer_name_anchor)
        payee.account = _extract_account(lines, _PAYEE_ACCOUNT_LABELS[:4]) or _account_near(lines, payee_name_anchor)
        payer.bank = _match_label_value(lines, _PAYER_BANK_LABELS)
        payee.bank = _match_label_value(lines, _PAYEE_BANK_LABELS)

    payer.account_prefix, payer.account_last4 = _derive_account_parts(payer.account)
    payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)

    # 宽泛的 "bank" 标签可能误取银行页脚地址（如 e-Receipt 底部的抬头声明），
    # 这类值不含交易对手银行信息，直接丢弃。
    if _is_address_like(payer.bank):
        payer.bank = None
    if _is_address_like(payee.bank):
        payee.bank = None
    return payer, payee


def _is_address_like(value: Optional[str]) -> bool:
    if not value:
        return False
    low = value.lower()
    if len(value) > 60:
        return True
    for tok in ("colombo", "mawatha", "street", "road", "p.o.", "tel", "bristol"):
        if tok in low:
            return True
    return False


_DENOM_LABEL_RE = re.compile(r"^\s*\d{2,5}\s*[xX]\b")


def _is_denomination_label_line(text: str) -> bool:
    """判断是否为现金存款凭条的面额标签行（如 "5000 X"、"2000 X"）。

    这类行含数字但不是交易金额，提取主金额时需跳过，避免把 5000 当成存款金额。
    """
    return bool(_DENOM_LABEL_RE.match(text.strip()))


def _parse_money_skip_denom(text: str) -> Optional[float]:
    """解析金额，但如果整行是面额标签行则返回 None。"""
    if _is_denomination_label_line(text):
        return None
    return _parse_money(text)


def _extract_amounts(lines) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """返回 (amount, fee, total_debit)。

    金额行通常只有一个数字，按行内子串特征（fee/charge、total、amount/deposit）
    分类提取，避免 "total debit amount" 里的 "amount" 把总额误判为主金额。
    现金存款凭条的面额标签行（"5000 X" 等）会被跳过，防止把面额当成交易金额。
    """
    if _is_cash_credit_slip(lines):
        # Paper forms contain numbered labels and handwritten currency cells,
        # not the label/value layout used by electronic receipts.
        amount = _find_credit_slip_printed_amount(lines)
        if amount is None:
            amount = _find_deposit_total_from_table(lines)
        return amount, None, amount

    fee = None
    total = None
    amount = None
    ordered0 = _sorted_by_y(lines)
    # 先扫 "amount charged"（PayMaster 扣款总额），优先级高于 subtotal/total
    for i, ln in enumerate(ordered0):
        low = ln.text.lower()
        if "amount charged" in low:
            total = _parse_money(ln.text)
            if total is None:
                side = _value_to_right(i, ordered0, ln)
                if not side:
                    side = _right_column_value(i, ordered0, ln)
                if side:
                    total = _parse_money(side)
    for i, ln in enumerate(ordered0):
        low = ln.text.lower()
        # "amount charged" 是扣款总额（如 PayMaster），不是手续费；subtotal 不是总额
        is_amount_charged = "amount charged" in low
        if fee is None and ("fee" in low or "charges" in low) and not is_amount_charged:
            fee = _parse_money(ln.text)
            if fee is None:
                side = _value_to_right(i, ordered0, ln)
                if not side:
                    side = _right_column_value(i, ordered0, ln)
                if side:
                    fee = _parse_money(side)
        if total is None and "total" in low and "subtotal" not in low:
            total = _parse_money(ln.text)
            if total is None:
                side = _value_to_right(i, ordered0, ln)
                if not side:
                    side = _right_column_value(i, ordered0, ln)
                if side:
                    total = _parse_money(side)

    ordered = _sorted_by_y(lines)
    for i, ln in enumerate(ordered):
        low = ln.text.lower()
        # "subtotal" 是本金（如 PayMaster），不是 total，不跳过
        is_subtotal = "subtotal" in low
        if ("total" in low and not is_subtotal) or "fee" in low or "charge" in low:
            continue
        if "amount" in low or "deposit" in low or is_subtotal:
            # 跳过纯表头行（如 "NOTES VALUE AMOUNT"），避免误取右侧/下方的错误值
            if _looks_like_label_text(ln.text):
                continue
            amount = _parse_money_skip_denom(ln.text)
            # OCR 常把标签读坏产生小整数噪声（如 "JF11jS11 AMOUNT" → 11），
            # 含 amount/deposit 的行解析出 < 100 的纯整数通常是噪声，跳过
            if amount is not None and amount < 100 and amount == int(amount):
                amount = None
            if amount is None:
                # 交易类型描述行（如 "CARDLESS DEPOSIT"）不是金额标签，
                # 其右侧/下方的值不属于金额，跳过避免误取（如把收据外的 "13" 当金额）
                if "amount" not in low and _is_transaction_type(low):
                    continue
                side = _value_to_right(i, ordered, ln)
                if side and not _is_denomination_label_line(side):
                    amount = _parse_money(side)
                    if amount is not None and amount < 100 and amount == int(amount):
                        amount = None
            if amount is None:
                side = _right_column_value(i, ordered, ln)
                if side and not _is_denomination_label_line(side):
                    amount = _parse_money(side)
                    if amount is not None and amount < 100 and amount == int(amount):
                        amount = None
            if amount is None and "deposit amount" in low:
                amount = _money_near_label_right(ordered, ln)
            if amount is not None:
                break

    # 头部无标签金额行（如 "LKR 37,800.00"）
    if amount is None:
        for ln in _sorted_by_y(lines):
            low = ln.text.lower()
            if ("lkr" in low or "rs." in low or low.startswith("rs")) and "total" not in low and "fee" not in low:
                amount = _parse_money_skip_denom(ln.text)
                if amount is not None:
                    break

    # 现金存款：TOTAL 行即存款总额，优先采用（面额表的 TOTAL 比散点金额更可靠）
    if amount is None and total is not None:
        amount = total
    # 现金存款（CDM）无 TOTAL 行，DEPOSIT AMOUNT 即总额。
    # 注意：若已识别到 fee（转账收据），不应把 total 设为 amount，
    # 否则 amount+fee != total 会产生误报。
    if total is None and amount is not None and fee is None:
        low_all = "\n".join(ln.text.lower() for ln in lines)
        if "deposit" in low_all or "cardless" in low_all:
            total = amount
    return amount, fee, total


def _is_app_loan_page(full_text: str) -> bool:
    """检测是否为还款 App 的非凭证页面（如「发起还款」「上传截图」页）。

    这类页面包含 loan amount / due date / upload / repayment screenshot /
    camera / album / cancel 等 App UI 词，不是银行交易凭证。
    """
    t = full_text.lower()
    app_indicators = ["loan amount", "due date", "upload repayment",
                      "repayment screenshot", "total amount"]
    app_picker = ("camera" in t and "album" in t and "cancel" in t)
    hit = sum(1 for w in app_indicators if w in t)
    return hit >= 2 or app_picker


def _detect_doc_type(full_text: str) -> Optional[str]:
    t = full_text.lower()
    if _is_app_loan_page(full_text):
        return "unknown"
    if "deposit" in t or "cardless" in t:
        return "cash_deposit_slip"
    if "e-receipt" in t:
        return "e_receipt"
    if "confirmation" in t or "payment details" in t:
        return "payment_confirmation"
    if "receipt" in t or "transfer" in t or "payment" in t:
        return "fund_transfer_receipt"
    return "unknown"


def _detect_status(full_text: str) -> Optional[str]:
    t = full_text.lower()
    if "successful" in t or " successfully " in t or "completed" in t or "success" in t:
        return "success"
    if "failed" in t or "declined" in t or "unsuccessful" in t:
        return "failed"
    if "pending" in t:
        return "pending"
    return None


def _parse_datetime(s: str) -> Optional[str]:
    if not s:
        return None
    s = re.sub(r"\s+", " ", s.strip())
    s = re.sub(r"(?i)\b(am|pm)\b", lambda m: m.group(1).upper(), s)
    # 时间点号： "1.43 PM" / "1.43PM" -> "1:43 PM"
    s = re.sub(r"(?i)(\d{1,2})\.(\d{2})\s*(am|pm)", r"\1:\2 \3", s)
    # 归一化：日期分隔符 "." 统一为 "/"，去掉日期与时间之间的逗号，补偿
    # "10.08.2026 , 06:45 PM" / "10.08.202606:45PM" 这类带逗号或无空格写法。
    s = s.replace(".", "/")
    s = re.sub(r"\s*,\s*", " ", s)
    s = re.sub(r"(?i)(\d{2,4})(\d{1,2}:\d{2})", r"\1 \2", s)
    # 日期与时间以冒号粘连且为 12 小时制（如 "2026:1:43 PM"）拆开；
    # 仅限 AM/PM 后缀，避免误拆 24 小时制 "08:08:32"。
    s = re.sub(r"(?i)(\d{2,4})\s*:\s*(\d{1,2}:\d{2}\s*(?:am|pm))", r"\1 \2", s)
    s = re.sub(r"(?i)(\d{1,2}:\d{2})(am|pm)", r"\1 \2", s)
    s = re.sub(r"\s+", " ", s).strip()
    formats = [
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %I:%M:%S %p",
        "%d-%m-%Y %I:%M:%S %p",
        "%d/%m/%Y %I:%M %p",
        "%d-%m-%Y %I:%M %p",
        "%d %b %Y %I:%M %p",
        "%d %b %Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d/%m/%y %H:%M",
        "%d-%m-%y %H:%M",
        "%d/%m/%y %H:%M:%S",
        "%d-%m-%y %H:%M:%S",
        "%Y/%m/%d",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt).isoformat()
        except ValueError:
            continue
    return None


def _find_datetime(lines) -> Optional[str]:
    if _is_cash_credit_slip(lines):
        # Machine print can lose all date separators and the separator before
        # seconds: "2026100909:2416" means 2026-10-09 09:24:16.
        compact_pattern = re.compile(
            r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])([0-2]\d|3[01])"
            r"([01]\d|2[0-3]):([0-5]\d)([0-5]\d)(?!\d)"
        )
        for ln in lines:
            match = compact_pattern.search(ln.text)
            if match:
                try:
                    return datetime(
                        int(match.group(1)),
                        int(match.group(2)),
                        int(match.group(3)),
                        int(match.group(4)),
                        int(match.group(5)),
                        int(match.group(6)),
                    ).isoformat()
                except ValueError:
                    pass
        printed = [
            ln for ln in lines
            if re.search(r"\d{1,2}:\d{2}", ln.text)
            and re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", ln.text)
        ]
        for ln in _sorted_by_y(printed):
            match = re.search(
                r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?",
                ln.text,
            )
            if match:
                parsed = _parse_datetime(match.group(0))
                if parsed:
                    return parsed
    dt_text = _match_label_value(lines, _DATETIME_LABELS)
    if dt_text:
        parsed = _parse_datetime(dt_text)
        if parsed:
            return parsed

    # 全卡扫描带时间的完整日期时间（优先于纯日期，避免误取 Payment Date 的无时间值）
    datetime_pats = [
        r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s*[,\s]?\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?",
        r"\d{4}[/-]\d{1,2}[/-]\d{1,2}[ T]\s*\d{1,2}:\d{2}(?::\d{2})?",
        r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?",
        r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?",
    ]
    for ln in lines:
        for pat in datetime_pats:
            m = re.search(pat, ln.text, re.IGNORECASE)
            if m:
                parsed = _parse_datetime(m.group(0))
                if parsed:
                    return parsed

    # 日期与时间分行（如纸质凭条 DATE 07/10/26 / TIME 18:12）
    d = _match_label_value(lines, _DATE_LABELS)
    t = _match_label_value(lines, _TIME_LABELS)
    # 校验时间值必须是 HH:MM 格式，否则可能误取了日期/其他值
    if t and not re.match(r"^\s*([01]?\d|2[0-3]):[0-5]\d\s*$", t):
        t = None
    # 兜底：OCR 把 TIME 标签和值拆成两行，扫描全卡找 HH:MM 时间
    if not t:
        for ln in lines:
            tm = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", ln.text)
            if tm and not re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", ln.text):
                t = tm.group(0)
                break
    if d:
        combined = _parse_datetime(f"{d} {t}" if t else d)
        if combined:
            return combined
        # d 可能是 OCR 损坏值（如 "2509/26"），尝试从全卡找有效日期与 t 组合
        if t:
            for ln in lines:
                dm = re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", ln.text)
                if dm:
                    combined = _parse_datetime(f"{dm.group(0)} {t}")
                    if combined:
                        return combined

    # 兜底：纯日期
    for ln in lines:
        m = re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", ln.text)
        if m:
            parsed = _parse_datetime(m.group(0))
            if parsed:
                return parsed
    return None


_REMARKS_LABELS = [
    "beneficiary's account narration", "account narration", "remarks",
    "narration", "description", "reference/remarks",
]
_REMARKS_LABEL_SET = set(_REMARKS_LABELS)


def _looks_like_remarks_hint(value: str) -> bool:
    """某些回执把备注占位写成 "Remarks - Max N characters"，需当作标签残留而非值。"""
    v = value.lower().strip(" .:：-–")
    return bool(re.fullmatch(r"max\s*\d+\s*(characters?|chars?)\b.*", v))


def _extract_remarks(lines) -> Optional[str]:
    """提取备注/附言，兼容三种版式：标签+值同行、左标右值、标签在上值在下。"""
    ordered = _sorted_by_y(lines)
    for ln in ordered:
        core = re.sub(r"(?i)\s*[-–]\s*max\s*\d+\s*(characters?|chars?)\b.*$", "", ln.text)
        for lbl in _REMARKS_LABELS:
            value = _value_after_label(core, lbl)
            if value and not _looks_like_remarks_hint(value):
                return value
    for i, ln in enumerate(ordered):
        t = ln.text.strip().strip(":：. ").lower()
        if not (t.startswith("remark") or t in _REMARKS_LABEL_SET):
            continue
        side = _value_to_right(i, ordered, ln)
        if side and not _looks_like_remarks_hint(side) and not _looks_like_label_text(side):
            return side
        below = _value_below(i, ordered, ln)
        if below and not _looks_like_remarks_hint(below) and not _looks_like_label_text(below):
            return below
    return None


def _extract_references(lines) -> ReferencesOut:
    refs = ReferencesOut()
    values = {}
    for field, label in _REF_KEYS:
        if field in values and values[field]:
            continue
        if field == "remarks":
            continue  # 备注单独走 _extract_remarks，避免占位提醒干扰
        v = _match_label_value(lines, [label])
        if v:
            values[field] = v
    refs.transaction_id = values.get("transaction_id")
    refs.txn_ref = values.get("txn_ref")
    refs.retrieval_ref = values.get("retrieval_ref")
    refs.bank_reference_number = values.get("bank_reference_number")
    refs.e_receipt_reference = values.get("e_receipt_reference")
    refs.my_ref = values.get("my_ref")
    refs.receiver_ref = values.get("receiver_ref")
    refs.remarks = _extract_remarks(lines)

    # 无标签的独立参考号（如 BOC "UFT7304438337322"）：字母前缀 + 长数字的单行
    if not refs.transaction_id:
        for ln in _sorted_by_y(lines):
            t = ln.text.strip()
            if re.fullmatch(r"[A-Za-z]{2,5}\d{9,}", t):
                refs.transaction_id = t
                break
    return refs


def _find_deposit_breakdown(lines, total_amount: Optional[float] = None) -> List[DenominationOut]:
    """现金存款凭条：识别纸币明细。

    兼容三种版式：
    * CDM 三栏式（Commercial Bank CDM）：NOTES(张数) / VALUE(面额) / AMOUNT(金额)；
    * 纸质凭条三栏式（Commercial Bank CASH CREDIT SLIP）：NOTES(面额标签) / RS.(张数) / CTS(金额)；
    * 单行式（旧版 "面值 张数 金额" 同行）作为兜底。
    """
    if _is_cash_credit_slip(lines):
        return _breakdown_from_credit_slip_columns(lines, total_amount)
    cols = _breakdown_from_columns(lines, total_amount)
    if cols:
        return cols
    credit = _breakdown_from_credit_slip_columns(lines, total_amount)
    if credit:
        return credit
    return _breakdown_single_line(lines)


def _parse_denomination(s: str) -> Optional[float]:
    """解析纸币面额（VALUE 列），容忍 OCR 千分位分隔符的混合写法。

    收据面额恒为整数元（100/1000/5000 等），末尾两位 ".00" 为分。把数字按分隔符
    切成分组、末组 "00" 视为分，其余拼接成整数，从而正确还原
    "LKR 5, 000. 00" / "LKR5.000.00" -> 5000、"LKR 1,000.00" -> 1000。

    OCR 严重损坏的行（如 "LKR 5 0OU OO"，含字母 OU）会误解析为 50，
    因此去掉币种词后仍含字母的行直接返回 None。
    但部分字母是数字的常见 OCR 误读（Q/O→0、I/l→1、Z→2、S→5、B→8），
    先还原再判断。
    """
    s = re.sub(r"(?i)lkr", "", s).strip()
    s = re.sub(r"(?i)\brs\.?", "", s).strip()
    # OCR 常见数字→字母误读还原（仅在还原后无字母时才使用）
    restored = s.translate(str.maketrans({"Q": "0", "q": "0", "O": "0", "o": "0",
                                          "I": "1", "l": "1", "Z": "2", "z": "2",
                                          "S": "5", "s": "5", "B": "8", "b": "8"}))
    if re.search(r"[a-zA-Z]", restored):
        return None
    s = restored
    groups = re.findall(r"\d+", s)
    if not groups:
        return None
    if len(groups) >= 2 and groups[-1] == "00":
        integer = "".join(groups[:-1])
    else:
        integer = "".join(groups)
    if not integer:
        return None
    val = float(int(integer))
    # OCR 可能丢了小数点导致面额放大 10/100/1000 倍（如 "5.00000" → 500000），
    # 尝试缩小到常见面额
    if val not in _COMMON_DENOMS:
        for div in (10, 100, 1000):
            if val / div in _COMMON_DENOMS:
                return val / div
    return val


def _breakdown_from_columns(lines, total_amount: Optional[float]) -> List[DenominationOut]:
    """三栏式 NOTES/VALUE/AMOUNT 布局：按表头 x 分列，各列按 y 排序后逐行配对。"""
    ordered = _sorted_by_y(lines)
    headers: dict = {}
    for ln in ordered:
        t = ln.text.strip().lower().rstrip(":.")
        if t in ("notes", "value", "amount") and t not in headers:
            headers[t] = (ln, _line_center_x(ln.box), _line_center_y(ln.box))
    if not ("notes" in headers and "value" in headers and "amount" in headers):
        return []
    notes_cx = headers["notes"][1]
    value_cx = headers["value"][1]
    amount_cx = headers["amount"][1]
    if not (notes_cx < value_cx < amount_cx):
        return []
    b1 = (notes_cx + value_cx) / 2
    b2 = (value_cx + amount_cx) / 2
    header_y = min(headers[k][2] for k in headers)

    qty_rows: List[tuple] = []
    denom_rows: List[tuple] = []
    amount_rows: List[tuple] = []
    for ln in ordered:
        y = _line_center_y(ln.box)
        if y <= header_y + 2:
            continue
        t = ln.text.strip().lower().rstrip(":.")
        if t in ("notes", "value", "amount") or "deposit amount" in t:
            continue
        cx = _line_center_x(ln.box)
        text = ln.text.strip()
        if cx < b1:
            m = re.fullmatch(r"\d{1,3}", text)
            if m:
                qty_rows.append((y, int(m.group(0)), ln.confidence))
        elif cx < b2:
            val = _parse_denomination(text)
            if val is not None and val in _COMMON_DENOMS:
                denom_rows.append((y, val))
        else:
            val = _parse_denomination(text)
            if val is not None:
                amount_rows.append((y, val))

    if not denom_rows:
        return []
    qty_rows.sort()
    # 数量去重：OCR 常把同一数量识别成多个变体（如 "8" / "18"），
    # 同一 y 行只保留置信度最高的一个，避免与面额行按索引配对时错位
    unique_qty: List[tuple] = []
    for y, qty, conf in qty_rows:
        if unique_qty and abs(y - unique_qty[-1][0]) < 15:
            if conf > unique_qty[-1][2]:
                unique_qty[-1] = (y, qty, conf)
        else:
            unique_qty.append((y, qty, conf))
    qty_rows = [(y, qty) for y, qty, _ in unique_qty]
    denom_rows.sort()
    amount_rows.sort()
    if total_amount is not None:
        amount_rows = [(y, m) for y, m in amount_rows if abs(m - total_amount) > 0.01]

    # 面额去重：OCR 常把同一面额识别成 "100.00" / "100. 00" 等多个变体行
    seen_denoms = set()
    unique_denoms = []
    for y, denom in denom_rows:
        if denom in seen_denoms:
            continue
        seen_denoms.add(denom)
        unique_denoms.append((y, denom))
    denom_rows = unique_denoms

    breakdown: List[DenominationOut] = []
    for i, (_, denom) in enumerate(denom_rows):
        qty = qty_rows[i][1] if i < len(qty_rows) else 1
        amount = denom * qty
        for _, amt in amount_rows:
            if abs(amt - denom * qty) < 0.05:
                amount = amt
                break
        breakdown.append(DenominationOut(denomination=denom, quantity=qty, amount=amount))
    return breakdown


def _breakdown_from_credit_slip_columns(lines, total_amount: Optional[float]) -> List[DenominationOut]:
    """Paper form: NOTES is denomination; RS./CTS are rupees/cents."""
    ordered = _sorted_by_y(lines)
    breakdown: List[DenominationOut] = []
    seen = set()
    for ln in ordered:
        match = re.fullmatch(r"\s*(\d{2,5})\s*[xX]\s*", ln.text)
        if not match:
            continue
        denom = float(match.group(1))
        if denom not in _COMMON_DENOMS or denom in seen:
            continue
        amount = _credit_slip_row_amount(ordered, ln)
        if amount is None or amount <= 0:
            continue
        qty = round(amount / denom)
        if qty <= 0 or abs(amount - denom * qty) > 0.02:
            continue
        seen.add(denom)
        breakdown.append(DenominationOut(denomination=denom, quantity=qty, amount=amount))
    return breakdown


def _credit_slip_row_amount(lines, label_line) -> Optional[float]:
    """Read only overlapping currency cells, never a nearby row or signature."""
    rs = [ln for ln in lines if ln.text.strip().lower().rstrip(".:") == "rs"]
    if not rs:
        return None
    rs_x = _line_center_x(rs[0].box)
    cts = [ln for ln in lines if ln.text.strip().lower().rstrip(".:") in ("cts", "ct")]
    boundary = (rs_x + _line_center_x(cts[0].box)) / 2 if cts else None
    ly0 = min(p[1] for p in label_line.box)
    ly1 = max(p[1] for p in label_line.box)
    cells = []
    for ln in lines:
        if ln is label_line:
            continue
        x = min(p[0] for p in ln.box)
        y0, y1 = min(p[1] for p in ln.box), max(p[1] for p in ln.box)
        if x < max(p[0] for p in label_line.box) or max(y0, ly0) >= min(y1, ly1):
            continue
        text = ln.text.strip()
        val = _parse_flexible_money(text)
        if val is not None and val >= 0:
            cells.append((x, _line_center_x(ln.box), val))
    rupees = sorted(cell for cell in cells if boundary is None or cell[1] < boundary)
    if not rupees:
        return None
    if len(rupees) != 1:
        return None
    value = rupees[0][2]
    if value == 0 and boundary is not None:
        cents = [cell for cell in cells if cell[1] >= boundary]
        if len(cents) == 1 and 0 <= cents[0][2] < 100:
            value += cents[0][2] / 100
        elif cents:
            return None
    return value


def _parse_flexible_money(text: str) -> Optional[float]:
    """解析 OCR 输出的金额，兼容逗号/点混淆（如 5.300.00、5,300.00、5300）。

    OCR 常把千分位逗号识别成点，导致 "5,300.00" 变成 "5.300.00"。
    规则：
    - 同时有逗号和点：最后的分隔符是小数点，其余是千分位
    - 只有多个点：最后一个点是小数点（5.300.00 → 5300.00）
    - 只有多个逗号：最后一个逗号是小数点（5.300,00 → 5300.00）
    - 单个逗号无点：千分位（5,300 → 5300）
    - 单个点且后接 2 位数字：小数点（5300.00）；否则千分位（5.300 → 5300）
    """
    candidates = re.findall(r"[\d.,]+", text.replace(" ", ""))
    if not candidates:
        return None
    best_val = None
    best_score = -1
    for s in candidates:
        if not any(c.isdigit() for c in s):
            continue
        original = s
        if "," in s and "." in s:
            last_comma = s.rfind(",")
            last_dot = s.rfind(".")
            if last_dot > last_comma:
                s = s.replace(",", "")
            else:
                s = s.replace(".", "").replace(",", ".")
        elif s.count(".") > 1:
            parts = s.split(".")
            s = "".join(parts[:-1]) + "." + parts[-1]
        elif s.count(",") > 1:
            parts = s.split(",")
            s = "".join(parts[:-1]) + "." + parts[-1]
        elif "," in s and "." not in s:
            s = s.replace(",", "")
        elif "." in s and "," not in s:
            parts = s.split(".")
            if len(parts) == 2 and len(parts[1]) == 2:
                pass
            else:
                s = s.replace(".", "")
        try:
            val = float(s)
        except ValueError:
            continue
        # 优先选位数最多（最像金额）的候选，避免取到 "1" 这类数量词
        score = len(original.replace(",", "").replace(".", ""))
        if score > best_score:
            best_score = score
            best_val = val
    return best_val


_LKR_FLEX_RE = re.compile(
    r"\blkr\b|l\.k\.r|1\.kr|lkr(?=\d)|\bkr\b",
    re.IGNORECASE,
)


def _find_credit_slip_printed_amount(lines) -> Optional[float]:
    """从机打区 LKR 标签附近取存款金额，兼容 OCR 格式错误。

    OCR 常把 "LKR" 读成 "1.KR" / "L KR" / "L.K.R" 或与金额粘连成
    "LKR35,800.00"，因此用宽松正则匹配 LKR 变体。
    若完全未识别到 LKR，则回退到底部区域扫描最大金额。
    """
    ordered = _sorted_by_y(lines)
    lkr_lines = [ln for ln in ordered if _LKR_FLEX_RE.search(ln.text)]

    candidates = []
    for lkr in lkr_lines:
        lkr_y = _line_center_y(lkr.box)
        lkr_x = _line_center_x(lkr.box)
        for ln in ordered:
            ly = _line_center_y(ln.box)
            lx = _line_center_x(ln.box)
            if abs(ly - lkr_y) > 80:
                continue
            if lx < lkr_x - 50 and ln is not lkr:
                continue
            if _is_denomination_label_line(ln.text):
                continue
            val = _parse_flexible_money(ln.text)
            # 拒绝 < 100 的噪声（如 "LKR 5" 截断、数量词等）
            if val is not None and val >= 100:
                candidates.append((abs(ly - lkr_y), abs(lx - lkr_x), val))

    if candidates:
        candidates.sort()
        return candidates[0][2]

    # Fallback: LKR 完全未识别，扫描底部区域找最大金额
    if not lkr_lines:
        all_vals = []
        for ln in ordered:
            if _is_denomination_label_line(ln.text):
                continue
            val = _parse_flexible_money(ln.text)
            # 排除账号/手机号等大整数（>1000万）和 <100 的噪声
            if val is not None and 100 <= val <= 10_000_000:
                all_vals.append((val, _line_center_y(ln.box)))
        if all_vals:
            # 优先取底部（y 较大）的金额，取底部前 5 个中的最大值
            all_vals.sort(key=lambda x: -x[1])
            bottom = all_vals[:5]
            return max(v[0] for v in bottom)

    return None


def _find_deposit_total_from_table(lines) -> Optional[float]:
    """Read the handwritten TOTAL currency row without loose right-column fallback."""
    ordered = _sorted_by_y(lines)
    for ln in ordered:
        t = ln.text.strip().lower().rstrip(":.")
        if t == "total":
            value = _credit_slip_row_amount(ordered, ln)
            if value is not None and value > 0:
                return value
    return None


def _breakdown_single_line(lines) -> List[DenominationOut]:
    """单行式「面值 张数 金额」三元组（旧版兜底）。"""
    breakdown: List[DenominationOut] = []
    seen = set()
    for ln in lines:
        # 形如 "5000 4 20000.00" 或 "100 1 100.00"
        for m in re.finditer(r"(\d[\d,]*)\s+(\d{1,3})\s+([\d,]+\.\d{2})", ln.text):
            denom = float(m.group(1).replace(",", ""))
            qty = int(m.group(2))
            amt = float(m.group(3).replace(",", ""))
            if denom not in _COMMON_DENOMS:
                continue
            if denom in seen:
                continue
            seen.add(denom)
            if abs(denom * qty - amt) > 0.05:
                continue
            breakdown.append(DenominationOut(denomination=denom, quantity=qty, amount=amt))
    return breakdown


# ---- 银行/渠道识别：按收款凭证来源 app 的强特征短语判型 ----
# 越靠前优先级越高；"commercial bank" 这类宽泛词放最后，避免被收款行的
# "Commercial Bank PLC" 误判（还款场景收款方恒为 Lak Artha / Commercial Bank）。
_BANK_MARKERS = [
    ("vishwa", ("vishwa",)),
    ("peoples_bank", ("peoplespay", "people's pay", "people's bank")),
    ("commercial_bank", ("cardless deposit", "combank", "transfer within", "e-receipt", "bank reference number", "sender's account number", "beneficiary notified", "cash credit slip")),
    ("boc", ("bank of ceylon", "boc flex", "boc")),
    ("hnb", ("hatton national", "hnb", "this is an auto generated receipt")),
    ("dfcc", ("dfcc bank", "dfcc")),
    ("ntb", ("nations trust",)),
    ("lb_finance", ("cash in mobile", "lb finance", "lbcim")),
    ("ipay", ("ipay",)),
    ("pay_master", ("paymaster", "pay master")),
    ("qpayment", ("q payment", "qpayment")),
    ("flash", ("flash",)),
]


_BOC_APP_MARKERS = (
    "casa transfer",
    "my bank account",
    "fund transfer/card",
    "settlement service charge",
)


def _is_boc_app(lines) -> bool:
    """BOC 手机银行 "Transaction Successful" 版式（Account Information 卡片）。"""
    full = " ".join(ln.text for ln in lines).lower()
    return any(m in full for m in _BOC_APP_MARKERS)


_CDM_MARKERS = ("cardless deposit",)


def _is_cash_deposit(lines) -> bool:
    """Commercial Bank CDM 无卡存款凭条（CARDLESS DEPOSIT）。"""
    full = " ".join(ln.text for ln in lines).lower()
    return any(m in full for m in _CDM_MARKERS)


_CASH_CREDIT_SLIP_MARKERS = ("cash credit slip", "current account - cash deposit")


def _has_denomination_table(lines) -> bool:
    """检测现金存款凭条右侧的面额表（5000 X / 2000 X / 1000 X ...）。

    OCR 常把 "CASH CREDIT SLIP" 标题读坏，但面额表是结构化印刷体，
    只要识别出 3 个以上面额标签行即可判定为现金存款凭条。
    """
    count = sum(1 for ln in lines if _is_denomination_label_line(ln.text))
    return count >= 3


def _is_cash_credit_slip(lines) -> bool:
    """Commercial Bank 纸质现金存款凭条（CASH CREDIT SLIP）。

    强特征（任一满足）：
    1. 标题 "CASH CREDIT SLIP" 或底部机打 "CURRENT ACCOUNT - CASH DEPOSIT"；
    2. 面额表（3+ 个 "XXXX X" 标签行）+ "commercial bank" 或 "cash deposit"。
    与 CDM（无卡存款）区分：CDM 有 "CARDLESS DEPOSIT"，本版式为手写填表 + 机打底部。
    """
    full = " ".join(ln.text for ln in lines).lower()
    if any(m in full for m in _CASH_CREDIT_SLIP_MARKERS):
        return True
    # 兜底：面额表 + 银行/存款关键词（OCR 把标题读坏时仍能命中）
    if _has_denomination_table(lines) and (
        "commercial bank" in full or "cash deposit" in full or "deposit by" in full
    ):
        return True
    return False


def _is_to_only_receipt(lines) -> bool:
    """Commercial Bank 手机 App「转账成功」版式：只显示收款方（To），无付款方区。

    强特征 "Beneficiary Notified"；或用 "Transfer Successful!" + 独立的 "To" 行兜底，
    避免与其它银行的同名标题混淆。
    """
    full = " ".join(ln.text for ln in lines).lower()
    if "beneficiary notified" in full:
        return True
    if "transfer successful" not in full:
        return False
    return any(ln.text.strip().strip(":：. ").lower() == "to" for ln in lines)


def _is_hnb_app_receipt(lines) -> bool:
    """HNB 手机 App「Fund Transfer Receipt」：居中 From/To，收款方姓名+账号合并一行，
    底部 "This is an auto generated receipt" / "Receiver reference"。"""
    full = " ".join(ln.text for ln in lines).lower()
    if "this is an auto generated receipt" in full or "hatton national" in full:
        return True
    return "fund transfer receipt" in full and "receiver reference" in full


def _detect_bank(lines) -> Optional[str]:
    full = " ".join(ln.text for ln in lines).lower()
    # 抢在 "people's bank" 之前：该版式底部会显示付款来源银行（如 People's Bank）。
    if _is_boc_app(lines):
        return "boc"
    for bank, markers in _BANK_MARKERS:
        for m in markers:
            if m == "bank of ceylon":
                # 仅命中非 "commercial bank of ceylon" 的独立 "bank of ceylon"（区分 BOC 与 ComBank）
                if re.search(r"(?<!commercial )bank of ceylon", full):
                    return bank
                continue
            if m in full:
                return bank
    return None


def _match_two_column(zone, label_texts) -> Optional[str]:
    """左标右值版式：标签独占一行（精确匹配），取右侧或正下方原文值。"""
    ordered = _sorted_by_y(zone)
    for i, ln in enumerate(ordered):
        t = ln.text.strip().strip(":：. ").lower()
        if t not in label_texts:
            continue
        side = _value_to_right(i, ordered, ln)
        if side and not _looks_like_label_text(side):
            return side
        below = _value_below(i, ordered, ln)
        if below and not _looks_like_label_text(below):
            return below
    return None


def _first_alpha_value(zone, x_threshold: float = 400.0) -> Optional[str]:
    """兜底：取区域内首个「右列 + 含字母」的值行（用于漏识别 Name 标签时）。"""
    for ln in _sorted_by_y(zone):
        if min(p[0] for p in ln.box) < x_threshold:
            continue  # 左列标签行
        t = ln.text.strip()
        if len(t) < 2 or re.fullmatch(r"[\d\s,\.*/\-:]+", t):
            continue
        return t
    return None


def _first_account_line(zone) -> Optional[str]:
    """兜底：取区域内在 y 序上首个纯数字/星号（>=6 位）账号行。"""
    for ln in _sorted_by_y(zone):
        t = ln.text.strip()
        if re.fullmatch(r"[\d*]{6,}", t):
            return t
    return None


def _extract_peoples_bank_parties(lines) -> tuple[PartyOut, PartyOut]:
    """People's Bank 回执：兼容两栏（People's Pay 左标右值）与单栏（标签+值同行）。"""
    payer, payee = PartyOut(), PartyOut()
    payer_zone, payee_zone, _ = _split_zones(lines)

    # 两栏（左标右值）
    payer.name = _match_two_column(payer_zone, {"name"})
    payer.account = _match_two_column(payer_zone, {"account no", "account number"})
    payer.bank = _match_two_column(payer_zone, {"bank"})
    payee.name = _match_two_column(payee_zone, {"name"})
    payee.bank = _match_two_column(payee_zone, {"bank name", "beneficiary bank", "beneficiary's bank", "to bank"})
    payee.account = _match_two_column(payee_zone, {"account no", "account number"})

    # 单栏（标签+值同行）回退
    if not payer.name:
        payer.name = _match_name(payer_zone, _PAYER_NAME_LABELS)
    if not payer.account:
        payer.account = _extract_account(payer_zone, _PAYER_ACCOUNT_LABELS)
    if not payer.bank:
        payer.bank = _match_label_value(payer_zone, _PAYER_BANK_LABELS)
    if not payee.name:
        payee.name = _match_name(payee_zone, _PAYEE_NAME_LABELS)
    if not payee.bank:
        payee.bank = _match_label_value(payee_zone, _PAYEE_BANK_LABELS)
    if not payee.account:
        payee.account = _extract_account(payee_zone, _PAYEE_ACCOUNT_LABELS)

    # 漏识别标签时的位置回退（pay to 的 Name / Account No 可能整行漏 OCR）
    if not payee.name:
        payee.name = _first_alpha_value(payee_zone)
    if not payee.account:
        payee.account = _first_account_line(payee_zone)

    payer.account_prefix, payer.account_last4 = _derive_account_parts(payer.account)
    payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)
    return payer, payee


def _extract_cdm_parties(lines) -> tuple[PartyOut, PartyOut]:
    """Commercial Bank CDM 无卡存款凭条：现金存款，无付款方。

    收款方（户名/账号）来自 "CUSTOMER NAME" / "ACC0UNT NUMBER" 同行标签，
    OCR 常把 "ACCOUNT" 误识为 "ACC0UNT"（0 替 O），故标签加容错变体。
    """
    payer, payee = PartyOut(), PartyOut()
    payee.name = _match_label_value(lines, ["customer name", "beneficiary name", "account name"])
    payee.account = _extract_account(
        lines,
        ["account number", "acc0unt number", "account no", "acc0unt no"],
    )
    payer.account_prefix, payer.account_last4 = _derive_account_parts(payer.account)
    payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)
    return payer, payee


_ACCOUNT_HOLDER_NAME_LABELS = [
    "name of account holder",
    "name of account holdur",  # OCR 常见误读
    "ot account holder",       # "Name of" 被截断
]
_DEPOSITOR_NAME_LABELS = [
    "name and address of the depositor",
    "name & address of the depositor",
    "address of the depositor",
    "address ofthe depositor",  # OCR 把 "of the" 连成 "ofthe"
    "ano address ofthe depositor",  # "NAME AND" 被误读为 "ANO"
]


def _extract_cash_credit_slip_parties(lines) -> tuple[PartyOut, PartyOut]:
    """Commercial Bank 纸质现金存款凭条（CASH CREDIT SLIP）。

    版式：上方「Name of Account Holder」（收款方/账户持有人，手写）、
    「ACCOUNT NUMBER」（右栏），中部「NAME AND ADDRESS OF THE DEPOSITOR」（付款方/存款人），
    右侧面额表格，底部机打交易信息（户名、账号、金额）。

    账号用 _extract_account（带 _account_token 校验），与 CDM 保持一致，
    避免把右栏的 OCR 噪声（如 "Gur"）当成账号。
    姓名优先取表单字段值，缺失时回退到底部机打户名。
    """
    payer, payee = PartyOut(), PartyOut()
    ordered = _sorted_by_y(lines)

    # 收款方姓名：账户持有人字段，回退底部机打户名
    payee.name = _credit_slip_name_value(ordered, _ACCOUNT_HOLDER_NAME_LABELS)
    if not payee.name:
        payee.name = _find_bottom_account_holder_name(ordered)

    # 付款方姓名：存款人字段
    payer.name = _credit_slip_name_value(ordered, _DEPOSITOR_NAME_LABELS)

    # 收款方账号：ACCOUNT NUMBER，带 token 校验，回退底部纯数字账号行
    payee.account = _extract_account(
        ordered,
        ["account number", "acc0unt number", "account no", "acc0unt no"],
    )
    if not payee.account:
        payee.account = _find_bottom_account_number(ordered)

    payee.bank = "Commercial Bank"

    payer.account_prefix, payer.account_last4 = _derive_account_parts(payer.account)
    payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)
    return payer, payee


def _looks_like_account_or_ref(text: str) -> bool:
    """判断文本是否像账号/参考号（含较长数字段的字母数字串），用于户名兜底时排除。"""
    t = re.sub(r"\s+", "", text)
    # 全字母（无数字）的不是账号
    if not re.search(r"\d", t):
        return False
    # 含 6 位以上连续数字
    if re.search(r"\d{6,}", t):
        return True
    # 字母+数字混合且数字占比高（如 G058335870）
    digits = len(re.findall(r"\d", t))
    if len(t) >= 6 and digits >= len(t) * 0.5:
        return True
    return False


def _valid_credit_slip_name(text: Optional[str]) -> bool:
    if not text or _looks_like_account_or_ref(text):
        return False
    # Compact OCR-corrupted labels (e.g. "5.REFNUMSER") are not names.
    compact = re.sub(r"[^a-z]", "", text.lower())
    if any(word in compact for word in (
        "refnum", "reference", "name", "address", "adoress", "depositor",
        "account", "purpose", "source", "funds", "signature", "thank",
        "bank", "total", "teller", "officer", "customer", "cdbs", "lkr",
    )):
        return False
    words = re.findall(r"[A-Za-z]{2,}", text)
    return len(words) >= 2 and not re.search(r"\d", text)


def _credit_slip_name_value(lines, labels) -> Optional[str]:
    """Use the form's field boundaries, not the nearest right-column label."""
    for ln in lines:
        for label in labels:
            if label not in ln.text.lower():
                continue
            inline = _value_after_label(ln.text, label)
            if _valid_credit_slip_name(inline):
                return inline
            y = _line_center_y(ln.box)
            height = max(p[1] for p in ln.box) - min(p[1] for p in ln.box)
            x0, x1 = min(p[0] for p in ln.box), max(p[0] for p in ln.box)
            below = [
                other for other in lines
                if y + 2 < _line_center_y(other.box) <= y + 2.5 * height
                and x0 - 0.5 * height <= min(p[0] for p in other.box) < x1
            ]
            # Never search past the next printed label in the field.
            for other in _sorted_by_y(below):
                if _valid_credit_slip_name(other.text):
                    return _clean(other.text)
                if re.search(r"[A-Za-z]{3,}", other.text):
                    break
    return None


def _find_bottom_account_holder_name(lines) -> Optional[str]:
    """现金存款凭条底部机打区：取第一个非标签、非账号的字母行作为户名。

    底部通常有 "LAK ARTHA SERVICES" 等户名，夹在日期、账号、金额之间。
    跳过：标签词行、纯数字/符号行、面额标签行、账号/参考号型字符串。
    """
    skip_words = (
        "date", "time", "reference", "account", "bank", "deposit", "thank", "you",
        "current", "savings", "lkr", "rs", "teller", "officer", "copy", "auth",
        "cdbs", "notes", "coins", "total", "name", "address", "purpose", "funds",
        "nic", "pdl", "tel", "cash", "credit", "slip", "customer",
    )
    ys = [_line_center_y(l.box) for l in lines]
    if not ys:
        return None
    mid = min(ys) + 0.6 * (max(ys) - min(ys))
    # A nearby printed account line is stronger evidence than a random alpha line.
    accounts = [ln for ln in lines if re.fullmatch(r"\d{8,}", ln.text.strip())
                and _line_center_y(ln.box) >= mid]
    if not accounts:
        return None
    for ln in _sorted_by_y(lines):
        if _line_center_y(ln.box) < mid:
            continue
        t = ln.text.strip()
        if not t or len(t) < 3:
            continue
        if not _valid_credit_slip_name(t):
            continue
        height = max(p[1] for p in ln.box) - min(p[1] for p in ln.box)
        name_x0, name_x1 = min(p[0] for p in ln.box), max(p[0] for p in ln.box)
        if not any(
            0 < _line_center_y(acc.box) - _line_center_y(ln.box) <= 3 * height
            and max(name_x0, min(p[0] for p in acc.box))
            < min(name_x1, max(p[0] for p in acc.box))
            for acc in accounts
        ):
            continue
        if re.fullmatch(r"[\d\s,\.*/\-:]+", t):
            continue  # 纯数字/符号行（日期、账号、金额）
        low = t.lower()
        if any(w in low for w in skip_words):
            continue
        if _looks_like_account_or_ref(t):
            continue  # 账号/参考号型字符串（如 G058335870）
        if re.fullmatch(r"\d+\s*[xX]\s*.*", t):
            continue  # 面额标签行（如 "5000 X"）
        return _clean(t)
    return None


def _find_bottom_account_number(lines) -> Optional[str]:
    """现金存款凭条底部机打区：取第一个纯数字（>=8 位）的账号行。"""
    for ln in _sorted_by_y(lines):
        t = ln.text.strip()
        if re.fullmatch(r"\d{8,}", t):
            return t
    return None


def _extract_to_only_parties(lines) -> tuple[PartyOut, PartyOut]:
    """Commercial Bank「转账成功」收款方-only 回执：只提取收款方，付款方留空。

    要点：泛型 "bank" 标签会把收款方银行 "Commercial Bank PLC" 误取成 "PLC"，
    这里按 "To" 锚点下方区块的结构化位置（姓名→账号→银行）逐项提取。
    """
    payer, payee = PartyOut(), PartyOut()
    ordered = _sorted_by_y(lines)
    anchor_y = None
    for ln in ordered:
        if ln.text.strip().strip(":：. ").lower() == "to":
            anchor_y = _line_center_y(ln.box)
            break
    if anchor_y is None:
        return payer, payee

    below = [ln for ln in ordered if _line_center_y(ln.box) > anchor_y + 2]

    # 银行：第一个含 "bank" 的整行原文（"Commercial Bank PLC." -> "Commercial Bank PLC"）
    for ln in below:
        if "bank" in ln.text.lower():
            payee.bank = _clean(ln.text)
            break
    # 账号：第一个纯数字/星号（>=6 位）行
    for ln in below:
        t = ln.text.strip()
        if re.fullmatch(r"[\d*]{6,}", t):
            payee.account = t
            break
    # 姓名：第一个「非纯数字、非银行、非标签/页脚」的字母行
    for ln in below:
        t = ln.text.strip()
        if re.fullmatch(r"[\d\s,\.*/\-:]+", t):
            continue
        low = t.lower()
        if any(k in low for k in ("bank", "reference", "date", "time", "notified",
                                   "transfer", "another", "download", "ok")):
            continue
        v = _clean(t)
        if v and len(v) >= 2:
            payee.name = v
            break

    payer.account_prefix, payer.account_last4 = _derive_account_parts(payer.account)
    payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)
    return payer, payee


def _extract_hnb_app_parties(lines) -> tuple[PartyOut, PartyOut]:
    """HNB「Fund Transfer Receipt」：From/To 居中标签，值堆叠在下方。

    收款方「姓名+账号」常合并在同一行（"Lak Artha Pvt Ltd-1001096962"），
    银行 "Commercial Bank PLC" 需取整行而不是泛型 "bank" 截出的 "PLC"。
    """
    payer, payee = PartyOut(), PartyOut()
    ordered = _sorted_by_y(lines)
    from_idx = to_idx = None
    for i, ln in enumerate(ordered):
        t = ln.text.strip().strip(":：. ").lower()
        if t == "from" and from_idx is None:
            from_idx = i
        elif t == "to" and to_idx is None:
            to_idx = i

    if from_idx is not None:
        for j in range(from_idx + 1, len(ordered)):
            t = ordered[j].text.strip()
            if re.fullmatch(r"[\d\s,.\-:/]+", t):
                continue
            v = _clean(t)
            if v and not _looks_like_label_text(v):
                payer.name = v
                break

    if to_idx is not None:
        got_account = False
        for ln in ordered[to_idx + 1:]:
            t = ln.text.strip()
            low = t.lower()
            if any(k in low for k in ("reference", "date/time", "date & time",
                                        "auto generated", "this is")):
                break
            if "bank" in low:
                cand = _clean(t)
                if payee.bank is None or len(cand) > len(payee.bank):
                    payee.bank = cand
                continue
            if not got_account:
                m = re.search(r"(\d{6,})$", t)
                if m:
                    payee.account = m.group(1)
                    name = t[:m.start()].strip(" -–:：.")
                    if name:
                        payee.name = _clean(name)
                    got_account = True

    payer.bank = "HNB"
    payer.account_prefix, payer.account_last4 = _derive_account_parts(payer.account)
    payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)
    return payer, payee


def _extract_boc_app_parties(lines) -> tuple[PartyOut, PartyOut]:
    """BOC 手机银行 "Transaction Successful" 版式：Account Information 卡片，
    左标右值两栏，无 Pay from / Pay to 分区，收款账户在卡片内、付款来源在底部。"""
    payer, payee = PartyOut(), PartyOut()
    ordered = _sorted_by_y(lines)

    payee.account = _right_column_for(ordered, {"account number"})
    payee.bank = _right_column_for(ordered, {"transfer bank", "beneficiary bank", "bank name"})
    payee.name = _right_column_for(ordered, {"beneficiary name"})

    # 付款来源：底部 "My bank account X" 下方显示的银行名
    for i, ln in enumerate(ordered):
        if ln.text.strip().lower().startswith("my bank account"):
            v = _value_below(i, ordered, ln)
            if v and not _looks_like_label_text(v):
                payer.bank = v
            break

    payer.account_prefix, payer.account_last4 = _derive_account_parts(payer.account)
    payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)
    return payer, payee


_PEOPLES_BANK_LABELS = (
    "Bank",
    "Account No",
    "Account Currency",
    "Name",
    "Bank Name",
    "Amount (LKR)",
    "Fee Amount (LKR)",
    "Total debit amount (LKR)",
    "Date & Time",
    "Trace No",
)

_E_RECEIPT_LABELS = (
    "Bank Reference Number",
    "Sender's Account Number",
    "Sender's Name",
    "Transfer Amount",
    "Transfer Currency",
    "Beneficiary Name",
    "Beneficiary Account Number",
    "Beneficiary's Account Narration",
    "Transaction Date/Time",
    "Payment Date",
    "Status",
)

_BOC_APP_LABELS = (
    "Transaction Type",
    "Account Number",
    "Transfer bank",
    "Reference/Remarks",
    "Amount",
    "Other Charges",
    "Total Amount",
)


def _norm_label(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _build_label_fields(lines, labels) -> dict:
    """按白名单标签，提取「单据原始英文字段名 -> 原文值」的扁平映射。

    兼容两种版式：
    * 两栏「左标签 / 右值 / 下方」（如 Commercial Bank e-Receipt、People's Pay）；
    * 单栏「Label Value」或「Label: Value」同行。
    匹配时忽略空格/标点，容忍 OCR 的 "( LKR )"、"Date &Time" 等变体。
    """
    wanted = {_norm_label(lbl): lbl for lbl in labels}
    fields: dict = {}
    ordered = _sorted_by_y(lines)
    # 两栏：左标签、右值 / 下方取值（标签独占一行）
    for i, ln in enumerate(ordered):
        key = wanted.get(_norm_label(ln.text))
        if key is None or key in fields:
            continue
        side = _value_to_right(i, ordered, ln)
        if not side:
            side = _right_column_value(i, ordered, ln)
        if side:
            fields[key] = side
        else:
            below = _value_below(i, ordered, ln)
            if below:
                fields[key] = below
    # 单栏：标签与值在同一行
    for ln in ordered:
        for lbl in labels:
            if lbl in fields:
                continue
            value = _value_after_label(ln.text, lbl)
            if value and not _looks_like_label_text(value):
                fields[lbl] = value
                break
    return fields


_BRANCH_RE = re.compile(r"(?i)^[a-z0-9][a-z0-9\-./ ]*\bbr\b$")


def _extract_branch(lines) -> Optional[str]:
    """存款凭条网点：通常以 "BR"（branch）结尾，如 "BANDARAG-CRM2 BR"。"""
    for ln in _sorted_by_y(lines):
        t = ln.text.strip()
        if _BRANCH_RE.fullmatch(t):
            return t
    return _match_label_value(lines, ["branch", "branch name"])


def extract(lines, include_lines: bool = False) -> RepaymentResult:
    warnings: List[str] = []

    full_text = " ".join(ln.text for ln in lines)

    doc_type = _detect_doc_type(full_text)
    status = _detect_status(full_text)
    bank = _detect_bank(lines)
    # 现金存款凭条版式固定为 Commercial Bank，即使 OCR 把 "cash credit slip" 读坏，
    # 只要面额表检测命中就设为 commercial_bank。
    if _is_cash_credit_slip(lines) and not bank:
        bank = "commercial_bank"

    payer, payee = _extract_parties(lines, bank)
    trace_no = _match_label_value(lines, ["trace no", "trace number", "tranceno", "trace"])
    terminal_id = _match_label_value(lines, ["terminal id"])
    branch = _extract_branch(lines)
    amount, fee, total = _extract_amounts(lines)
    dt = _find_datetime(lines)
    references = _extract_references(lines)
    if trace_no is None and references.transaction_id:
        trace_no = references.transaction_id

    deposit_breakdown = _find_deposit_breakdown(lines, total_amount=amount) if doc_type == "cash_deposit_slip" else []
    if _is_cash_credit_slip(lines):
        if amount is None:
            warnings.append("未可靠识别存款金额，请检查 OCR 原文")
        if payee.name is None:
            warnings.append("未可靠识别账户持有人姓名")
        if not deposit_breakdown:
            warnings.append("未可靠识别手写纸币明细，未默认补填张数")

    # 金额一致性校验
    if amount is not None and fee is not None and total is not None:
        if abs(total - (amount + fee)) > 0.02:
            warnings.append(
                f"金额校验不一致: amount({amount}) + fee({fee}) != total({total})"
            )

    # 存款凭条：纸币明细加总校验
    if deposit_breakdown:
        breakdown_sum = sum(d.amount for d in deposit_breakdown)
        if amount is not None and abs(breakdown_sum - amount) > 0.05:
            # 面额表是逐行扫描的，比总额行的 OCR 更可靠（总额常被读成
            # "000008" 之类的损坏串），不一致时优先采用明细加总
            amount = breakdown_sum
            if total is not None:
                total = breakdown_sum
        elif amount is None:
            amount = breakdown_sum
            if total is None:
                total = breakdown_sum

    # 收款方归一化：还款场景常见 Lak Artha 系列写法
    if payee.name:
        low = payee.name.lower()
        if "lak artha" in low or "lak-artha" in low:
            payee.name = "Lak Artha (Pvt) Ltd"

    success = bool(amount is not None or payee.account is not None or payee.name is not None)
    # App 还款发起页/上传截图页不是交易凭证，强制 success=false
    if doc_type == "unknown" and _is_app_loan_page(full_text):
        success = False
        warnings.append("上传图片不是银行交易凭证，请上传银行还款截图")

    if _is_boc_app(lines):
        field_labels = _BOC_APP_LABELS
    elif bank == "peoples_bank":
        field_labels = _PEOPLES_BANK_LABELS
    else:
        field_labels = _E_RECEIPT_LABELS

    return RepaymentResult(
        success=success,
        doc_type=doc_type,
        status=status,
        bank=bank,
        payer=payer,
        payee=payee,
        amount=amount,
        fee=fee,
        total_debit=total,
        currency="LKR",
        datetime=dt,
        references=references,
        fields=_build_label_fields(lines, field_labels),
        deposit_breakdown=deposit_breakdown,
        branch=branch,
        terminal_id=terminal_id,
        trace_no=trace_no,
        warnings=warnings,
        lines=[OcrLineOut(text=l.text, confidence=l.confidence, box=l.box) for l in lines] if include_lines else [],
    )
