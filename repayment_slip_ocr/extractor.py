"""还款/转账凭证的字段抽取。

从 OCR 行中抽取：单据类型、交易状态、付款方/收款方、金额、手续费、总扣款、
日期时间、各类参考号，以及现金存款凭条的纸币明细。不同银行版式（People's Bank /
Pan Asia Bank / BOC Flex / Commercial Bank）标签措辞不同，故使用多组同义词标签 + 分区
归属（Pay from / Pay to 上下区）来定位字段，识别不到时降级为 null 并写入 warnings。
"""
from __future__ import annotations

import re
from collections import Counter
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


def _is_rotated_box(box) -> bool:
    """检测非水平/垂直的旋转文本框（如截图上的斜向水印、批注）。

    正常文本四边分别接近水平/垂直，斜向文本顶边两点 y 差（或侧边 x 差）明显偏大。
    """
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = box
    return (
        abs(y0 - y1) > 25.0
        or abs(y2 - y3) > 25.0
        or abs(x0 - x3) > 25.0
        or abs(x1 - x2) > 25.0
    )


def _is_tall_box(box) -> bool:
    """轴对齐但明显竖直的文本框（竖拍凭条上 OCR 读出的竖排标签）。"""
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    return h > max(60.0, 1.5 * max(w, 1.0))


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
    # 账号形态（如 "LKR 055-2-001-2-3595355"）不能当金额
    if re.search(r"\d+-\d+-\d+", s):
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
    # label 中字母数字易混淆字符做 OCR 容错（O↔0、I↔1），兼容 "ACC0UNT" 匹配 "ACCOUNT"
    pattern = re.escape(label)
    pattern = re.sub(r"[Oo0]", "[O0]", pattern)
    pattern = re.sub(r"[Ii1]", "[I1]", pattern)
    # 短标签 "Bank" 必须在行首，否则 "Commercial Bank PLC" 会被截成 "PLC"
    if label.lower() in {"bank", "name"}:
        m = re.search(r"^\s*" + pattern + r"\b\s*[:：]?\s*(.+)", line_text, re.IGNORECASE)
    else:
        m = re.search(r"\b" + pattern + r"\b\s*[:：]?\s*(.+)", line_text, re.IGNORECASE)
    if not m:
        return None
    value = _clean(m.group(1))
    return value or None


def _value_line_above(idx: int, lines, label_line):
    """取标签正上方同列最近的值行（竖拍手机截图：原左值转到标签上方）。"""
    tall = _is_tall_box(label_line.box)
    label_top = min(p[1] for p in label_line.box)
    base_y = label_top if tall else _line_center_y(label_line.box)
    label_left = min(p[0] for p in label_line.box)
    label_cx = _line_center_x(label_line.box)
    best = None
    for j, other in enumerate(lines):
        if j == idx:
            continue
        text = other.text.strip()
        if not text or _looks_like_label_text(text):
            continue
        other_bottom = max(p[1] for p in other.box)
        y = _line_center_y(other.box)
        other_left = min(p[0] for p in other.box)
        other_cx = _line_center_x(other.box)
        if tall:
            dy = base_y - other_bottom
            # 竖拍手机 UI 标签与值纵向间距常 400–600px
            if dy < -40 or dy > 700:
                continue
            dy = max(dy, 0.0) + 0.01
        else:
            dy = base_y - y
            if dy <= 2 or dy > 180:
                continue
        dx = min(abs(other_left - label_left), abs(other_cx - label_cx))
        if dx >= 140:
            continue
        score = (dy, dx)
        if best is None or score < best[0]:
            best = (score, other)
    return best[1] if best else None


def _value_above(idx: int, lines, label_line) -> Optional[str]:
    """取标签正上方最近的值行文本。"""
    ln = _value_line_above(idx, lines, label_line)
    return _clean(ln.text) if ln else None


def _merge_x_adjacent_fragments(lines, seed_line, wanted_norms: set) -> str:
    """竖排 OCR 把长姓名拆成左右相邻碎片时，按 x 拼回同一值。"""
    sy0 = min(p[1] for p in seed_line.box)
    sy1 = max(p[1] for p in seed_line.box)
    seed_h = max(sy1 - sy0, 1.0)
    cands = []
    for other in lines:
        text = other.text.strip()
        if not text or _looks_like_label_text(text):
            continue
        if _norm_label(text) in wanted_norms:
            continue
        oy0 = min(p[1] for p in other.box)
        oy1 = max(p[1] for p in other.box)
        overlap = max(0.0, min(sy1, oy1) - max(sy0, oy0))
        if overlap < 0.25 * min(seed_h, max(oy1 - oy0, 1.0)):
            continue
        cands.append(other)
    if not cands:
        return _clean(seed_line.text)
    # 同框 OCR 变体（掩码账号 90***/00***）只留置信度最高者，避免拼成两串
    cands.sort(
        key=lambda ln: (
            -float(getattr(ln, "confidence", 0.0) or 0.0),
            _line_center_x(ln.box),
        )
    )
    unique = []
    for ln in cands:
        cx, cy = _line_center_x(ln.box), _line_center_y(ln.box)
        if any(abs(cx - _line_center_x(u.box)) < 35 and abs(cy - _line_center_y(u.box)) < 35 for u in unique):
            continue
        unique.append(ln)
    cands = sorted(unique, key=lambda ln: (_line_center_x(ln.box), _line_center_y(ln.box)))
    xs = [_line_center_x(ln.box) for ln in cands]
    seed_i = next((i for i, ln in enumerate(cands) if ln is seed_line), None)
    if seed_i is None:
        seed_i = min(
            range(len(cands)),
            key=lambda i: abs(xs[i] - _line_center_x(seed_line.box)),
        )
    lo = hi = seed_i
    while lo > 0 and xs[lo] - xs[lo - 1] < 90:
        lo -= 1
    while hi + 1 < len(cands) and xs[hi + 1] - xs[hi] < 90:
        hi += 1
    parts = [_clean(ln.text) for ln in cands[lo : hi + 1] if _clean(ln.text)]
    out = []
    for p in parts:
        if out and _norm_label(out[-1]) == _norm_label(p):
            continue
        out.append(p)
    return " ".join(out)


def _value_below(idx: int, lines, label_line) -> Optional[str]:
    """取标签正下方最近的值行。

    用中心点 x + 收紧的水平窗口，避免 CDM 并排表头把邻列 TERMINAL ID
    （left-x 仍可能落入旧的 200px 窗口）抢给 DATE/TIME。
    打分优先更近的下一行（dy），再比水平对齐（dx）：TRACE 的值常印在 TIME
    列正下方，若先比 dx 会越过本列的 HH:MM 误取 TRACE 号。
    竖排高标签以底边起算 dy，否则标签自身高度会把正下方值挤出 160px 窗口。
    """
    tall = _is_tall_box(label_line.box)
    label_bottom = max(p[1] for p in label_line.box)
    base_y = label_bottom if tall else _line_center_y(label_line.box)
    label_left = min(p[0] for p in label_line.box)
    label_cx = _line_center_x(label_line.box)
    best = None
    for j, other in enumerate(lines):
        if j == idx:
            continue
        text = other.text.strip()
        if not text or _looks_like_label_text(text):
            continue
        other_top = min(p[1] for p in other.box)
        y = _line_center_y(other.box)
        other_left = min(p[0] for p in other.box)
        other_cx = _line_center_x(other.box)
        if tall:
            dy = other_top - base_y
            if dy < -15 or dy > 220:
                continue
            dy = max(dy, 0.0) + 0.01  # 保持「越近越好」
        else:
            dy = y - base_y
            if dy <= 2 or dy > 160:
                continue
        # 宽标签（如 Beneficiary Account Number）中心偏右，值往往左对齐；
        # 窄并列表头则中心对齐更稳。取 left/center 较小 dx。
        dx = min(abs(other_left - label_left), abs(other_cx - label_cx))
        if dx >= 140:
            continue
        score = (dy, dx)
        if best is None or score < best[0]:
            best = (score, text)
    return best[1] if best else None


def _value_to_right(idx: int, lines, label_line) -> Optional[str]:
    """左标右值的两栏版式：取与标签行同一水平带、位于其右侧的值行文本。

    用垂直重叠度挑选右侧候选行，避免把相邻标签的值张冠李戴。
    """
    best_line = _value_line_to_right(idx, lines, label_line)
    return _clean(best_line.text) if best_line else None


def _value_line_to_right(idx: int, lines, label_line):
    """返回与标签同行、位于右侧的最佳值行对象。"""
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
            best = (overlap, other)
    return best[1] if best else None


def _value_line_to_left(idx: int, lines, label_line):
    """返回与标签同一水平带、位于左侧的最佳值行（竖拍 CDM：值在标签左侧）。"""
    ly0 = min(p[1] for p in label_line.box)
    ly1 = max(p[1] for p in label_line.box)
    label_left_x = min(p[0] for p in label_line.box)
    best = None
    for j, other in enumerate(lines):
        if j == idx:
            continue
        ox1 = max(p[0] for p in other.box)
        oy0 = min(p[1] for p in other.box)
        oy1 = max(p[1] for p in other.box)
        if ox1 > label_left_x + 25:
            continue
        if max(ly0, oy0) >= min(ly1, oy1):
            continue
        overlap = min(ly1, oy1) - max(ly0, oy0)
        gap = label_left_x - ox1
        score = (-overlap, gap)
        if best is None or score < best[0]:
            best = (score, other)
    return best[1] if best else None


def _right_column_value(idx: int, lines, label_line, max_vy: float = 170.0) -> Optional[str]:
    """左标右值两栏版式：取标签行右侧（可略偏下）最近的一条右列值行文本。

    部分电子回单的值比标签略低（如 BOC "Other Charges" 的值在标签下一行），严格按
    垂直重叠会取空，这里用「在标签右侧 + 垂直方向不高于 max_vy」的宽松窗口兜底。
    """
    best_line = _right_column_line(idx, lines, label_line, max_vy=max_vy)
    return _clean(best_line.text) if best_line else None


def _right_column_line(idx: int, lines, label_line, max_vy: float = 170.0):
    """返回标签右侧（可略偏下）的最佳值行对象。"""
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
            best = (oy, other)
    return best[1] if best else None


def _row_has_left_label(lines, value_line, other, base_left_x, x_tol: float = 140.0, y_tol: float = 20.0) -> bool:
    """判断候选行 other 左侧同一水平带是否存在标签行。"""
    oy = _line_center_y(other.box)
    for peer in lines:
        if peer is value_line or peer is other:
            continue
        py = _line_center_y(peer.box)
        if abs(py - oy) > y_tol:
            continue
        px = min(p[0] for p in peer.box)
        if px < base_left_x - x_tol:
            return True
    return False


def _collect_column_block(lines, value_line, max_gap: float = 400.0, x_tol: float = 140.0, min_gap: float = 30.0) -> str:
    """拼接同一右列连续值块，兼容目标值换到下一行的电子回执版式。

    向下扫描，区分三种情况：
    * y 间距过小（min_gap）视为同一水平带的 OCR 重复变体，跳过；
    * 左侧同一水平带出现标签行，说明进入下一组字段，停止；
    * 右侧同列的行视为当前值的续行，拼接。
    """
    parts = [_clean(value_line.text)]
    base_left_x = min(p[0] for p in value_line.box)
    last_y = _line_center_y(value_line.box)
    seen_value = False
    for other in _sorted_by_y(lines):
        if other is value_line:
            seen_value = True
            continue
        if not seen_value:
            continue
        oy = _line_center_y(other.box)
        dy = oy - last_y
        if dy > max_gap:
            break
        if dy < min_gap:
            continue  # 同一水平带的重复变体
        ox = min(p[0] for p in other.box)
        if ox < base_left_x - x_tol:
            break  # 左侧出现新标签行，进入下一组字段
        if _row_has_left_label(lines, value_line, other, base_left_x, x_tol=x_tol):
            break  # 右侧行但左侧同行有标签，属下一字段
        if ox > base_left_x + x_tol:
            continue  # 更靠右的其它内容（如 logo）
        text = _clean(other.text)
        if not text or _looks_like_label_text(text):
            continue
        parts.append(text)
        last_y = oy
    return " ".join(parts)


def _has_notes_value_table(lines) -> bool:
    texts = {" ".join(ln.text.lower().split()) for ln in lines}
    return any("notes" == t or t.startswith("notes") for t in texts) and any(
        "value" == t or t.startswith("value") for t in texts
    )


def _recover_cdm_deposit_amount_from_notes_band(lines) -> Optional[float]:
    """CDM 漏读 DEPOSIT AMOUNT 标签时：从 NOTES/VALUE/AMOUNT 带回收总额。

    典型：表头 + 行金额/存款总额均为 15.000.00，标签被拇指挡住。
    """
    if not lines:
        return None
    anchor_ys = []
    for ln in lines:
        low = " ".join(ln.text.lower().split())
        if low in {"notes", "value", "amount"} or low.startswith(
            ("notes", "value", "deposit amount", "depositamount")
        ):
            anchor_ys.append(_line_center_y(ln.box))
        elif re.search(r"(?i)\blkr\b", ln.text) and _parse_money(ln.text) is None:
            # 单独 LKR 常在总额旁
            anchor_ys.append(_line_center_y(ln.box))
    if anchor_ys:
        y_min = min(anchor_ys) - 80
    else:
        ys = [_line_center_y(ln.box) for ln in lines if ln.box]
        if not ys:
            return None
        y_min = max(ys) * 0.55

    cands: list = []
    for ln in lines:
        if not ln.box:
            continue
        cy = _line_center_y(ln.box)
        if cy < y_min:
            continue
        text = ln.text.strip()
        if re.fullmatch(r"\d{1,2}", text):
            continue  # 张数
        if _is_denomination_label_line(text):
            continue
        if _looks_like_label_text(text):
            continue
        val = _parse_money(text)
        if val is None or val < 100 or val >= 50_000_000:
            continue
        # 无小数形态的超长整数多半是账号
        if val >= 1_000_000 and val == int(val) and not re.search(
            r"(?i)lkr|rs\.?|[.,]\d{2}", text
        ):
            continue
        conf = float(getattr(ln, "confidence", 0.0) or 0.0)
        cands.append((val, cy, conf, val in _COMMON_DENOMS))
    if not cands:
        return None
    non = [c for c in cands if not c[3]]
    if non:
        max_val = max(c[0] for c in non)
        top = [c for c in non if abs(c[0] - max_val) < 0.01]
        top.sort(key=lambda c: (-c[2], -c[1]))
        return top[0][0]
    # 仅有面额面值时：同一金额至少出现两次（行 AMOUNT + DEPOSIT 总额）才采纳，
    # 避免不完整面额表把单个 500.00 当成存款总额。
    counts = Counter(round(c[0], 2) for c in cands)
    dups = [v for v, n in counts.items() if n >= 2]
    if not dups:
        return None
    return max(dups)


def _money_near_label_right(lines, label_line, max_dy: float = 260.0) -> Optional[float]:
    """取 DEPOSIT AMOUNT 旁最近的金额。

    正拍：标签右侧（可略偏上下）；竖排：同列（近 x，值常在标签上方），
    有 NOTES/VALUE 面额表时优先非面额面值（避免 5,000 抢走 10,200）。
    """
    ly = _line_center_y(label_line.box)
    label_cx = _line_center_x(label_line.box)
    rx = max(p[0] for p in label_line.box) - 15
    tall = _is_tall_box(label_line.box)
    label_is_deposit = "deposit" in label_line.text.lower() and "amount" in _norm_label(
        label_line.text
    )
    skip_denoms = label_is_deposit and _has_notes_value_table(lines)
    cands: list = []
    for other in lines:
        if other is label_line:
            continue
        if re.search(r"(?i)account\s*number|customer\s*name|source\s*of\s*funds", other.text):
            continue
        val = _parse_money(other.text)
        if val is None:
            continue
        if val < 100 and val == int(val):
            continue
        if val >= 50_000_000 or (
            val >= 1_000_000
            and val == int(val)
            and not re.search(r"(?i)lkr|rs\.?|[.,]\d{2}", other.text)
        ):
            continue
        ox0 = min(p[0] for p in other.box)
        ocx = _line_center_x(other.box)
        ocy = _line_center_y(other.box)
        dy = abs(ocy - ly)
        dx = abs(ocx - label_cx)
        if tall:
            # 竖排同列：允许较大纵向间距（金额在标签上方）
            if dx > 150:
                continue
            if dy > max(max_dy * 3.0, 900.0):
                continue
            score = (dx, dy, -val)
        else:
            if ox0 < rx:
                continue
            if dy > max_dy:
                continue
            if skip_denoms and val in {20, 50, 100, 200, 500, 1000, 2000} and dy > 60:
                continue
            score = (dy, dx, -val)
        cands.append((score, val, val in _COMMON_DENOMS))
    if not cands:
        return None
    # 有面额表时：仅当存在「大于最大面额面值」的非面额候选（如 10,200 > 5,000）才优先它；
    # 真总额恰好等于面额（如只存一张 5000）时仍保留面额候选。
    if skip_denoms:
        non_denom = [c for c in cands if not c[2]]
        denom_vals = [c[1] for c in cands if c[2]]
        if non_denom and denom_vals:
            best_non = min(non_denom, key=lambda c: c[0])
            if best_non[1] > max(denom_vals) + 0.01:
                cands = non_denom
        elif non_denom and not denom_vals:
            cands = non_denom
    cands.sort(key=lambda c: c[0])
    return cands[0][1]


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


_KNOWN_LABEL_COMPACT = frozenset(
    {
        "narration",
        "mobileno",
        "accountnumber",
        "accountno",
        "customername",
        "sourceoffunds",
        "depositamount",
        "transaction",
        "transactionstatus",
        "terminalid",
        "trace",
        "date",
        "time",
        "notes",
        "value",
        "amount",
        "remarks",
        "branch",
        "status",
        "receiversaccountno",
        "receiversaccountnumber",
        "receiversbank",
        "receiversname",
        "sendersaccountno",
        "sendersaccountnumber",
        "sendersname",
        "sendersbank",
        "sendersbankname",
        "feescharges",
        "feesandcharges",
        "feecharges",
    }
)


def _is_near_known_label(value: str) -> bool:
    """识别 OCR 残缺/串字标签：IARRATION、IOBILE NO、IT AMOUNT、NSACTION STATUS 等。"""
    compact = _norm_label(value)
    if not compact or len(compact) < 4:
        return False
    if compact in _KNOWN_LABEL_COMPACT:
        return True
    # ACCOUNT NUMISE H / ACCOUNT NUMBE 等：以 accountnum 开头的残片
    if compact.startswith("accountnum") and len(compact) <= 16:
        return True
    for lab in _KNOWN_LABEL_COMPACT:
        if len(lab) < 4:
            continue
        # 前缀 1–2 个噪点字母：iarration / iobileno / itamount
        if compact.endswith(lab) and 0 < len(compact) - len(lab) <= 2:
            return True
        # 截断标签：nsactionstatus / erminalid / ranaction
        if lab.endswith(compact) and 0 < len(lab) - len(compact) <= 3:
            return True
        if abs(len(compact) - len(lab)) > 3:
            continue
        # 少量替换：iobileno ↔ mobileno；accountnumiseh ↔ accountnumber
        mismatch = sum(1 for a, b in zip(compact, lab) if a != b)
        mismatch += abs(len(compact) - len(lab))
        limit = 3 if len(lab) >= 10 else 2
        if mismatch <= limit:
            return True
    return False


def _looks_like_label_text(value: str) -> bool:
    """某些标签后紧跟的其实是另一个标签（如账户行 "Account No 138200..." 里
    "account" 匹配后得到 "no 138200..."）。此处用于剔除明显是标签残留的取值。"""
    low = value.lower().strip()
    words = [w for w in re.split(r"[\s:：.\-&]+", low) if w]
    if not words:
        return True
    if all(w in _FIELD_WORDS for w in words):
        return True  # 整值只由字段词组成，如 "Reference Number"
    if _is_near_known_label(value):
        return True
    # BOC/NSB 等：整行就是下一字段标题（Sender's Account No / Fees & Charges）
    if re.match(
        r"(?i)^(sender|receiver|beneficiary)'?s?\s+(account|name|bank)\b",
        low,
    ):
        return True
    if re.match(r"(?i)^fees?\s*&?\s*charges?$", low.replace(" ", "")) or re.match(
        r"(?i)^fees?\s*&?\s*charges?$", low
    ):
        return True
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


def _extract_union_ubgo_parties(lines) -> tuple[PartyOut, PartyOut]:
    """Union Bank UBgo：Paid From / Pay To / Beneficiary Name + 金额下收款行。"""
    payer, payee = PartyOut(), PartyOut()
    fields = _build_union_ubgo_fields(lines)
    if fields.get("Paid From"):
        payer.account = fields["Paid From"].strip()
    if fields.get("Pay To"):
        payee.account = _account_token(fields["Pay To"]) or fields["Pay To"].strip()
    if fields.get("Beneficiary Name"):
        payee.name = fields["Beneficiary Name"].strip(" .")
    if fields.get("Beneficiary Bank"):
        payee.bank = fields["Beneficiary Bank"]
    payer.bank = "Union Bank of Colombo PLC"
    payer.account_prefix, payer.account_last4 = _derive_account_parts(payer.account)
    payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)
    return payer, payee


def _extract_parties(lines, bank: Optional[str] = None) -> tuple[PartyOut, PartyOut]:
    if bank == "ipay":
        return _extract_ipay_parties(lines)
    if bank == "peoples_bank":
        return _extract_peoples_bank_parties(lines)
    if bank == "union_bank":
        return _extract_union_ubgo_parties(lines)
    if _is_boc_mobile_txn_details(lines):
        return _extract_boc_mobile_txn_parties(lines)
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
            is_deposit_amt_label = (
                "deposit amount" in low
                or _norm_label(ln.text).startswith("depositamount")
            )
            # 纯表头 NOTES/AMOUNT 跳过；DEPOSIT AMOUNT: 标签本身要去旁侧找总额
            if _looks_like_label_text(ln.text) and not is_deposit_amt_label:
                continue
            if is_deposit_amt_label:
                # 同行已带总额（DEPOSIT AMOUNT LKR 7,600.00）先解析；再旁侧同列几何
                inline = _parse_money_skip_denom(ln.text)
                near = _money_near_label_right(ordered, ln, max_dy=400.0)
                cands = [v for v in (inline, near) if v is not None and v >= 100]
                if cands:
                    den = [v for v in cands if v in _COMMON_DENOMS]
                    non = [v for v in cands if v not in _COMMON_DENOMS]
                    if (
                        _has_notes_value_table(ordered)
                        and non
                        and (not den or max(non) > max(den) + 0.01)
                    ):
                        amount = max(non)
                    elif inline is not None:
                        amount = inline
                    else:
                        amount = near
                    if amount is not None:
                        break
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
    # CDM 漏读 DEPOSIT AMOUNT 标签：从 NOTES/AMOUNT 带回收（如仅有 15.000.00）
    low_all = "\n".join(ln.text.lower() for ln in lines)
    is_cdm_amt = "cardless" in low_all or "deposit" in low_all or _has_notes_value_table(lines)
    if amount is None and is_cdm_amt and fee is None:
        amount = _recover_cdm_deposit_amount_from_notes_band(lines)
    # 现金存款（CDM）无 TOTAL 行，DEPOSIT AMOUNT 即总额。
    # 注意：若已识别到 fee（转账收据），不应把 total 设为 amount，
    # 否则 amount+fee != total 会产生误报。
    if total is None and amount is not None and fee is None:
        if "deposit" in low_all or "cardless" in low_all or _has_notes_value_table(lines):
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
    # OCR 常把标题截成 "Transaction confirmat..."
    if "confirmation" in t or "confirmat" in t or "payment details" in t:
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
    # OCR 把日期中的 1 读成 t/l： "02-1t-2026" / "02-1l-2026" → "02-11-2026"
    s = re.sub(r"(?i)(\d{1,2})[/.-](\d)[tl][/.-](\d{2,4})", r"\1/\g<2>1/\3", s)
    # 时间点号： "1.43 PM" / "1.43PM" -> "1:43 PM"
    s = re.sub(r"(?i)(\d{1,2})\.(\d{2})\s*(am|pm)", r"\1:\2 \3", s)
    # UBgo："02-Nov-2026 | 02:09 PM" / "02-Nov-202602:09PM"
    s = re.sub(r"\s*\|\s*", " ", s)
    s = re.sub(r"(?i)([A-Za-z]{3}-\d{4})(\d{1,2}:\d{2})", r"\1 \2", s)
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
        "%d-%b-%Y %I:%M %p",
        "%d-%b-%Y %I:%M:%S %p",
        "%d %b %Y %I:%M %p",
        "%d %b %Y %H:%M",
        "%d-%b-%Y",
        "%d %b %Y",
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
        # MM/DD 美式日期兜底（如 "10/27/2026"）：仅当上面的 DD/MM 解析失败（月 > 12）时命中
        "%m/%d/%Y %I:%M:%S %p",
        "%m-%d-%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p",
        "%m-%d-%Y %I:%M %p",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%m/%d/%y",
        "%m-%d-%y",
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
    # 必须先匹配 4 位年，且日/月模式加 (?<!\d)：否则 "2026/10/30 14:21:53"
    # 会被 `\d{1,2}/...` 吃成 "26/10/30 14:21:53" → 2030-10-26。
    datetime_pats = [
        r"(?<!\d)\d{4}[/-]\d{1,2}[/-]\d{1,2}[ T]\s*\d{1,2}:\d{2}(?::\d{2})?",
        r"(?<!\d)\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s*[,\s]?\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?",
        r"(?<!\d)\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?",
        r"(?<!\d)\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?",
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

    # 兜底：纯日期（同样先 4 位年，避免从 2026/10/30 里截出 26/10/30）
    for ln in lines:
        for pat in (
            r"(?<!\d)\d{4}[/-]\d{1,2}[/-]\d{1,2}(?!\d)",
            r"(?<!\d)\d{1,2}[/-]\d{1,2}[/-]\d{2,4}(?!\d)",
        ):
            m = re.search(pat, ln.text)
            if m:
                parsed = _parse_datetime(m.group(0))
                if parsed:
                    return parsed
    return None


def _find_datetime_raw(lines) -> Optional[str]:
    """提取无标签的纯日期时间行原文（如 "10.08.2026 , 06:45 PM"）。

    只匹配整行几乎就是日期时间的行，避免把带标签的时间行
    （如 "Date & Time : 09/10/2026 01:19 PM"）重复提取。
    """
    pats = [
        re.compile(
            r"(?<!\d)\d{4}[./-]\d{1,2}[./-]\d{1,2}\s*[,\s]?\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?<!\d)\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\s*[,\s]?\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?",
            re.IGNORECASE,
        ),
    ]
    for ln in _sorted_by_y(lines):
        text = ln.text.strip()
        for pat in pats:
            m = pat.search(text)
            if not m:
                continue
            rest = (text[: m.start()] + text[m.end() :]).strip(" :：.-,，")
            if rest:
                continue
            raw = m.group(0).strip()
            if _parse_datetime(raw):
                return raw
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

    # OCR 漏读 VALUE 列时：NOTES 数量行多于面额行（如 4、3 两行数量但只认出 500），
    # 按索引硬配对会把总额算少；此时放弃不完整明细，避免把 4×500 当成存款总额。
    if len(qty_rows) >= 2 and len(qty_rows) > len(denom_rows):
        return []

    breakdown: List[DenominationOut] = []
    used_qty = set()
    for y_d, denom in denom_rows:
        # 按 y 邻近配对 NOTES 数量，而不是按索引（行高不同时索引会错位）
        best_i = None
        best_dy = 55.0
        for i, (y_q, qty) in enumerate(qty_rows):
            if i in used_qty:
                continue
            dy = abs(y_q - y_d)
            if dy < best_dy:
                best_dy = dy
                best_i = i
        qty = qty_rows[best_i][1] if best_i is not None else 1
        if best_i is not None:
            used_qty.add(best_i)
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
    candidates = [c.strip(".,") for c in re.findall(r"[\d.,]+", text.replace(" ", ""))]
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


def _normalize_money_text(value: str) -> str:
    """OCR 常把金额小数点误读成冒号（如 "2,500:00"），还原为 "2,500.00"。"""
    if not value:
        return value
    return re.sub(r"(\d):(\d{1,2})(?!\d)", r"\1.\2", value)


def _normalize_money_fields(fields: dict) -> dict:
    """对金额类字段的值做冒号→小数点归一化。"""
    for k in list(fields.keys()):
        kl = k.lower()
        if any(w in kl for w in ("amount", "fee", "total", "debit", "charge")):
            fields[k] = _normalize_money_text(fields[k])
    return fields


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
    # iPay / HNB 须抢在 people's bank 之前：回执正文常带付款来源行 "People's Bank **"
    ("ipay", ("ipay", "www.ipay.lk")),
    ("hnb", ("hatton national", "this is an auto generated receipt")),
    ("ntb", ("nations trust", "nationstrust")),
    # Union Bank UBgo：须抢在 commercial_bank 之前（收款行常为 Commercial Bank）
    ("union_bank", ("unionbank", "union bank of colombo", "ubgo", "ubgp", "ubgo trnx")),
    ("peoples_bank", ("peoplespay", "people's pay", "people's bank", "people's")),
    ("commercial_bank", ("cardless deposit", "combank", "transfer within", "e-receipt", "bank reference number", "sender's account number", "beneficiary notified", "cash credit slip")),
    ("boc", ("bank of ceylon", "boc flex", "boc smartpay", "boc")),
    ("hnb", ("hnb",)),
    ("dfcc", ("dfcc bank", "dfcc")),
    ("nsb", ("nsb online banking", "nsb online payment", "nsb")),
    ("lb_finance", ("cash in mobile", "lb finance", "lbcim")),
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

_BOC_SMARTPAY_MARKERS = (
    "boc smartpay",
    "smartpay",
    "sender name:",
    "receiver name:",
    "receiver account & bank",
)


def _is_boc_app(lines) -> bool:
    """BOC 手机银行 "Transaction Successful" 版式（Account Information 卡片）。"""
    full = " ".join(ln.text for ln in lines).lower()
    return any(m in full for m in _BOC_APP_MARKERS)


def _is_boc_smartpay(lines) -> bool:
    """BOC SmartPay / LANKAQR 转账回执：Sender Name / Receiver Name / Invoice Number。"""
    full = " ".join(ln.text for ln in lines).lower()
    if "boc smartpay" in full or ("smartpay" in full and "bank of ceylon" in full):
        return True
    return "sender name:" in full and "receiver name:" in full


_PEOPLES_OTP_MARKERS = (
    "acknowledgement",
    "transfer description",
    "debit amount",
    "beneficiary mobile number",
    "one time transfer",
    "reference number",
    "beneficiary account number",
    "payment option",
)


def _is_peoples_otp(lines) -> bool:
    """People's Bank "One Time Transfer" 确认回执（ACKNOWLEDGEMENT），标签在上、值在下。

    有两版：带 Transfer Amount/Debit 的金额确认页，以及带 Status/Reference Number
    的成功回执页。后者 OCR 常把 Beneficiary Mobile Number 读坏，不能只靠它判定。
    """
    full = " ".join(ln.text for ln in lines).lower()
    if "acknowledgement" not in full:
        return False
    if any(m in full for m in ("transfer description", "debit amount", "beneficiary mobile number")):
        return True
    return "one time transfer" in full and any(
        m in full
        for m in ("reference number", "beneficiary account number", "payment option", "from account")
    )


_BOC_FLEX_MARKERS = (
    "flex online banking",
    "sender a/c details",
    "beneficiary a/c details",
)


def _is_boc_flex(lines) -> bool:
    """BOC Flex 网页版转账回执（Transaction Details / A/C Details 分区）。"""
    full = " ".join(ln.text for ln in lines).lower()
    return any(m in full for m in _BOC_FLEX_MARKERS)


def _is_boc_mobile_txn_details(lines) -> bool:
    """BOC 手机银行 Transaction Details：Receiver's/Sender's Account No + Fees & Charges。"""
    norms = {_norm_label(ln.text) for ln in lines}
    has_recv = any(n.startswith("receivers") for n in norms)
    has_send = any(n.startswith("senders") for n in norms)
    has_fees = any("feescharge" in n or n in {"feescharges", "feesandcharges"} for n in norms)
    if not (has_recv and has_send):
        return False
    full = " ".join(ln.text for ln in lines).lower()
    return "bank of ceylon" in full or has_fees or "remarks" in norms


def _looks_like_lak_artha_name(name: str) -> bool:
    """Lak Artha 户名容错：Kak Artha / L.a.k Artha / Lakatha 等 OCR 变体。"""
    if not name:
        return False
    low = name.lower()
    compact = re.sub(r"[^a-z]", "", low)
    if "lakartha" in compact or "lak artha" in low or "lak-artha" in low:
        return True
    # 首字母 L↔K 混淆
    if re.match(r"^[kl]akartha", compact):
        return True
    if compact in {"lakatha", "lakarth", "kakarth", "lakarthaservices", "kakarthapvt"}:
        return True
    return False


def _pick_boc_hero_transfer_amount(lines, fee: Optional[float]) -> Optional[float]:
    """从 OCR 行挑选 BOC Transaction Details 顶部主金额（排除手续费）。"""
    hero_amounts = []
    for ln in lines:
        if _looks_like_label_text(ln.text):
            continue
        low = ln.text.lower()
        if "fee" in low or "charge" in low:
            continue
        if re.fullmatch(r"\d{4}[./\-]\d{1,2}[./\-]\d{1,2}", ln.text.strip()):
            continue
        if not re.search(r"(?i)\blkr\b", ln.text) and not re.search(
            r"\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2}", ln.text
        ):
            continue
        if re.fullmatch(r"\d{8,}", re.sub(r"\s", "", ln.text)):
            continue
        m = _parse_money(ln.text)
        if m is not None and m >= 100:
            hero_amounts.append(m)
    if not hero_amounts:
        return None
    hero_amounts.sort(reverse=True)
    for cand in hero_amounts:
        if fee is not None and abs(cand - fee) < 0.01:
            continue
        return cand
    return None


def _boc_sender_name_quality(name: str) -> float:
    """越高越好：偏好全大写整词，惩罚「m R e s」这类单字母碎读。"""
    if not name:
        return -1.0
    letters = [c for c in name if c.isalpha()]
    if not letters:
        return 0.0
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    toks = [t for t in re.split(r"\s+", name) if t]
    singles = sum(1 for t in toks if len(re.sub(r"[^A-Za-z]", "", t)) == 1)
    return upper_ratio * 2.0 + min(len(name), 48) * 0.02 - singles * 0.35


def _repair_boc_sender_name(fields: dict, lines) -> None:
    """Sender's Name 被低置信度碎读时，优先取同行高置信全大写姓名。"""
    cur = fields.get("Sender's Name") or ""
    best = None
    for ln in lines:
        raw = ln.text.strip()
        # "Sender's NameMR E S M HI SENEVIRATNE" / "Sender's Name  MR ..."
        m = re.match(
            r"(?i)^\s*sender'?s?\s*name\s*[:：]?\s*(.+)$",
            raw,
        )
        if not m:
            continue
        name = _clean(m.group(1))
        if not name or _looks_like_label_text(name) or len(name) < 6:
            continue
        conf = float(getattr(ln, "confidence", 0.0) or 0.0)
        score = conf + _boc_sender_name_quality(name)
        if best is None or score > best[0]:
            best = (score, name)
    if best and (
        not cur or _boc_sender_name_quality(best[1]) > _boc_sender_name_quality(cur) + 0.15
    ):
        fields["Sender's Name"] = best[1]


_CDM_MARKERS = ("cardless deposit",)
_CDM_HEADER_NORMS = {"date", "time", "terminalid", "trace", "depositamount"}


def _is_cash_deposit(lines) -> bool:
    """Commercial Bank CDM 无卡存款凭条（CARDLESS DEPOSIT）。"""
    full = " ".join(ln.text for ln in lines).lower()
    if any(m in full for m in _CDM_MARKERS):
        return True
    # OCR 漏读 CARDLESS DEPOSIT 时：并排表头 + DEPOSIT AMOUNT 仍可判定
    headers = {
        _norm_label(ln.text)
        for ln in lines
        if _norm_label(ln.text) in _CDM_HEADER_NORMS
    }
    return len(headers) >= 4 and "deposit" in full


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


def _is_peoples_pay_layout(lines) -> bool:
    """无 PEOPLE'S 字样时，凭版式判定 People's Pay 确认/回执页。

    强特征组合：Pay to + Trace No + Amount(LKR)/Total debit；
    常伴截断标题 Transaction confirmat... 或 Remarks Max 16 characters。
    """
    full = " ".join(ln.text for ln in lines).lower()
    if any(
        m in full
        for m in (
            "ipay",
            "www.ipay.lk",
            "vishwa",
            "smartpay",
            "cardless deposit",
            "acknowledgement",
            "one time transfer",
        )
    ):
        return False
    norms = {_norm_label(ln.text) for ln in lines}
    has_pay_to = any(ln.text.strip().lower() == "pay to" for ln in lines)
    has_trace = "traceno" in norms
    has_amount = bool(norms & {"amountlkr", "totaldebitamountlkr", "feeamountlkr"})
    has_title = "confirmat" in full or "successfully completed" in full
    has_remarks_hint = "max 16 characters" in full
    if has_pay_to and has_trace and has_amount:
        return True
    if has_pay_to and has_amount and (has_title or has_remarks_hint):
        return True
    return False


def _detect_bank(lines) -> Optional[str]:
    full = " ".join(ln.text for ln in lines).lower()
    # 抢在 "people's bank" 之前：该版式底部会显示付款来源银行（如 People's Bank）。
    if _is_boc_smartpay(lines) or _is_boc_app(lines):
        return "boc"
    if _is_hnb_app_receipt(lines):
        return "hnb"
    for bank, markers in _BANK_MARKERS:
        for m in markers:
            if m == "bank of ceylon":
                # 仅命中非 "commercial bank of ceylon" 的独立 "bank of ceylon"（区分 BOC 与 ComBank）
                if re.search(r"(?<!commercial )bank of ceylon", full):
                    return bank
                continue
            if m in full:
                return bank
    # Logo / 行名 OCR 漏读时，用 People's Pay 版式兜底
    if _is_peoples_pay_layout(lines):
        return "peoples_bank"
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


def _clean_person_or_org_name(text: str) -> Optional[str]:
    """从 OCR 行抠出付款/收款人姓名（去掉行首 O/0 噪点）。"""
    t = re.sub(r"^[O0\s]+", "", (text or "").strip()).strip(" .")
    if len(t) < 5:
        return None
    if re.search(r"(?i)\bbank\b|lkr|receipt|amount|trace|status", t):
        return None
    if not re.search(r"[A-Za-z]{2,}", t):
        return None
    if len(re.findall(r"[A-Za-z]", t)) < 6:
        return None
    return _clean(t)


def _masked_or_digit_account(text: str) -> Optional[str]:
    """People's Pay 账号：纯数字或带 x/* 掩码（如 149200xxxxxxx84）。"""
    t = (text or "").strip()
    if re.fullmatch(r"\d{8,14}", t):
        return t
    if re.fullmatch(r"[\d*xX]{8,20}", t):
        return t
    return _account_token(t)


def _is_peoples_pay_sinhala_layout(lines) -> bool:
    """僧伽罗语 People's Pay：无英文 Pay from/to，但有 People's Bank + Commercial Bank + 金额。"""
    full = " ".join(ln.text for ln in lines).lower()
    if "people's bank" not in full and "peoples bank" not in full:
        return False
    if "commercial bank" not in full:
        return False
    # 排除 One Time Transfer / 英文 People's Pay
    if any(
        m in full
        for m in ("acknowledgement", "one time transfer", "pay from", "pay to", "trace no")
    ):
        return False
    if any(ln.text.strip().lower() in {"pay from", "pay to"} for ln in lines):
        return False
    has_acct = any(_masked_or_digit_account(ln.text) for ln in lines)
    has_money = any(
        (_parse_money(ln.text) or 0) >= 20
        for ln in lines
        if re.search(r"\d+[.,]\d{2}", ln.text)
    )
    return has_acct and has_money


def _extract_peoples_pay_positional(lines) -> tuple[PartyOut, PartyOut, dict]:
    """英文标签缺失时，按 People's Bank / Commercial Bank 锚点与右列金额位置兜底。"""
    payer, payee = PartyOut(), PartyOut()
    fields: dict = {}
    ordered = _sorted_by_y(lines)

    peoples_ln = None
    commercial_ln = None
    for ln in ordered:
        t = ln.text.strip()
        if peoples_ln is None and re.search(r"(?i)people'?s\s*bank", t):
            peoples_ln = ln
            payer.bank = "People's Bank"
            fields["Payer Bank"] = payer.bank
        elif commercial_ln is None and re.search(r"(?i)commercial\s*bank", t):
            commercial_ln = ln
            payee.bank = re.sub(r"\s+", " ", t).strip(" .")
            fields["Payee Bank"] = payee.bank

    if peoples_ln is not None:
        py = _line_center_y(peoples_ln.box)
        for ln in reversed([x for x in ordered if _line_center_y(x.box) < py - 5]):
            name = _clean_person_or_org_name(ln.text)
            if name:
                payer.name = name
                fields["Payer Name"] = name
                break
        limit_y = _line_center_y(commercial_ln.box) if commercial_ln is not None else py + 500
        for ln in ordered:
            y = _line_center_y(ln.box)
            if y <= py + 5 or y >= limit_y:
                continue
            acc = _masked_or_digit_account(ln.text)
            if acc and not payer.account:
                payer.account = acc
                fields["Payer Account No"] = acc
            if ln.text.strip().upper() == "LKR":
                fields["Account Currency"] = "LKR"

    if commercial_ln is not None:
        cy = _line_center_y(commercial_ln.box)
        floor = _line_center_y(peoples_ln.box) if peoples_ln is not None else 0.0
        for ln in reversed([x for x in ordered if floor + 30 < _line_center_y(x.box) < cy - 5]):
            name = _clean_person_or_org_name(ln.text)
            if name:
                payee.name = name
                fields["Payee Name"] = name
                break
        for ln in ordered:
            y = _line_center_y(ln.box)
            if y <= cy + 5:
                continue
            acc = _masked_or_digit_account(ln.text)
            if acc and re.fullmatch(r"\d{8,14}", acc):
                payee.account = acc
                fields["Payee Account No"] = acc
                break

    # 金额：优先短行（纯金额），按 y 依次为 Amount / Fee / Total
    money_rows = []
    for ln in ordered:
        if not re.search(r"\d+[.,]\d{2}", ln.text):
            continue
        amt = _parse_money(ln.text)
        if amt is None or amt < 20:
            continue
        non_num = re.sub(r"[\d,.\sLKRRkrs]", "", ln.text)
        score = 0 if len(non_num) <= 4 else 1
        money_rows.append((score, _line_center_y(ln.box), amt))
    money_rows.sort()
    # 同 y 去重后按出现顺序
    picked = []
    for _, y, amt in money_rows:
        if picked and abs(y - picked[-1][0]) < 40 and abs(amt - picked[-1][1]) < 0.01:
            continue
        picked.append((y, amt))
    picked.sort(key=lambda t: t[0])
    if picked:
        fields["Amount (LKR)"] = f"{picked[0][1]:,.2f}"
    if len(picked) >= 2:
        fields["Fee Amount (LKR)"] = f"{picked[1][1]:,.2f}"
    if len(picked) >= 3:
        fields["Total debit amount (LKR)"] = f"{picked[2][1]:,.2f}"
    elif len(picked) >= 2:
        fields["Total debit amount (LKR)"] = f"{picked[0][1] + picked[1][1]:,.2f}"

    payer.account_prefix, payer.account_last4 = _derive_account_parts(payer.account)
    payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)
    return payer, payee, fields


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

    # 僧伽罗语版：英文分区/标签缺失时按锚点位置兜底（勿污染 OTP 等其它 People's 版式）
    if _is_peoples_pay_sinhala_layout(lines):
        pos_payer, pos_payee, _ = _extract_peoples_pay_positional(lines)
        if not payer.name:
            payer.name = pos_payer.name
        if not payer.account:
            payer.account = pos_payer.account
        if not payer.bank or payer.bank.upper() in {"PLC", "BANK"}:
            payer.bank = pos_payer.bank or payer.bank
        if not payee.name:
            payee.name = pos_payee.name
        if not payee.account:
            payee.account = pos_payee.account
        if not payee.bank:
            payee.bank = pos_payee.bank

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


def _extract_boc_mobile_txn_parties(lines) -> tuple[PartyOut, PartyOut]:
    """BOC 手机 Transaction Details：Receiver's* / Sender's* 扁平字段回填收付款方。"""
    payer, payee = PartyOut(), PartyOut()
    fields = _build_label_fields(lines, _BOC_MOBILE_TXN_LABELS)
    payee.account = fields.get("Receiver's Account No")
    payee.bank = fields.get("Receiver's Bank")
    payee.name = fields.get("Receiver's Name")
    payer.account = fields.get("Sender's Account No")
    payer.name = fields.get("Sender's Name")
    payer.bank = fields.get("Sender's Bank Name") or "Bank of Ceylon"
    if payee.name and _looks_like_lak_artha_name(payee.name):
        payee.name = "Lak Artha (Pvt) Ltd"
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

# People's Bank "One Time Transfer" 确认回执（ACKNOWLEDGEMENT）：标签在上、值在下。
_PEOPLES_OTP_LABELS = (
    "Status",
    "Reference Number",
    "From Account",
    "Payment Option",
    "Beneficiary Account Bank",
    "Beneficiary Branch Name",
    "Beneficiary Account Number",
    "Beneficiary Name",
    "Email Address",
    "Beneficiary Mobile Number",
    "Transfer Amount",
    "Fee & Charges",
    "Debit Amount",
    "Total Debit Amount",
    "Transfer On",
    "Transfer Description",
)

# NSB Online Banking 回执：三栏（Source / Receiver / Transaction Details），左标右值。
_NSB_SOURCE_LABELS = (
    "Account No.",
    "Account Type",
    "Transfer Type",
)
_NSB_RECEIVER_LABELS = (
    "Account No.",
    "Beneficiary Name",
    "Benefi. Bank Name",
    "Benefi. Branch Name",
    "Benefi. Account Type",
)
_NSB_TXN_LABELS = (
    "Transaction Reference",
    "Transaction Date/Time",
    "Transfer Amount",
    "Fee & Charges",
    "Total Amount",
    "Transaction Type",
    "Status",
    "Payment Type",
    "Beneficiary Reference",
    "Your Reference",
    "Transaction Purpose",
)

_E_RECEIPT_LABELS = (
    "Bank Reference Number",
    "Sender's Account Number",
    "Sender's Name",
    "Transfer Amount",
    "Transfer Currency",
    "Beneficiary Name",
    "Beneficiary's Account Currency",
    "Beneficiary Account Number",
    "Beneficiary's Account Number",
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

_SAMPATH_VISHWA_LABELS = (
    "Status",
    "Transaction ID",
    "Date & Time",
    "Source Account Number",
    "Source Account",
    "Amount",
    "Beneficiary Name",
    "Beneficiary Account No.",
    "Beneficiary Account",
    "Beneficiary Remarks",
    "Beneficiary Bank",
    "Destination Bank",
)

_BOC_SMARTPAY_LABELS = (
    "Sender Name",
    "Receiver Name",
    "Source Account",
    "Receiver Account & Bank",
    "Transaction Amount",
    "Service Charge",
    "Transaction Date",
    "Transaction Time",
    "Transaction Status",
    "Invoice Number",
    "Description",
)

_HNB_APP_LABELS = (
    "Transaction Reference",
    "Payment Reference",
    "Date/ Time",
    "Date/Time",
    "Receiver reference",
    "Receiver Reference",
)

# Union Bank UBgo Fund Transfer Receipt：同行 Label: Value + Amount 上下布局
_UNION_UBGO_LABELS = (
    "Transaction Status",
    "Status",
    "Paid From",
    "Pay To",
    "Branch",
    "Beneficiary Name",
    "Service Charge",
    "Remarks",
    "Date & Time",
    "Reference Number",
    "Amount",
)

_NSB_MOBILE_LABELS = (
    "Transaction ID",
    "Transaction Date/Time",
    "Transaction Type",
    "Transaction Amount",
    "Bank Charges",
    "Status",
    "Sender's Name",
    "Source Bank Name",
    "Source Bank Account Number",
    "Beneficiary Name",
    "Destination Bank",
    "Destination Account No",
    "Destination Account No.",
    "Remarks",
)

_BOC_FLEX_LABELS = (
    "Transaction Amount",
    "Transaction Date & Time",
    "Transaction ID",
    "Charges & Fee",
    "Remarks",
    "Transaction Status",
    "Account Number",
    "Sender's Name",
    "Sender's Bank",
    "Account No",
    "Beneficiary Name",
    "Beneficiary Bank",
)

# BOC 手机 App Transaction Details（竖拍常见）：Receiver/Sender 字段 + Fees & Charges
_BOC_MOBILE_TXN_LABELS = (
    "Receiver's Account No",
    "Receiver's Bank",
    "Receiver's Name",
    "Sender's Account No",
    "Sender's Name",
    "Sender's Bank Name",
    "Remarks",
    "Fees & Charges",
)

_CDM_LABELS = (
    "TRANSACTION",
    "ACCOUNT NUMBER",
    "CUSTOMER NAME",
    "NARRATION",
    "MOBILE NO.",
    "SOURCE OF FUNDS",
    "DEPOSIT AMOUNT",
    "TRANSACTION STATUS",
    "TRACE",
    "DATE",
    "TIME",
    "TERMINAL ID",
)

_LB_FINANCE_LABELS = (
    "From",
    "From Bank",
    "From Account",
    "To Bank",
    "To Account",
    "Beneficiary Name",
    "Amount",
    "Remarks",
    "Transaction Date & Time",
    "Reference No.",
    "Status",
)

_IPAY_LABELS = (
    "Transaction Date",
    "Transaction ID",
    "Type",
    "From",
    "To",
    "Recipient",
    "Remarks",
    "Status",
    "Amount",
)


def _norm_label(s: str) -> str:
    """标签归一化：去非字母数字，并还原常见 OCR 字母数字混淆（0→O、1→I）。"""
    s = re.sub(r"[^a-z0-9]", "", s.lower())
    s = s.replace("0", "o").replace("1", "i")
    # Vishwa 等版式常见 beneficiary 拼写损坏
    for bad in ("beneficlary", "beneflciary", "beneticlary", "benefciary"):
        s = s.replace(bad, "beneficiary")
    # CDM「DEPOSIT AMOUNT」常被读成 AMCUNT / AMOUNI
    s = s.replace("amcunt", "amount").replace("amouni", "amount").replace("arnount", "amount")
    return s


def _build_label_fields(lines, labels, same_row: bool = False) -> dict:
    """按白名单标签，提取「单据原始英文字段名 -> 原文值」的扁平映射。

    兼容两种版式：
    * 两栏「左标签 / 右值 / 下方」（如 Commercial Bank e-Receipt、People's Pay）；
    * 单栏「Label Value」或「Label: Value」同行。
    匹配时忽略空格/标点，容忍 OCR 的 "( LKR )"、"Date &Time" 等变体。
    same_row=True 时仅取标签同一水平带右侧的值，不做「下方取值」兜底，
    用于值恒与标签同行、空值字段不误取下一字段值的版式（如 NSB）。
    """
    wanted = {_norm_label(lbl): lbl for lbl in labels}
    fields: dict = {}
    ordered = _sorted_by_y(lines)
    # 几乎同行且横向分开的 ≥2 个白名单标签（如 CDM 的 DATE/TIME/TERMINAL ID）
    # 为并排表头，值在各自正下方；此时禁用右侧取值，否则更右一列的值会因垂直重叠
    # 更大被 _value_line_to_right / _right_column_line 抢给左侧标签。
    # y/x 阈值须收紧：纵向两栏版式（LB Finance / NSB）相邻标签 dy 常约 40–50px，
    # 不能把它们误判成并排表头。
    header_row_labels = set()
    wanted_label_lines = [
        ln for ln in ordered if wanted.get(_norm_label(ln.text)) is not None
    ]
    for a_i, a in enumerate(wanted_label_lines):
        ay = _line_center_y(a.box)
        ax = _line_center_x(a.box)
        for b in wanted_label_lines[a_i + 1 :]:
            if abs(_line_center_y(b.box) - ay) > 30.0:
                continue
            if abs(_line_center_x(b.box) - ax) < 80.0:
                continue  # 同列上下堆叠，不是并排表头
            header_row_labels.add(id(a))
            header_row_labels.add(id(b))
    def _accept_amountish(key: str, value: str) -> Optional[str]:
        """金额类标签拒绝邻字段/账号串，必要时改找近旁金额。"""
        if "amount" not in _norm_label(key):
            return value
        if re.search(r"(?i)source\s*of\s*funds|account\s*number|customer\s*name|terminal|trace", value):
            return None
        if _norm_label(value) == "lkr":
            return None
        amt = _parse_money(value)
        if amt is None or amt >= 50_000_000:
            return None
        if amt < 100 and amt == int(amt) and not re.search(r"[.,]\d{2}", value):
            return None
        return value

    def _accept_side_value(key: str, label_ln, side_line) -> Optional[str]:
        side_value = _collect_column_block(ordered, side_line)
        if not side_value or _looks_like_label_text(side_value):
            return None
        if _norm_label(side_value) == "lkr" and "amount" in _norm_label(key):
            money = _money_near_label_right(ordered, label_ln)
            if money is not None:
                return f"{money:,.2f}"
            return None
        return _accept_amountish(key, side_value)

    def _accept_below_value(key: str, below: str) -> Optional[str]:
        if not below or _looks_like_label_text(below):
            return None
        below_norm = _norm_label(below)
        # 下方是另一个标签（或标签+值，如空值字段 "NARRATION:" 下接 "MOBILE NO. :"），
        # 不应作为当前字段的值
        if below_norm in wanted or any(below_norm.startswith(n) for n in wanted):
            return None
        return _accept_amountish(key, below)

    # 两栏：左标签、右值 / 下方取值（标签独占一行）
    for i, ln in enumerate(ordered):
        key = wanted.get(_norm_label(ln.text))
        if key is None or key in fields:
            continue
        adjacent_header = id(ln) in header_row_labels
        tall = _is_tall_box(ln.box)
        value = None
        if adjacent_header:
            # 并排表头默认取下方（CDM DATE/TIME）。竖拍手机 UI 值在标签上方。
            if not same_row and tall:
                above_ln = _value_line_above(i, ordered, ln)
                if above_ln is not None and _norm_label(above_ln.text) not in wanted:
                    merged = _merge_x_adjacent_fragments(ordered, above_ln, set(wanted))
                    value = _accept_amountish(key, merged) if merged else None
            if value is None and not same_row:
                value = _accept_below_value(key, _value_below(i, ordered, ln) or "")
        elif tall:
            # 竖排 DEPOSIT AMOUNT：同列金额常在标签上方，优先几何取总额，避免面额 5000 串位
            if value is None and (
                _norm_label(key) == "depositamount"
                or ("deposit" in key.lower() and "amount" in key.lower())
            ):
                money = _money_near_label_right(ordered, ln, max_dy=400.0)
                if money is not None:
                    value = f"{money:,.2f}"
            # 竖拍：先左侧（CDM DATE/TIME/TERMINAL）。TIME 同带右侧真值须先于正下方。
            # 手机竖拍 UI（BOC Transaction Details）原左值转到标签正上方，above 先于 below。
            left = _value_line_to_left(i, ordered, ln)
            if (
                value is None
                and left is not None
                and _norm_label(left.text) not in wanted
                and not _looks_like_label_text(left.text)
            ):
                value = _accept_side_value(key, ln, left)
            prefer_right_before_below = _norm_label(key) == "time"
            if value is None and not same_row and prefer_right_before_below:
                for cand in (
                    _value_line_to_right(i, ordered, ln),
                    _right_column_line(i, ordered, ln),
                ):
                    if cand is None or _norm_label(cand.text) in wanted:
                        continue
                    value = _accept_side_value(key, ln, cand)
                    if value:
                        break
            if value is None and not same_row:
                above_ln = _value_line_above(i, ordered, ln)
                if above_ln is not None and _norm_label(above_ln.text) not in wanted:
                    merged = _merge_x_adjacent_fragments(ordered, above_ln, set(wanted))
                    value = _accept_amountish(key, merged) if merged else None
            if value is None and not same_row:
                value = _accept_below_value(key, _value_below(i, ordered, ln) or "")
            if value is None and not same_row and not prefer_right_before_below:
                for cand in (
                    _value_line_to_right(i, ordered, ln),
                    _right_column_line(i, ordered, ln),
                ):
                    if cand is None or _norm_label(cand.text) in wanted:
                        continue
                    value = _accept_side_value(key, ln, cand)
                    if value:
                        break
            # 竖排 DEPOSIT AMOUNT：下方金额可能超出默认 dy，或右侧被 SOURCE OF FUNDS 挡住
            if value is None and "amount" in _norm_label(key):
                money = _money_near_label_right(ordered, ln)
                if money is None:
                    label_bottom = max(p[1] for p in ln.box)
                    label_cx = _line_center_x(ln.box)
                    best_m = None
                    for other in ordered:
                        oy0 = min(p[1] for p in other.box)
                        if oy0 < label_bottom - 10 or oy0 - label_bottom > 550:
                            continue
                        if abs(_line_center_x(other.box) - label_cx) > 200:
                            continue
                        mval = _parse_money(other.text)
                        if mval is None or mval < 100 or mval >= 50_000_000:
                            continue
                        score = (oy0 - label_bottom, abs(_line_center_x(other.box) - label_cx))
                        if best_m is None or score < best_m[0]:
                            best_m = (score, _clean(other.text))
                    if best_m:
                        value = best_m[1]
                else:
                    value = f"{money:,.2f}"
        else:
            for cand in (
                _value_line_to_right(i, ordered, ln),
                _right_column_line(i, ordered, ln) if not same_row else None,
            ):
                if cand is None or _norm_label(cand.text) in wanted:
                    continue
                value = _accept_side_value(key, ln, cand)
                if value:
                    break
            if value is None and not same_row:
                value = _accept_below_value(key, _value_below(i, ordered, ln) or "")
        if value:
            fields[key] = value
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


def _right_column_buckets(lines, labels) -> dict:
    """两栏版式（左列标签 / 右列值，值可多行）通用归属。

    右列值行按其 y 中心与左列标签行的 y 中心做最近邻归属（阈值 80px），
    从而把多行值（如 iPay 的 "From" 下姓名+银行、"To" 下银行+账号）分到各自标签，
    避免通用 `_collect_column_block` 把所有右列行串进一个字段。
    """
    label_keys = {_norm_label(lbl): lbl for lbl in labels}
    ordered = _sorted_by_y(lines)
    label_lines: list = []
    seen = set()
    for ln in ordered:
        k = label_keys.get(_norm_label(ln.text))
        if k and k not in seen:
            seen.add(k)
            label_lines.append((k, ln))
    buckets = {k: [] for k, _ in label_lines}
    for ln in ordered:
        text = ln.text.strip()
        if _norm_label(text) in label_keys:
            continue  # 标签行本身不作为值
        ox = min(p[0] for p in ln.box)
        if ox < 400:
            continue  # 左列 / 居中内容（页眉、页脚）不是字段值
        oy = _line_center_y(ln.box)
        best_k = None
        best_d = 81.0
        for k, lbl in label_lines:
            d = abs(oy - _line_center_y(lbl.box))
            if d < best_d:
                best_d = d
                best_k = k
        if best_k is None:
            continue
        val = _clean(text)
        if not val or _looks_like_label_text(val):
            continue
        buckets[best_k].append((oy, val, ln.confidence))
    result = {}
    for k, items in buckets.items():
        items.sort(key=lambda t: t[0])
        # 同一视觉行的多个 OCR 变体（0↔O、冒号↔小数点、空格差异等）按 y 去重，
        # 保留置信度最高者；不同 y 的行（多行值）保留并拼接。
        deduped = []
        for oy, val, conf in items:
            if deduped and abs(oy - deduped[-1][0]) <= 15.0:
                if conf > deduped[-1][2]:
                    deduped[-1] = (oy, val, conf)
            else:
                deduped.append((oy, val, conf))
        result[k] = [v for _, v, _ in deduped]
    return result


def _build_ipay_fields(lines) -> dict:
    buckets = _right_column_buckets(lines, _IPAY_LABELS)
    fields = {k: " ".join(v) for k, v in buckets.items() if v}
    # Amount 常无标签，仅 "Rs.7,575.00" 独立行
    if not any("amount" in k.lower() for k in fields):
        for ln in _sorted_by_y(lines):
            m = re.search(r"(?i)\bRs\.?\s*([\d,]+(?:\.\d{2})?)", ln.text)
            if m:
                fields["Amount"] = f"Rs.{m.group(1)}"
                break
    return fields


def _looks_like_terminal_id_value(value: str) -> bool:
    """CDM TIME 误取 TERMINAL ID 时的形态：如 RWELAWA2HT / RMATCIT2HT。"""
    compact = re.sub(r"\s+", "", value or "")
    if re.search(r"\d{1,2}:\d{2}", compact):
        return False
    if re.search(r"(?i)bank|commercial|ceylon|deposit", compact):
        return False
    return bool(re.match(r"(?i)^R?[A-Z]{3,}\d*[A-Z]*HT$", compact))


def _normalize_cdm_time(value: str) -> Optional[str]:
    """归一化 CDM TIME：19.11 / 19:11 → 19:11；拒绝日期误读 01:11.26 / 01/11/26。"""
    v = _clean(value or "")
    if not v:
        return None
    # 日期或「时:分.年片段」不能当时间
    if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", v):
        return None
    if re.search(r"\d{1,2}:\d{2}\.\d{2}", v):
        return None
    m = re.match(r"^\s*([01]?\d|2[0-3])[.:\- ]([0-5]\d)\s*$", v)
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def _is_plausible_cdm_field_value(key: str, value: str) -> bool:
    """CDM 强类型字段取值校验，拒绝银行名/邻字段串位。"""
    v = _clean(value or "")
    if not v or _looks_like_label_text(v):
        return False
    kn = _norm_label(key)
    if kn == "date":
        return bool(re.search(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}", v)) and not re.search(
            r"(?i)bank|commercial|trace|terminal", v
        )
    if kn == "time":
        return _normalize_cdm_time(v) is not None
    if kn == "terminalid":
        return _looks_like_terminal_id_value(v)
    if kn == "trace":
        return bool(re.match(r"^\d{3,6}$", v)) and not re.search(r"[/.\-]", v)
    if kn == "transactionstatus":
        if re.search(r"(?i)source\s*of\s*funds|unknown", v):
            return False
        return bool(re.search(r"(?i)\b(successful|success|failed|fail|rejected)\b", v))
    if kn == "accountnumber":
        digits = re.sub(r"\s+", "", v)
        if not re.fullmatch(r"\d{8,14}", digits):
            return False
        # 00 开头的 8 位多半是 10 位账号截断（1001096962 → 00109696）
        if len(digits) < 10 and digits.startswith("00"):
            return False
        return True
    if kn == "transaction":
        if re.search(r"(?i)commercial\s*bank|union\s*bank|\(il\)|deposit\s*amount|source\s*of", v):
            return False
        # 仅接受交易类型，拒绝单独的 AMOUNT / 面额表头
        return bool(re.search(r"(?i)cardless\s*deposit|cash\s*deposit", v)) or bool(
            re.fullmatch(r"(?i)deposit", v)
        )
    if kn == "customername":
        if re.search(r"(?i)narration|mobile|account|bank|source", v):
            return False
        return len(re.findall(r"[A-Za-z]", v)) >= 6
    if kn == "mobileno":
        if re.search(r"(?i)narration|account|customer|bank", v):
            return False
        if v in {"-", "–", "—"}:
            return True
        digits = re.sub(r"\D", "", v)
        # 拒账号串位：无 +94/07 前缀的 8–14 位纯数字
        if re.fullmatch(r"\d{8,14}", digits) and not (
            re.search(r"(?:\+|94)", v) or digits.startswith(("07", "01"))
        ):
            return False
        if digits.startswith("0") and 9 <= len(digits) <= 11:
            return True
        return bool(re.search(r"(?:\+|94)", v) and len(digits) >= 9)
    if kn == "depositamount":
        amt = _parse_money(v)
        # 账号常被误解析成超大金额；面额表张数等纯小整数也不当存款额
        if amt is None or not (0 < amt < 50_000_000):
            return False
        if amt < 100 and amt == int(amt) and not re.search(r"[.,]\d{2}", v):
            return False
        return bool(re.search(r"(?i)lkr|rs\.?|[.,]\d{2}", v) or amt >= 100)
    return True


def _extract_cdm_typed_substring(key: str, text: str) -> Optional[str]:
    """从一行 OCR 文本中抠出符合 CDM 字段类型的子串。"""
    kn = _norm_label(key)
    if kn == "date":
        m = re.search(r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}", text)
        return m.group(0) if m else None
    if kn == "time":
        return _normalize_cdm_time(text)
    if kn == "terminalid":
        for tok in re.findall(r"[A-Za-z0-9]{6,}", text):
            if _looks_like_terminal_id_value(tok):
                return tok.upper()
        return None
    if kn == "trace":
        # 日期残片 D0710/26... 里的 0710 不是 TRACE；660f6 也不是
        if re.search(r"\d{1,2}[/.\-]\d{1,2}([/.\-]\d{2,4})?", text):
            return None
        if re.search(r"(?i)d\d{3,4}/\d{2}", text):
            return None
        m = re.search(r"(?<![A-Za-z0-9])(\d{3,6})(?![A-Za-z0-9])", text)
        return m.group(1) if m else None
    if kn == "transactionstatus":
        m = re.search(r"(?i)\b(successful|success|failed|fail|rejected)\b", text)
        return m.group(0).upper() if m else None
    if kn == "accountnumber":
        # 同屏多段数字时取最长且非 00 截断
        best = None
        for m in re.finditer(r"(?<!\d)(\d{8,14})(?!\d)", text):
            acct = m.group(1)
            if acct in {"500000", "100000", "200000", "1000000"}:
                continue
            if len(acct) < 10 and acct.startswith("00"):
                continue
            score = (len(acct), 0 if acct.startswith("00") else 1)
            if best is None or score > best[0]:
                best = (score, acct)
        return best[1] if best else None
    if kn == "transaction":
        m = re.search(r"(?i)cardless\s*deposit", text)
        return "CARDLESS DEPOSIT" if m else None
    if kn == "customername":
        if re.search(r"(?i)narration|mobile|account", text):
            return None
        name = _clean_person_or_org_name(text)
        return name
    return None


def _pick_cdm_typed_near(idx: int, ordered, label_line, key: str) -> Optional[str]:
    """在标签附近按左/同带右/下优先级挑选通过类型校验的值。

    TIME 在竖拍时值与标签同行，须优先 y 重叠的左右候选，避免下方日期误读
    （01:11.26）抢走 19:11。
    """
    kn = _norm_label(key)
    label_cx = _line_center_x(label_line.box)
    label_cy = _line_center_y(label_line.box)
    label_left = min(p[0] for p in label_line.box)
    label_right = max(p[0] for p in label_line.box)
    label_bottom = max(p[1] for p in label_line.box)
    ly0 = min(p[1] for p in label_line.box)
    ly1 = max(p[1] for p in label_line.box)
    best = None
    for j, other in enumerate(ordered):
        if j == idx:
            continue
        raw = other.text.strip()
        if not raw:
            continue
        text = raw
        if not _is_plausible_cdm_field_value(key, text):
            extracted = _extract_cdm_typed_substring(key, raw)
            if not extracted or not _is_plausible_cdm_field_value(key, extracted):
                continue
            text = extracted
        if kn == "time":
            norm_t = _normalize_cdm_time(text)
            if not norm_t:
                continue
            text = norm_t
        ox0 = min(p[0] for p in other.box)
        ox1 = max(p[0] for p in other.box)
        oy0 = min(p[1] for p in other.box)
        oy1 = max(p[1] for p in other.box)
        ocx = _line_center_x(other.box)
        ocy = _line_center_y(other.box)
        y_overlap = max(0.0, min(ly1, oy1) - max(ly0, oy0))
        conf = -float(getattr(other, "confidence", 0.0) or 0.0)
        # 账号：更长、非 00 截断优先（嵌入 score 次级键）
        acct_boost = 0
        if kn == "accountnumber":
            digits = re.sub(r"\D", "", text)
            weak = 1 if (len(digits) < 10 or digits.startswith("00")) else 0
            acct_boost = (weak, -len(digits))
        if ox1 <= label_left + 30 and y_overlap > 0:
            score = (0, acct_boost, conf, -y_overlap, label_left - ox1)
        elif ox0 >= label_right - 20 and y_overlap > 0:
            # 同带右侧：TIME 竖拍真值常在这里，优先于「下方」
            score = (0, acct_boost, conf, -y_overlap, ox0 - label_right)
        elif oy0 >= label_bottom - 20 and abs(ocx - label_cx) < 180:
            # TIME 的正下方常是 DATE 列误读，降权
            tier = 2 if kn == "time" else 1
            score = (tier, acct_boost, conf, max(0.0, oy0 - label_bottom), abs(ocx - label_cx))
        else:
            dist = abs(ocx - label_cx) + abs(ocy - label_cy)
            if dist > 450:
                continue
            score = (3, acct_boost, conf, dist, 0)
        if best is None or score < best[0]:
            best = (score, _clean(text))
    return best[1] if best else None


# 本产品还款入账账号；远距 OCR 常截成 00109696 / 0109696
_LAK_ARTHA_CDM_ACCOUNT = "1001096962"


def _blob_mentions_lak_artha(*parts: Optional[str]) -> bool:
    blob = " ".join(p for p in parts if p).lower()
    return "lak" in blob and "artha" in blob


def _maybe_complete_lak_artha_account(
    acct: Optional[str], customer: Optional[str], lines
) -> Optional[str]:
    """户名为 LAK ARTHA 且 OCR 账号是已知入账号的连续子串时补全。"""
    known = _LAK_ARTHA_CDM_ACCOUNT
    texts = [customer or "", acct or ""] + [ln.text for ln in lines]
    if not _blob_mentions_lak_artha(*texts):
        return acct
    digits = re.sub(r"\D", "", acct or "")
    if digits == known:
        return known
    if len(digits) >= 6 and digits in known:
        return known
    # 扫描碎片行（0109696 / 00109696）
    for ln in lines:
        d = re.sub(r"\D", "", ln.text)
        if len(d) >= 6 and d in known:
            return known
    return acct


def _account_candidate_score(acct: str, conf: float = 0.0) -> tuple:
    """更长、非 00 截断、高置信优先。"""
    weak = 1 if (len(acct) < 10 or acct.startswith("00")) else 0
    return (-weak, len(acct), conf)


def _recover_cdm_account_number(lines) -> Optional[str]:
    """CDM 漏读 ACCOUNT 标签时：取 TRANSACTION~NARRATION 之间的 8–14 位账号。"""
    ordered = _sorted_by_y(lines)
    y0 = None
    y1 = None
    for ln in ordered:
        low = ln.text.lower()
        if y0 is None and ("cardless" in low or _norm_label(ln.text) in {"transaction", "ransaction"}):
            y0 = _line_center_y(ln.box)
        if y0 is not None and y1 is None and any(
            k in low for k in ("narration", "mobile", "source of funds", "notes")
        ):
            y1 = _line_center_y(ln.box)
    best = None
    for ln in ordered:
        cy = _line_center_y(ln.box)
        # 竖排时 TRANSACTION/NARRATION 的 y 几乎重叠，放宽带状过滤
        if y0 is not None and y1 is not None and abs(y1 - y0) > 80:
            if cy < min(y0, y1) - 40 or cy > max(y0, y1) + 40:
                continue
        conf = float(getattr(ln, "confidence", 0.0) or 0.0)
        for m in re.finditer(r"(?<!\d)(\d{8,14})(?!\d)", ln.text):
            acct = m.group(1)
            if acct in {"500000", "100000", "200000", "1000000"}:
                continue
            score = _account_candidate_score(acct, conf)
            if best is None or score > best[0]:
                best = (score, acct)
        if re.search(r"(?i)account", ln.text):
            tok = _account_token(_value_after_label(ln.text, "account number") or "")
            if not tok:
                tok = _account_token(ln.text)
            if tok and re.fullmatch(r"\d{8,14}", tok):
                score = _account_candidate_score(tok, conf + 0.05)
                if best is None or score > best[0]:
                    best = (score, tok)
    return best[1] if best else None


def _recover_cdm_customer_name(lines) -> Optional[str]:
    """CDM 漏读 CUSTOMER NAME 标签时：中间带人名/机构名兜底。"""
    ordered = _sorted_by_y(lines)
    y0 = y1 = None
    for ln in ordered:
        low = ln.text.lower()
        if y0 is None and ("cardless" in low or _norm_label(ln.text) in {"transaction", "ransaction"}):
            y0 = _line_center_y(ln.box)
        if y0 is not None and y1 is None and any(
            k in low for k in ("narration", "mobile", "source of funds", "notes")
        ):
            y1 = _line_center_y(ln.box)
    for ln in ordered:
        cy = _line_center_y(ln.box)
        if y0 is not None and cy < y0 - 20:
            continue
        if y1 is not None and cy > y1 + 20:
            continue
        text = ln.text.strip()
        if re.search(r"(?i)customer\s*name", text):
            inline = _value_after_label(text, "customer name")
            if inline and not _looks_like_label_text(inline):
                return _clean(inline)
        low = text.lower()
        if any(k in low for k in ("account", "transaction", "cardless", "narration", "mobile", "source")):
            continue
        if _looks_like_label_text(text) or re.search(r"\d{5,}", text):
            continue
        letters = re.findall(r"[A-Za-z]{2,}", text)
        if len(letters) >= 2:
            name = _clean(text)
            compact = re.sub(r"[^a-z]", "", name.lower())
            if "lakartha" in compact:
                return "LAK ARTHA SERVICES" if "service" in compact or "lak" in low else name
            return name
    return None


def _repair_cdm_typed_fields(fields: dict, lines) -> dict:
    """纠正竖拍/串列导致的 CDM DATE/TIME/TERMINAL/TRACE/ACCOUNT 等错绑。"""
    typed_keys = (
        "DATE",
        "TIME",
        "TERMINAL ID",
        "TRACE",
        "TRANSACTION STATUS",
        "ACCOUNT NUMBER",
        "TRANSACTION",
        "CUSTOMER NAME",
        "MOBILE NO.",
    )
    ordered = _sorted_by_y(lines)
    for key in typed_keys:
        cur = fields.get(key)
        # TIME/TRACE：即使当前值形态合法，也按几何+置信度重选（避免 01:11 日期误读、6359 低置信噪点）
        force = key in {"TIME", "TRACE"} or (
            cur is not None and not _is_plausible_cdm_field_value(key, cur)
        )
        if cur and _is_plausible_cdm_field_value(key, cur) and not force:
            continue
        label_i = None
        label_ln = None
        target = _norm_label(key)
        for i, ln in enumerate(ordered):
            # TERMINAL / ERMINAL 等残缺标签
            norm = _norm_label(ln.text)
            if norm == target or (
                key == "TERMINAL ID" and norm in {"terminal", "erminal", "terminalid"}
            ):
                label_i, label_ln = i, ln
                break
            if key == "TRANSACTION" and norm == "ransaction":
                label_i, label_ln = i, ln
                break
        found = None
        if label_ln is not None:
            found = _pick_cdm_typed_near(label_i, ordered, label_ln, key)
        if found is None and key in (
            "TIME",
            "TRACE",
            "TERMINAL ID",
            "ACCOUNT NUMBER",
            "TRANSACTION",
        ):
            # 标签漏读时：全卡扫描，TIME/TRACE 取置信度最高者
            best = None
            for ln in ordered:
                low = ln.text.lower()
                if key == "TRACE":
                    # 面额表/金额带噪点（8888、18.88）不当 TRACE
                    if any(
                        k in low
                        for k in (
                            "notes",
                            "value",
                            "amount",
                            "deposit",
                            "mount",
                            "galaxy",
                            "spam",
                            "truecaller",
                        )
                    ):
                        continue
                    if re.search(r"[.,]\d{2}", ln.text) or re.fullmatch(
                        r"\s*[08]{3,6}\s*", ln.text
                    ):
                        continue
                    conf = float(getattr(ln, "confidence", 0.0) or 0.0)
                    if conf < 0.85:
                        continue
                extracted = _extract_cdm_typed_substring(key, ln.text)
                if extracted and _is_plausible_cdm_field_value(key, extracted):
                    conf = float(getattr(ln, "confidence", 0.0) or 0.0)
                    if best is None or conf > best[0]:
                        best = (conf, extracted)
            if best:
                found = best[1]
        if found:
            if key == "TIME":
                found = _normalize_cdm_time(found) or found
            fields[key] = found
        elif key in fields and not _is_plausible_cdm_field_value(key, fields[key]):
            fields.pop(key, None)
    # ACCOUNT：弱截断号时用更长候选 / Lak Artha 入账号补全覆盖
    cur_acct = fields.get("ACCOUNT NUMBER")
    recovered = _recover_cdm_account_number(lines)
    if recovered and (
        not cur_acct
        or _account_candidate_score(recovered)
        > _account_candidate_score(re.sub(r"\D", "", str(cur_acct)))
    ):
        fields["ACCOUNT NUMBER"] = recovered
    completed = _maybe_complete_lak_artha_account(
        fields.get("ACCOUNT NUMBER"), fields.get("CUSTOMER NAME"), lines
    )
    if completed:
        fields["ACCOUNT NUMBER"] = completed
    # 空字段 OCR 残片：NARRATION/MOBILE 读成 IARRATION: / IOBILE NO.: 时清空
    for blank_key in ("NARRATION", "MOBILE NO.", "SOURCE OF FUNDS", "CUSTOMER NAME"):
        val = fields.get(blank_key)
        if val is None:
            continue
        if _looks_like_label_text(val) or not _clean(val) or _clean(val) in {":", "-", "–", "—"}:
            fields.pop(blank_key, None)
    # NARRATION 被交易类型串位；MOBILE 被账号串位
    narr = fields.get("NARRATION")
    txn = fields.get("TRANSACTION") or ""
    if narr and (
        re.search(r"(?i)cardless\s*deposit|cash\s*deposit", narr)
        or _norm_label(narr) == _norm_label(txn)
    ):
        fields.pop("NARRATION", None)
    mob = fields.get("MOBILE NO.")
    acct = re.sub(r"\D", "", str(fields.get("ACCOUNT NUMBER") or ""))
    if mob:
        mob_digits = re.sub(r"\D", "", mob)
        if acct and mob_digits == acct:
            fields.pop("MOBILE NO.", None)
        elif not _is_plausible_cdm_field_value("MOBILE NO.", mob):
            fields.pop("MOBILE NO.", None)
    rem = fields.get("Remarks")
    if rem and (
        _looks_like_label_text(rem)
        or re.search(r"(?i)cardless\s*deposit", rem)
        or (narr and _norm_label(rem) == _norm_label(narr))
    ):
        fields.pop("Remarks", None)
    # TRACE：仅出现在日期残片里则丢弃
    tr = fields.get("TRACE")
    if tr and re.match(r"^\d{3,6}$", str(tr)):
        in_clean = False
        in_date_junk = False
        for ln in lines:
            if str(tr) not in ln.text:
                continue
            if re.search(r"\d{1,2}[/.\-]\d{1,2}", ln.text) or re.search(
                r"(?i)d\d{3,4}/\d{2}", ln.text
            ):
                in_date_junk = True
            elif re.fullmatch(r"\s*\d{3,6}\s*", ln.text):
                in_clean = True
            elif re.search(rf"(?<!\d){re.escape(str(tr))}(?!\d)", ln.text) and not re.search(
                r"[A-Za-z]{3,}", ln.text
            ):
                in_clean = True
        if in_date_junk and not in_clean:
            fields.pop("TRACE", None)
    # DEPOSIT AMOUNT：仅丢掉「账号当金额」这类明显错值，不从面额表臆造总额
    dep = fields.get("DEPOSIT AMOUNT")
    if dep:
        amt = _parse_money(dep)
        if amt is not None and amt >= 50_000_000:
            fields.pop("DEPOSIT AMOUNT", None)
    return fields


def _is_plausible_reference(value: str) -> bool:
    """过滤 OCR 噪点参考号（如 Vishwa 的 \"Transaction ID :e\"）。"""
    v = _clean(value or "")
    if len(v) < 4:
        return False
    if v.lower() in {"n/a", "na", "none", "null", "success", "failed"}:
        return False
    if not re.search(r"\d", v):
        return False
    # 纯水印/银行名 + 数字不够长时也丢掉
    if re.search(r"(?i)nationstrust", v) and not re.search(r"\d{6,}", v):
        return False
    return True


def _build_dash_label_fields(lines, labels) -> dict:
    """解析「Label - value」/「Label: value」同行写法（HNB App / ComBank App）。

    值为空时（如 \"Transaction Reference -\"）取正下方一行。
    """
    wanted = {_norm_label(lbl): lbl for lbl in labels}
    fields: dict = {}
    ordered = _sorted_by_y(lines)
    for i, ln in enumerate(ordered):
        text = ln.text.strip()
        m = re.match(r"^(.+?)\s*[-:：]\s*(.*)$", text)
        if not m:
            continue
        raw_label, raw_value = m.group(1).strip(), m.group(2).strip()
        key = wanted.get(_norm_label(raw_label))
        if key is None or key in fields:
            continue
        value = _clean(raw_value)
        # "Branch: -" 表示空值，不能向下误取下一字段
        if value in {"-", "–", "—"}:
            continue
        if not value:
            # 空值：先右侧（UBgo Paid From:  ****6011），再下方
            side = _value_to_right(i, ordered, ln)
            value = _clean(side) if side else None
            if not value or value in {"-", "–", "—"}:
                below = _value_below(i, ordered, ln)
                value = _clean(below) if below else None
            # 下方若是另一组 "Label: value"，不是当前空字段的值
            if value and re.match(r"^[A-Za-z][A-Za-z\s/&]{1,40}\s*[:：-]", value):
                value = None
        if value and value not in {"-", "–", "—"} and not _looks_like_label_text(value):
            fields[key] = value
    return fields


def _build_union_ubgo_fields(lines) -> dict:
    """Union Bank UBgo FUND TRANSFER RECEIPT：冒号同行字段 + Amount 上下布局。"""
    fields = _build_dash_label_fields(lines, _UNION_UBGO_LABELS)
    # Amount 常独占一行，值在正下方 "LKR 5,000.00"
    for k, v in _build_label_fields(lines, ("Amount", "Paid From")).items():
        fields.setdefault(k, v)
    if fields.get("Transaction Status") and not fields.get("Status"):
        fields["Status"] = fields["Transaction Status"]
    # 金额下方居中的收款行名（无 Bank 标签）
    if not fields.get("Beneficiary Bank"):
        for ln in _sorted_by_y(lines):
            t = ln.text.strip()
            if re.search(r"(?i)commercial\s*bank", t) and not re.search(r"(?i)union", t):
                fields["Beneficiary Bank"] = re.sub(r"\s+", " ", t).strip(" .")
                break
    return fields


def _is_ntb_watermark_text(text: str) -> bool:
    """Nations Trust 斜向水印及其 OCR 残片。"""
    compact = re.sub(r"[^a-z]", "", (text or "").lower())
    if not compact or len(compact) < 4:
        return False
    if compact in {
        "nations",
        "nation",
        "trustbank",
        "trust",
        "tbank",
        "stbank",
        "ustbank",
        "rustbank",
        "nsbank",
        "tionstrustbank",
        "nationstrustbank",
        "nationstrust",
        "nationstrus",
        "nationstru",
        "verifiedby",
    }:
        return True
    if "nationstrustbank" in compact and len(compact) <= len("pnationstrustbank") + 2:
        return True
    if compact.endswith("trustbank") and len(compact) <= 20:
        return True
    # DescriptiontBank / Success 粘水印等
    if re.fullmatch(r"(description|status|success|amount)?n?ations?trustbank.*", compact):
        return True
    if compact.endswith("tbank") and any(
        k in compact for k in ("description", "status", "success", "amount", "nations", "trust")
    ):
        return True
    return False


def _is_ntb_description_code(text: str) -> bool:
    """NTB Description 常见短码：PU8QAW（字母+数字，非纯账号）。"""
    t = (text or "").strip()
    return bool(
        re.fullmatch(r"[A-Z0-9]{4,12}", t)
        and re.search(r"[A-Z]", t)
        and re.search(r"\d", t)
        and not re.fullmatch(r"\d{6,}", t)
    )


def _is_ntb_ocr_junk_token(text: str) -> bool:
    """仅水印残片算 junk；PU8QAW 这类描述短码保留。"""
    t = (text or "").strip()
    if not t:
        return True
    if _is_ntb_description_code(t):
        return False
    return _is_ntb_watermark_text(t)


def _scrub_ntb_watermark_glue(value: str) -> str:
    """剥掉 Description 上粘连的 NationsTrust 水印前缀，保留真实短码。

    例：NatiPU8QAW / 3 Nat PU8QAW → PU8QAW。
    """
    v = _clean(value or "")
    if not v:
        return ""
    if _is_ntb_watermark_text(v):
        return ""
    # 去掉整段水印子串
    v = re.sub(
        r"(?i)(?:nations?\s*trust\s*bank|nationstrustbank|tionstrustbank|trustbank)",
        " ",
        v,
    )
    v = re.sub(r"\s+", " ", v).strip(" .-:")
    if not v or _is_ntb_watermark_text(v):
        return ""
    # 已是干净短码
    if _is_ntb_description_code(v):
        return v
    # "3 Nat PU8QAW" / "Nat PU8QAW"
    m = re.match(
        r"(?i)^(?:\d+\s+)?(?:nations?|nati|nat|tions?)\s+([A-Z0-9]{4,12})$",
        v,
    )
    if m and _is_ntb_description_code(m.group(1)):
        return m.group(1).upper()
    # 粘连：NatiPU8QAW / NatPU8QAW / NationsPU8QAW
    m = re.match(
        r"(?i)^(?:nations?|nati|nat|tions?)([A-Z0-9]*\d[A-Z0-9]*)$",
        re.sub(r"\s+", "", v),
    )
    if m and _is_ntb_description_code(m.group(1)):
        return m.group(1).upper()
    # 尾部短码：任意水印残片 + PU8QAW
    m = re.search(r"([A-Z]{2,}\d[A-Z0-9]{2,}|\d[A-Z]{3,})$", re.sub(r"\s+", "", v))
    if m and _is_ntb_description_code(m.group(1)):
        return m.group(1).upper()
    if _is_ntb_ocr_junk_token(v):
        return ""
    return v


def _filter_ntb_watermark_lines(lines):
    return [ln for ln in lines if not _is_ntb_watermark_text(ln.text)]


def _pick_ntb_description(lines, label_line) -> Optional[str]:
    """Description 右列多候选：剥水印后取短码/正文；偏右、高置信优先。"""
    ly0 = min(p[1] for p in label_line.box)
    ly1 = max(p[1] for p in label_line.box)
    label_right = max(p[0] for p in label_line.box)
    best = None
    for ln in lines:
        if _is_ntb_watermark_text(ln.text):
            continue
        ox0 = min(p[0] for p in ln.box)
        if ox0 < label_right - 20:
            continue
        oy0 = min(p[1] for p in ln.box)
        oy1 = max(p[1] for p in ln.box)
        overlap = min(ly1, oy1) - max(ly0, oy0)
        if overlap <= 0:
            continue
        scrubbed = _scrub_ntb_watermark_glue(ln.text)
        if not scrubbed or _looks_like_label_text(scrubbed):
            continue
        if _ntb_description_contaminated(scrubbed):
            continue
        conf = float(getattr(ln, "confidence", 0.0) or 0.0)
        # 短码优先于仍带空格的残片；偏右（值列）、高置信
        code_bonus = 1 if _is_ntb_description_code(scrubbed) else 0
        score = (code_bonus, ox0, conf, overlap)
        if best is None or score > best[0]:
            best = (score, scrubbed)
    return best[1] if best else None


def _scrub_ntb_text_fields(fields: dict, lines) -> dict:
    """NTB：清洗 Description/Remarks，并在标签旁重选未被水印污染的描述。"""
    for key in ("Description", "Remarks", "Status", "To account name", "Bank"):
        if key not in fields or not fields[key]:
            continue
        cleaned = _scrub_ntb_watermark_glue(str(fields[key]))
        if cleaned:
            fields[key] = cleaned
        else:
            fields.pop(key, None)
    # 右列重选：PU8QAW 优于 NatiPU8QAW / 3 Nat PU8QAW
    picked = None
    for ln in lines:
        if _norm_label(ln.text) == "description":
            picked = _pick_ntb_description(lines, ln)
            break
    cur = fields.get("Description") or ""
    if picked and (
        not cur
        or _ntb_description_contaminated(cur)
        or (
            _is_ntb_description_code(picked)
            and not _is_ntb_description_code(cur)
        )
        or (
            _is_ntb_description_code(picked)
            and _is_ntb_description_code(cur)
            and picked != cur
            and len(picked) >= len(cur)
        )
    ):
        fields["Description"] = picked
    if fields.get("Description"):
        fields["Remarks"] = fields["Description"]
    elif "Remarks" in fields:
        rem = _scrub_ntb_watermark_glue(str(fields["Remarks"]))
        if rem and not _ntb_description_contaminated(rem):
            fields["Remarks"] = rem
        else:
            fields.pop("Remarks", None)
    return fields


def _ntb_description_contaminated(desc: Optional[str]) -> bool:
    """仍粘 Nations 水印前缀 / 空，需复检；纯 PU8QAW 短码视为干净。"""
    if not desc or not str(desc).strip():
        return True
    d = str(desc).strip()
    if _is_ntb_description_code(d):
        return False
    if _is_ntb_watermark_text(d):
        return True
    # 仍含 Nations/Nati/Nat 水印词
    if re.search(r"(?i)\b(?:nations?|nati|nat|tions?)\b", d):
        return True
    if re.match(r"(?i)^(?:\d+\s+)?(?:nations?|nati|nat)", d):
        return True
    if re.search(r"(?i)nationstrust|trustbank", d):
        return True
    return False


def _enrich_reference_aliases(fields: dict, references: ReferencesOut) -> dict:
    """下游常用 Payment Reference / Transaction Reference 别名补齐。"""
    candidates = [
        fields.get("Payment Reference"),
        fields.get("Transaction Reference"),
        fields.get("Transaction reference"),
        fields.get("Reference number"),
        references.txn_ref,
        references.transaction_id,
        references.bank_reference_number,
        references.e_receipt_reference,
    ]
    ref = next((c for c in candidates if c and _is_plausible_reference(str(c))), None)
    if not ref:
        return fields
    ref = _clean(str(ref))
    # 去掉 OCR 粘上的银行水印前缀
    ref = re.sub(r"(?i)^nationstrustbank\s*", "", ref).strip(" -:") or ref
    if not any(k.lower() == "payment reference" for k in fields):
        fields["Payment Reference"] = ref
    if not any(_norm_label(k) == "transactionreference" for k in fields):
        fields["Transaction Reference"] = ref
    return fields


def _synthesize_cdm_datetime_fields(fields: dict) -> dict:
    """CDM 的 DATE+TIME 合成下游常用 Date & Time / Transaction Date/Time。"""
    date_v = fields.get("DATE")
    time_v = fields.get("TIME")
    if not date_v:
        return fields
    if time_v and _looks_like_terminal_id_value(time_v):
        fields.pop("TIME", None)
        time_v = None
    if time_v:
        time_v = _normalize_cdm_time(time_v)
        if time_v:
            fields["TIME"] = time_v
        else:
            fields.pop("TIME", None)
    date_part = str(date_v).split()[0]
    if time_v:
        combined = f"{date_part} {time_v}:00"
        fields.setdefault("Date & Time", combined)
        fields.setdefault("Transaction Date/Time", combined)
    else:
        fields.setdefault("Date & Time", date_part if " " in str(date_v) else f"{date_part} 00:00:00")
    return fields


def _build_ereceipt_fields(lines) -> dict:
    buckets = _right_column_buckets(lines, _E_RECEIPT_LABELS)
    return {k: " ".join(v) for k, v in buckets.items() if v}


def _build_nsb_fields(lines) -> dict:
    """NSB Online Banking 回执：三栏（Source / Receiver / Transaction Details）。

    左列 Source/Receiver 与右列 Transaction 用 x 分界；Source 与 Receiver 之间用
    分区标题的 y 分界。两栏同名 "Account No." 分别标记为 Source/Receiver 前缀。
    """
    ordered = _sorted_by_y(lines)
    source_y = None
    receiver_y = None
    for ln in ordered:
        t = ln.text.strip().lower()
        if source_y is None and "source account details" in t:
            source_y = _line_center_y(ln.box)
        elif receiver_y is None and "receiver account details" in t:
            receiver_y = _line_center_y(ln.box)

    source_lines, receiver_lines, txn_lines = [], [], []
    for ln in lines:
        x = min(p[0] for p in ln.box)
        y = _line_center_y(ln.box)
        if x >= 560:
            txn_lines.append(ln)
        elif receiver_y is not None and y >= receiver_y:
            receiver_lines.append(ln)
        elif source_y is not None and y >= source_y:
            source_lines.append(ln)

    fields = _build_label_fields(txn_lines, _NSB_TXN_LABELS, same_row=True)

    src = _build_label_fields(source_lines, _NSB_SOURCE_LABELS, same_row=True)
    if src.get("Account No."):
        fields["Source Account No."] = src["Account No."]
    if src.get("Account Type"):
        fields["Account Type"] = src["Account Type"]
    if src.get("Transfer Type"):
        fields["Transfer Type"] = src["Transfer Type"]

    rcv = _build_label_fields(receiver_lines, _NSB_RECEIVER_LABELS, same_row=True)
    if rcv.get("Account No."):
        fields["Receiver Account No."] = rcv["Account No."]
    for k, v in rcv.items():
        if k != "Account No.":
            fields[k] = v
    return fields


def _extract_ipay_parties(lines) -> tuple:
    buckets = _right_column_buckets(lines, _IPAY_LABELS)
    payer = PartyOut()
    payee = PartyOut()

    from_vals = buckets.get("From", [])
    to_vals = buckets.get("To", [])
    recipient_vals = buckets.get("Recipient", [])

    # From: 首行姓名，后续行 bank + 掩码账号（如 "Bank of Ceylon ****1089"）
    if from_vals:
        payer.name = from_vals[0]
        for v in from_vals[1:]:
            tok = _account_token(v)
            if tok:
                payer.account = tok
                bank = re.sub(r"[0-9*Xx]{6,}", "", v).strip(" -")
                if bank:
                    payer.bank = bank
            elif payer.bank is None:
                payer.bank = v
    # To: 首行银行，后续行账号（如 "Commercial Bank PLC" + "1001096962"）
    if to_vals:
        payee.bank = to_vals[0]
        for v in to_vals[1:]:
            tok = _account_token(v)
            if tok:
                payee.account = tok
    # Recipient: 收款方姓名
    if recipient_vals:
        payee.name = recipient_vals[0]

    payer.account_prefix, payer.account_last4 = _derive_account_parts(payer.account)
    payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)
    return payer, payee


def _build_peoples_pay_fields(lines, payer, payee) -> dict:
    """People's Pay 回执：Pay from / Pay to 两个分区，字段用 Payer/Payee 别名区分。

    页面有多个同名字段（Name / Bank / Account No），按分区归属分别标记；
    标签漏识别时用结构化字段（payer/payee）兜底。
    僧伽罗语版英文标签缺失时，按 People's Bank / Commercial Bank 锚点位置兜底。
    """
    payer_zone, payee_zone, has_anchor = _split_zones(lines)

    fields = _build_label_fields(
        lines,
        ("Amount (LKR)", "Fee Amount (LKR)", "Total debit amount (LKR)", "Date & Time", "Trace No"),
    )

    # 有分区锚点时只用分区；否则不要把全卡丢给 "Bank" 标签（会误截 Commercial Bank PLC）
    payer_src = payer_zone if has_anchor else []
    payee_src = payee_zone if has_anchor else []

    # Pay from 区 -> Payer 别名
    payer_fields = _build_label_fields(payer_src, ("Name", "Bank", "Account No", "Account Currency")) if payer_src else {}
    if payer.name or payer_fields.get("Name"):
        fields["Payer Name"] = payer.name or payer_fields.get("Name")
    if payer.bank or payer_fields.get("Bank"):
        bank_v = payer.bank or payer_fields.get("Bank")
        if bank_v and bank_v.upper() not in {"PLC", "BANK", "LTD"}:
            fields["Payer Bank"] = bank_v
    if payer.account or payer_fields.get("Account No"):
        fields["Payer Account No"] = payer.account or payer_fields.get("Account No")
    if payer_fields.get("Account Currency"):
        fields["Account Currency"] = payer_fields["Account Currency"]

    # Pay to 区 -> Payee 别名（结构化 payee 已经过 Lak Artha 等归一化，优先采用）
    payee_fields = _build_label_fields(payee_src, ("Name", "Bank Name", "Account No")) if payee_src else {}
    if payee.name or payee_fields.get("Name"):
        fields["Payee Name"] = payee.name or payee_fields.get("Name")
    if payee.bank or payee_fields.get("Bank Name"):
        fields["Payee Bank"] = payee.bank or payee_fields.get("Bank Name")
    if payee.account or payee_fields.get("Account No"):
        fields["Payee Account No"] = payee.account or payee_fields.get("Account No")

    sparse = not fields.get("Payer Account No") or not fields.get("Payee Account No") or not fields.get(
        "Amount (LKR)"
    )
    if sparse or _is_peoples_pay_sinhala_layout(lines):
        _, _, pos_fields = _extract_peoples_pay_positional(lines)
        for k, v in pos_fields.items():
            if k == "Payer Bank" and fields.get("Payer Bank") and fields["Payer Bank"].upper() not in {
                "PLC",
                "BANK",
                "LTD",
            }:
                continue
            fields.setdefault(k, v)
            if k == "Payer Bank" and fields.get("Payer Bank", "").upper() in {"PLC", "BANK", "LTD"}:
                fields["Payer Bank"] = v

    return fields


_BRANCH_RE = re.compile(r"(?i)^[a-z0-9][a-z0-9\-./ ]*\bbr\b$")


def _branch_quality(text: str, conf: float = 0.0) -> tuple:
    """网点名质量：少数字串位（KAI U1ARA）、高置信优先。"""
    t = text.strip()
    digit_hits = len(re.findall(r"\d", re.sub(r"(?i)crm\s*\d+", "", t)))
    return (-digit_hits, conf, len(t))


def _extract_branch(lines) -> Optional[str]:
    """存款凭条网点：通常以 "BR"（branch）结尾，如 "BANDARAG-CRM2 BR"。

    OCR 常把 "EKALA-CRM1 BR" 拆成同行的 "EKALA-CRM1" + "BR"，需拼接。
    多候选时偏好无字母位数字串位者（KALUTARA 优于 KAI U1ARA）。
    """
    ordered = _sorted_by_y(lines)
    candidates = []
    for ln in ordered:
        t = ln.text.strip()
        if _BRANCH_RE.fullmatch(t):
            conf = float(getattr(ln, "confidence", 0.0) or 0.0)
            candidates.append((_branch_quality(t, conf), t))
    for ln in ordered:
        if ln.text.strip().upper() != "BR":
            continue
        br_y = _line_center_y(ln.box)
        br_left = min(p[0] for p in ln.box)
        best = None
        for other in ordered:
            if other is ln:
                continue
            if abs(_line_center_y(other.box) - br_y) > 45:
                continue
            other_right = max(p[0] for p in other.box)
            if other_right > br_left + 15:
                continue
            text = other.text.strip()
            if not re.match(r"(?i)^[A-Z0-9][A-Z0-9\-./]{2,}$", text):
                continue
            if text.upper() in {"DATE", "TIME", "TRACE", "NOTES", "VALUE", "AMOUNT", "LKR", "BANK"}:
                continue
            gap = br_left - other_right
            conf = float(getattr(other, "confidence", 0.0) or 0.0)
            cand = f"{text} BR"
            score = (_branch_quality(cand, conf), -gap)
            if best is None or score > best[0]:
                best = (score, cand)
        if best:
            candidates.append((_branch_quality(best[1]), best[1]))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    return _match_label_value(lines, ["branch", "branch name"])


def extract(lines, include_lines: bool = False) -> RepaymentResult:
    warnings: List[str] = []

    # 先剔除旋转文本框（截图上的斜向水印/批注），避免其大范围 box 抢占字段值
    lines = [ln for ln in lines if not _is_rotated_box(ln.box)]

    full_text = " ".join(ln.text for ln in lines)

    doc_type = _detect_doc_type(full_text)
    status = _detect_status(full_text)
    bank = _detect_bank(lines)
    # 现金存款凭条版式固定为 Commercial Bank，即使 OCR 把标题读坏，
    # 只要面额表 / CDM 表头检测命中就设为 commercial_bank。
    if (_is_cash_credit_slip(lines) or _is_cash_deposit(lines)) and not bank:
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

    # 收款方归一化：还款场景常见 Lak Artha 系列写法（含 Kak/L.a.k OCR 混淆）
    if payee.name and _looks_like_lak_artha_name(payee.name):
        payee.name = "Lak Artha (Pvt) Ltd"

    success = bool(amount is not None or payee.account is not None or payee.name is not None)
    # App 还款发起页/上传截图页不是交易凭证，强制 success=false
    if doc_type == "unknown" and _is_app_loan_page(full_text):
        success = False
        warnings.append("上传图片不是银行交易凭证，请上传银行还款截图")

    if _is_boc_mobile_txn_details(lines):
        field_labels = _BOC_MOBILE_TXN_LABELS
    elif _is_boc_smartpay(lines):
        field_labels = _BOC_SMARTPAY_LABELS
    elif _is_boc_app(lines):
        field_labels = _BOC_APP_LABELS
    elif _is_boc_flex(lines):
        field_labels = _BOC_FLEX_LABELS
    elif bank == "vishwa":
        field_labels = _SAMPATH_VISHWA_LABELS
    elif bank == "peoples_bank":
        field_labels = _PEOPLES_BANK_LABELS
    elif _is_cash_deposit(lines):
        field_labels = _CDM_LABELS
    elif bank == "lb_finance":
        field_labels = _LB_FINANCE_LABELS
    elif bank == "ipay":
        field_labels = _IPAY_LABELS
    elif bank == "union_bank":
        field_labels = _UNION_UBGO_LABELS
    elif bank == "ntb":
        field_labels = (
            "Status",
            "Amount",
            "Date",
            "Time",
            "Reference number",
            "From account",
            "To account",
            "To account name",
            "Bank",
            "Service charge",
            "Description",
        )
    else:
        field_labels = _E_RECEIPT_LABELS

    if bank == "ipay":
        fields = _build_ipay_fields(lines)
    elif bank == "union_bank":
        fields = _build_union_ubgo_fields(lines)
        if amount is None and fields.get("Amount"):
            amount = _parse_money(fields["Amount"])
        if fee is None and fields.get("Service Charge"):
            fee = _parse_money(fields["Service Charge"])
        if total is None and amount is not None:
            total = amount + (fee or 0.0)
        if not payee.account and fields.get("Pay To"):
            payee.account = _account_token(fields["Pay To"]) or fields["Pay To"].strip()
            payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)
        if not payee.name and fields.get("Beneficiary Name"):
            raw_name = fields["Beneficiary Name"].strip(" .")
            compact = re.sub(r"[^a-z]", "", raw_name.lower())
            payee.name = "Lak Artha (Pvt) Ltd" if "lakartha" in compact else raw_name
        if payee.name:
            fields["Beneficiary Name"] = payee.name
        if not payee.bank and fields.get("Beneficiary Bank"):
            payee.bank = fields["Beneficiary Bank"]
        if not payer.account and fields.get("Paid From"):
            payer.account = fields["Paid From"].strip()
            payer.account_prefix, payer.account_last4 = _derive_account_parts(payer.account)
        if not payer.bank:
            payer.bank = "Union Bank of Colombo PLC"
        if amount is not None or payee.account is not None or fields.get("Reference Number"):
            success = True
    elif _is_peoples_otp(lines):
        fields = _build_label_fields(lines, _PEOPLES_OTP_LABELS)
        # 结构化付款/收款方：OTP 页无 Pay from/to 分区，从扁平字段回填
        if not payee.account and fields.get("Beneficiary Account Number"):
            payee.account = _account_token(fields["Beneficiary Account Number"]) or fields[
                "Beneficiary Account Number"
            ].strip()
        if not payee.name and fields.get("Beneficiary Name"):
            payee.name = fields["Beneficiary Name"]
        if not payee.bank and fields.get("Beneficiary Account Bank"):
            payee.bank = re.sub(r"^\d+\s*-\s*", "", fields["Beneficiary Account Bank"]).strip()
        if not payer.account and fields.get("From Account"):
            payer.account = fields["From Account"].strip()
        payer.account_prefix, payer.account_last4 = _derive_account_parts(payer.account)
        payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)
        if amount is None and fields.get("Transfer Amount"):
            amount = _parse_money(fields["Transfer Amount"])
        if not success and (
            payee.account or payee.name or fields.get("Reference Number") or fields.get("Status")
        ):
            success = True
    elif bank == "peoples_bank":
        fields = _build_peoples_pay_fields(lines, payer, payee)
        # 僧伽罗语等标签缺失时，结构化金额常被状态栏噪点带偏，用扁平金额回填
        for src_key, setter in (
            ("Amount (LKR)", "amount"),
            ("Fee Amount (LKR)", "fee"),
            ("Total debit amount (LKR)", "total"),
        ):
            parsed = _parse_money(fields.get(src_key) or "")
            if parsed is None:
                continue
            if setter == "amount" and (amount is None or amount < 100):
                amount = parsed
            elif setter == "fee" and (fee is None or fee < 1):
                fee = parsed
            elif setter == "total" and (total is None or total < 100):
                total = parsed
        if total is None and amount is not None and fee is not None:
            total = amount + fee
        if amount is not None or payee.account is not None or fields.get("Payer Account No"):
            success = True
    elif doc_type == "e_receipt":
        fields = _build_ereceipt_fields(lines)
    elif bank == "nsb" and "nsb online banking" in full_text.lower():
        fields = _build_nsb_fields(lines)
    elif bank == "nsb":
        # NSB Online Payment - Mobile：左标签冒号右值
        fields = _build_label_fields(lines, _NSB_MOBILE_LABELS, same_row=True)
        dash = _build_dash_label_fields(lines, _NSB_MOBILE_LABELS)
        for k, v in dash.items():
            fields.setdefault(k, v)
    elif _is_hnb_app_receipt(lines) or _is_to_only_receipt(lines):
        fields = _build_dash_label_fields(lines, _HNB_APP_LABELS)
        # ComBank / HNB App 金额常为独立 "LKR x,xxx.00" 行
        if not any("amount" in k.lower() for k in fields):
            for ln in lines:
                m = re.search(r"(?i)\bLKR\s*([\d,]+(?:\.\d{2})?)", ln.text)
                if m:
                    fields["Amount"] = f"LKR {m.group(1)}"
                    break
    elif _is_boc_mobile_txn_details(lines):
        fields = _build_label_fields(lines, _BOC_MOBILE_TXN_LABELS)
        _repair_boc_sender_name(fields, lines)
        # 顶部大额为转账金额；Fees & Charges 为手续费（勿把 25 当成主金额）
        fee_v = fields.get("Fees & Charges")
        if fee_v:
            parsed_fee = _parse_money(fee_v)
            if parsed_fee is not None:
                fee = parsed_fee
        # 通用金额抽取常误把手续费当成主金额，先清掉再认顶部大额
        if fee is not None and amount is not None and abs(amount - fee) < 0.01:
            amount = None
        picked = _pick_boc_hero_transfer_amount(lines, fee)
        if picked is not None:
            amount = picked
            fields["Transfer Amount"] = f"LKR {amount:,.2f}"
        if fee is not None and amount is not None:
            total = amount + fee
        elif amount is not None:
            total = amount
        # 结构化收付款方以扁平字段为准（竖拍时通用分区易串位）
        if fields.get("Receiver's Account No"):
            payee.account = fields["Receiver's Account No"]
        if fields.get("Receiver's Bank"):
            payee.bank = fields["Receiver's Bank"]
        if fields.get("Receiver's Name"):
            raw_name = fields["Receiver's Name"]
            payee.name = (
                "Lak Artha (Pvt) Ltd" if _looks_like_lak_artha_name(raw_name) else raw_name
            )
            fields["Receiver's Name"] = payee.name
        if fields.get("Sender's Account No"):
            payer.account = fields["Sender's Account No"]
        if fields.get("Sender's Name"):
            payer.name = fields["Sender's Name"]
        if fields.get("Sender's Bank Name"):
            payer.bank = fields["Sender's Bank Name"]
        elif not payer.bank:
            payer.bank = "Bank of Ceylon"
        payer.account_prefix, payer.account_last4 = _derive_account_parts(payer.account)
        payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)
        if amount is not None or payee.account or fields.get("Remarks"):
            success = True
        # 日期常在截图角落：2026.11.01
        if not any("date" in k.lower() for k in fields):
            for ln in lines:
                if re.fullmatch(r"\d{4}[./\-]\d{1,2}[./\-]\d{1,2}", ln.text.strip()):
                    fields["Date"] = ln.text.strip().replace(".", "-")
                    parsed_dt = _parse_datetime(fields["Date"])
                    if parsed_dt:
                        dt = parsed_dt
                    break
    elif _is_boc_smartpay(lines):
        fields = _build_label_fields(lines, _BOC_SMARTPAY_LABELS)
        dash = _build_dash_label_fields(lines, _BOC_SMARTPAY_LABELS)
        for k, v in dash.items():
            fields.setdefault(k, v)
    elif bank == "ntb":
        # 斜向 NationsTrustBank 水印极多，先滤掉再抽字段，避免粘进 Description
        ntb_lines = _filter_ntb_watermark_lines(lines)
        fields = _build_label_fields(ntb_lines, field_labels)
        fields = _scrub_ntb_text_fields(fields, ntb_lines)
    else:
        fields = _build_label_fields(lines, field_labels)
    # 金额小数点被 OCR 误读为冒号时还原（如 "2,500:00" → "2,500.00"）
    fields = _normalize_money_fields(fields)
    if _is_cash_deposit(lines) or (bank == "commercial_bank" and fields.get("DATE")):
        fields = _repair_cdm_typed_fields(fields, lines)
        fields = _synthesize_cdm_datetime_fields(fields)
        # OCR 常漏读 CARDLESS DEPOSIT / 账号 / 存款总额行，用已识别结构化结果回填
        if not fields.get("TRANSACTION") and _is_cash_deposit(lines):
            fields["TRANSACTION"] = "CARDLESS DEPOSIT"
        if not fields.get("ACCOUNT NUMBER") and payee.account:
            fields["ACCOUNT NUMBER"] = payee.account
        if not fields.get("CUSTOMER NAME") and payee.name:
            fields["CUSTOMER NAME"] = payee.name
        # 中间带补检后：无标签时从纯数字行/户名行兜底
        if not fields.get("ACCOUNT NUMBER"):
            recovered_acct = _recover_cdm_account_number(lines)
            if recovered_acct:
                fields["ACCOUNT NUMBER"] = recovered_acct
        # Lak Artha 截断账号再补一次（repair 后仍可能缺户名锚点）
        completed_acct = _maybe_complete_lak_artha_account(
            fields.get("ACCOUNT NUMBER"), fields.get("CUSTOMER NAME"), lines
        )
        if completed_acct:
            fields["ACCOUNT NUMBER"] = completed_acct
        if fields.get("ACCOUNT NUMBER"):
            payee.account = fields["ACCOUNT NUMBER"]
            payee.account_prefix, payee.account_last4 = _derive_account_parts(payee.account)
        if not fields.get("CUSTOMER NAME"):
            recovered_name = _recover_cdm_customer_name(lines)
            if recovered_name:
                fields["CUSTOMER NAME"] = recovered_name
                if not payee.name:
                    payee.name = recovered_name
        if branch:
            # 多候选时 _extract_branch 已优选；覆盖 OCR 串位网点
            cur_br = fields.get("BRANCH")
            if not cur_br or _branch_quality(branch) > _branch_quality(str(cur_br)):
                fields["BRANCH"] = branch
        # DEPOSIT AMOUNT：结构化总额优先；面额表面值（5000）被误填时用 10,200 覆盖
        if amount is not None:
            dep_amt = _parse_money(fields["DEPOSIT AMOUNT"]) if fields.get("DEPOSIT AMOUNT") else None
            if dep_amt is None or (
                abs(dep_amt - amount) > 0.01
                and _has_notes_value_table(lines)
                and dep_amt in _COMMON_DENOMS
            ):
                fields["DEPOSIT AMOUNT"] = f"{amount:,.2f}"
            if fee is None:
                total = amount
        elif fields.get("DEPOSIT AMOUNT"):
            parsed_amt = _parse_money(fields["DEPOSIT AMOUNT"])
            if parsed_amt is not None and (amount is None or amount >= 50_000_000):
                amount = parsed_amt
                total = parsed_amt if total is None or (total is not None and total >= 50_000_000) else total
        # TRANSACTION / STATUS 串了邻行时收束
        txn = fields.get("TRANSACTION")
        if txn and re.search(r"(?i)cardless\s*deposit", txn):
            fields["TRANSACTION"] = "CARDLESS DEPOSIT"
        st = fields.get("TRANSACTION STATUS")
        if st:
            m = re.search(r"(?i)\b(successful|success|failed|fail|rejected)\b", st)
            if m:
                fields["TRANSACTION STATUS"] = m.group(0).upper()
                if fields["TRANSACTION STATUS"] == "SUCCESS":
                    fields["TRANSACTION STATUS"] = "SUCCESSFUL"
        if not fields.get("TRANSACTION STATUS") and status == "success":
            # 仅当 OCR 原文能佐证成功时填写，避免无 Status 行时硬造
            if re.search(r"(?i)success", full_text):
                fields["TRANSACTION STATUS"] = "SUCCESSFUL"
        # 竖拍串位后，结构化 terminal/trace 也常被右侧银行名污染，以修复后的扁平字段为准
        if fields.get("TERMINAL ID") and _looks_like_terminal_id_value(fields["TERMINAL ID"]):
            terminal_id = fields["TERMINAL ID"]
        if fields.get("TRACE") and re.match(r"^\d{3,6}$", str(fields["TRACE"])):
            trace_no = fields["TRACE"]
        # Date & Time 合成后回写结构化 datetime
        for dt_key in ("Date & Time", "Transaction Date/Time"):
            if fields.get(dt_key):
                parsed_dt = _parse_datetime(fields[dt_key])
                if parsed_dt:
                    dt = parsed_dt
                    break
        # 回填 amount 后刷新 success；CDM 仅表头完整时也视为识别成功
        if amount is not None or payee.account is not None or payee.name is not None:
            success = True
        elif fields.get("TRACE") or fields.get("TERMINAL ID"):
            success = True
    fields = _enrich_reference_aliases(fields, references)
    # 金额字段被水印/噪点污染时，用已解析数值回填
    for amount_key in list(fields.keys()):
        if "amount" not in amount_key.lower():
            continue
        raw_amt = fields.get(amount_key) or ""
        if amount is not None and not re.search(r"\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+\.\d{2}", raw_amt):
            fields[amount_key] = f"LKR {amount:,.2f}"
    if bank == "ntb":
        if fields.get("Status") and "nationstrust" in str(fields["Status"]).lower():
            if status:
                fields["Status"] = "Success" if status == "success" else status
        # Reference number 里的水印前缀已在 alias 里剥掉；同步写回
        if fields.get("Payment Reference") and "Reference number" in fields:
            fields["Reference number"] = fields["Payment Reference"]
        # 再次清洗（Remarks 兜底可能在后面写入前先对齐 Description）
        fields = _scrub_ntb_text_fields(fields, _filter_ntb_watermark_lines(lines))
        if fields.get("Description") and not fields.get("Remarks"):
            fields["Remarks"] = fields["Description"]
        elif fields.get("Remarks"):
            rem = _scrub_ntb_watermark_glue(str(fields["Remarks"]))
            if rem:
                fields["Remarks"] = rem
            else:
                fields.pop("Remarks", None)
    # 时间无标签（如 BOC App 独立的 "10.08.2026 , 06:45 PM" 行）时，从 OCR 原文补 Date & Time
    if not any("date" in k.lower() or "time" in k.lower() for k in fields):
        raw_dt = _find_datetime_raw(lines)
        if raw_dt:
            fields["Date & Time"] = raw_dt
        elif dt:
            fields["Date & Time"] = dt.replace("T", " ")
    # Remarks 兜底：结构化字段已提取但 fields 无 Remarks 时补上（如 People's Pay 占位标签下一行值）
    if (
        references.remarks
        and not _looks_like_label_text(references.remarks)
        and not any("remark" in k.lower() for k in fields)
    ):
        fields["Remarks"] = references.remarks
    # CDM 空 NARRATION 常被写成 Remarks；标签残片/交易类型不得作为备注
    if fields.get("NARRATION") and (
        _looks_like_label_text(fields["NARRATION"])
        or re.search(r"(?i)cardless\s*deposit|cash\s*deposit", fields["NARRATION"])
    ):
        fields.pop("NARRATION", None)
    if fields.get("Remarks") and (
        _looks_like_label_text(fields["Remarks"])
        or re.search(r"(?i)cardless\s*deposit|cash\s*deposit", fields["Remarks"])
    ):
        fields.pop("Remarks", None)
    if fields.get("NARRATION") and not any("remark" in k.lower() for k in fields):
        narr = fields["NARRATION"]
        if not re.search(r"(?i)cardless\s*deposit|cash\s*deposit", narr):
            fields["Remarks"] = narr
    # NTB：Remarks/Description 兜底写入后再剥一次水印乱码（如 NatiPU8QAW）
    if bank == "ntb":
        for key in ("Description", "Remarks"):
            if not fields.get(key):
                continue
            cleaned = _scrub_ntb_watermark_glue(str(fields[key]))
            if cleaned:
                fields[key] = cleaned
            else:
                fields.pop(key, None)
        if fields.get("Description") and not fields.get("Remarks"):
            fields["Remarks"] = fields["Description"]
    # 时间字段统一成 24 小时制（YYYY-MM-DD HH:MM:SS），去掉 AM/PM 与点号分隔
    for k in list(fields.keys()):
        if k in ("TIME",):
            # CDM 的 TIME 保持 HH:MM，避免被解析成仅时间失败后丢掉
            if re.match(r"^\s*([01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\s*$", fields[k] or ""):
                continue
        if "date" in k.lower() or "time" in k.lower():
            parsed = _parse_datetime(fields[k])
            if parsed:
                fields[k] = parsed.replace("T", " ")
                # 扁平 Date & Time 更可信时回写结构化 datetime
                if "date" in k.lower() and "time" in k.lower():
                    dt = parsed

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
        fields=fields,
        deposit_breakdown=deposit_breakdown,
        branch=branch,
        terminal_id=terminal_id,
        trace_no=trace_no,
        warnings=warnings,
        lines=[OcrLineOut(text=l.text, confidence=l.confidence, box=l.box) for l in lines] if include_lines else [],
    )
