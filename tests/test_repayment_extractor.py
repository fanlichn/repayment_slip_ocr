"""还款/转账凭证抽取的单元测试。

用真实样本（People's Bank / BOC / Pan Asia / Commercial Bank e-Receipt /
ATM 存款凭条）的关键文字构造 OCR 行，验证字段抽取与校验。
运行：pytest -q tests/test_repayment_extractor.py
"""
from __future__ import annotations

from app.ocr_engine import OcrLine
from repayment_slip_ocr.extractor import extract


def _line(text: str, y: float, conf: float = 0.9, h: float = 40.0) -> OcrLine:
    box = [
        [100, y - h / 2],
        [100 + len(text) * 18, y - h / 2],
        [100 + len(text) * 18, y + h / 2],
        [100, y + h / 2],
    ]
    return OcrLine(text=text, confidence=conf, box=box)


def _make(rows):
    """rows: list of (text, y)"""
    return [_line(t, y) for t, y in rows]


def test_peoples_bank_confirmation():
    rows = [
        ("Transaction confirmation", 40),
        ("Receipt", 80),
        ("Your payment has been successfully completed", 120),
        ("Pay from", 200),
        ("Bank People's Bank", 240),
        ("Account No 138200******20", 280),
        ("Account Currency LKR", 320),
        ("Name MMDA MALLAWA", 360),
        ("Pay to", 420),
        ("Name Lak Artha (Pvt) Ltd", 460),
        ("Bank Name Commercial Bank PLC", 500),
        ("Account No 1001096962", 540),
        ("Amount (LKR) 6,900.00", 600),
        ("Fee Amount (LKR) 25.00", 640),
        ("Total debit amount (LKR) 6,925.00", 680),
        ("Date & Time 2026/10/08 08:08:32", 720),
    ]
    r = extract(_make(rows))

    assert r.doc_type == "payment_confirmation"
    assert r.status == "success"
    assert r.payer.name == "MMDA MALLAWA"
    assert r.payer.account == "138200******20"
    assert r.payer.bank == "People's Bank"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank PLC"
    assert r.amount == 6900.0
    assert r.fee == 25.0
    assert r.total_debit == 6925.0
    assert r.datetime == "2026-10-08T08:08:32"
    assert r.warnings == []
    assert r.success is True


def test_boc_sender_beneficiary_accounts():
    rows = [
        ("Fund Transfer Receipt", 40),
        ("Transaction Amount LKR 5,000.00", 80),
        ("Transaction Date & Time 08-10-2026 11:28 AM", 120),
        ("Transaction ID FX10812413500000", 160),
        ("Charges & Fee LKR 25.00", 200),
        ("Remarks 0757576687", 240),
        ("Account Number **3936", 300),
        ("Sender's Name MR A S P D M GUNASINGHA", 340),
        ("Sender's Bank Bank of Ceylon", 380),
        ("Account Number 1001096962", 440),
        ("Beneficiary Name Lak Artha service", 480),
        ("Beneficiary Bank Commercial Bank", 520),
    ]
    r = extract(_make(rows))

    assert r.doc_type == "fund_transfer_receipt"
    assert r.amount == 5000.0
    assert r.fee == 25.0
    assert r.datetime == "2026-10-08T11:28:00"
    assert r.payer.name == "MR A S P D M GUNASINGHA"
    assert r.payer.account == "**3936"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"  # 归一化
    assert r.payee.account == "1001096962"
    assert r.references.transaction_id == "FX10812413500000"
    assert r.references.remarks == "0757576687"


def test_pan_asia_fund_transfer_receipt():
    rows = [
        ("Fund Transfer Receipt", 40),
        ("LKR 37,800.00", 80),
        ("08 Oct 2026 10:43 am", 120),
        ("Pay From", 200),
        ("Account Name H M D S DISSANAYAKA", 240),
        ("Account Number 2023****1513", 280),
        ("Bank Pan Asia Bank", 320),
        ("Pay To", 400),
        ("Account Name Lak Artha pvt ltd", 440),
        ("Account Number 1001096962", 480),
        ("Bank Commercial Bank Of Ceylon PLC", 520),
        ("Txn Ref 20260000000795909", 600),
        ("Retrieval Ref 628110632417", 640),
        ("My Ref NIC 871420076V", 680),
        ("Receiver Ref DIMUTHU", 720),
    ]
    r = extract(_make(rows))

    assert r.doc_type == "fund_transfer_receipt"
    assert r.amount == 37800.0
    assert r.datetime == "2026-10-08T10:43:00"
    assert r.payer.name == "H M D S DISSANAYAKA"
    assert r.payer.account == "2023****1513"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.references.txn_ref == "20260000000795909"
    assert r.references.retrieval_ref == "628110632417"
    assert r.references.my_ref == "NIC 871420076V"
    assert r.references.receiver_ref == "DIMUTHU"


def test_commercial_bank_e_receipt():
    rows = [
        ("Transfer within ComBank", 40),
        ("e-Receipt", 80),
        ("Bank Reference Number O600069434117", 120),
        ("Sender's Account Number 81******36", 160),
        ("Sender's Name MRS ABDUL CARDER FATHIMA SIMAYA", 200),
        ("Transfer Amount 5,000.00", 240),
        ("Transfer Currency LKR", 280),
        ("Beneficiary Name LAK ARTHA SERVICES (PVT) LTD", 320),
        ("Beneficiary Account Currency LKR", 360),
        ("Beneficiary Account Number 1001096962", 400),
        ("Beneficiary's Account Narration yhbbn", 440),
        ("Transaction Date/Time 08/10/2026 11:44 AM", 480),
        ("Status Completed", 520),
        ("e-Receipt Reference 855D-1263-8AE1-F237", 560),
    ]
    r = extract(_make(rows))

    assert r.doc_type == "e_receipt"
    assert r.status == "success"
    assert r.amount == 5000.0
    assert r.datetime == "2026-10-08T11:44:00"
    assert r.payer.name == "MRS ABDUL CARDER FATHIMA SIMAYA"
    assert r.payer.account == "81******36"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.references.bank_reference_number == "O600069434117"
    assert r.references.e_receipt_reference == "855D-1263-8AE1-F237"
    assert r.references.remarks == "yhbbn"


def test_atm_cardless_deposit():
    rows = [
        ("COMMERCIAL BANK OF CEYLON PLC", 40),
        ("KOHUWALA-CRM2 BR", 80),
        ("DATE 07/10/26", 120),
        ("TIME 18:12", 160),
        ("TERMINAL ID RKOHUWA2HT", 200),
        ("TRACE 5932", 240),
        ("TRANSACTION CARDLESS DEPOSIT", 280),
        ("ACCOUNT NUMBER 1001096962", 320),
        ("CUSTOMER NAME LAK ARTHA SERVICES", 360),
        ("100 1 100.00", 420),
        ("500 1 500.00", 460),
        ("1000 1 1000.00", 500),
        ("5000 4 20000.00", 540),
        ("DEPOSIT AMOUNT LKR 21,600.00", 600),
        ("TRANSACTION STATUS SUCCESSFUL", 640),
    ]
    r = extract(_make(rows))

    assert r.doc_type == "cash_deposit_slip"
    assert r.status == "success"
    assert r.amount == 21600.0
    assert r.datetime == "2026-10-07T18:12:00"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.payer.name is None  # 现金存款无付款方
    assert len(r.deposit_breakdown) == 4
    assert sum(d.amount for d in r.deposit_breakdown) == 21600.0
    # 纸币明细加总 == 存款总额，无警告
    assert not any("加总" in w for w in r.warnings)


def test_cdm_field_labels():
    """CDM 无卡存款凭条：单行 Label : Value 字段应完整提取，空值字段不误取下一标签。"""
    rows = [
        ("COMMERCIAL BANK", 40),
        ("COMMERCIAL BANK OF CEYLON PLC", 80),
        ("BANDARAG-CRM2 BR", 120),
        ("DATE TIME TERMINAL ID", 160),
        ("09/10/26 08:14 RBANDAR2HT", 200),
        ("TRACE 5107", 240),
        ("TRANSACTION : CARDLESS DEPOSIT", 280),
        ("ACCOUNT NUMBER: 1001096962", 320),
        ("CUSTOMER NAME :LAK ARTHA SERVICES", 360),
        ("NARRATION:", 400),
        ("MOBILE NO. :", 440),
        ("SOURCE OF FUNDS:UNKNOWN", 480),
        ("NOTES VALUE AMOUNT", 520),
        ("1 LKR 100.00 100.00", 560),
        ("1 LKR 1,000.00 1,000.00", 600),
        ("1 LKR 5,000.00 5,000.00", 640),
        ("DEPOSIT AMOUNT: LKR 6,100.00", 680),
        ("TRANSACTION STATUS : SUCCESSFUL", 720),
        ("THANK YOU FOR BANKING WITH US", 760),
    ]
    r = extract(_make(rows))

    assert r.doc_type == "cash_deposit_slip"
    assert r.fields["TRANSACTION"] == "CARDLESS DEPOSIT"
    assert r.fields["ACCOUNT NUMBER"] == "1001096962"
    assert r.fields["CUSTOMER NAME"] == "LAK ARTHA SERVICES"
    assert r.fields["SOURCE OF FUNDS"] == "UNKNOWN"
    assert r.fields["DEPOSIT AMOUNT"] == "LKR 6,100.00"
    assert r.fields["TRANSACTION STATUS"] == "SUCCESSFUL"
    assert r.fields["TRACE"] == "5107"
    # 空值字段不应误取下一标签
    assert "NARRATION" not in r.fields
    assert "MOBILE NO." not in r.fields


def test_cdm_real_ocr_field_labels():
    """CDM 凭条真实 OCR：ACC0UNT(0→O)、DEPOSIT AMOUNT 拆分 LKR+金额、面额表 AMOUNT 干扰。"""
    lines = [
        _lr("TRACE", 209, 467, 323, 519),
        _lr("5107", 455, 483, 540, 527),
        _lr("TRANSACTION", 214, 593, 442, 634),
        _lr(": CARDLESS DEPOSIT", 496, 602, 832, 635),
        _lr("ACC0UNT NUMBER: 1001096962", 218, 677, 721, 710),
        _lr("CUSTOMER NAME :LAK ARTHA SERVICES", 216, 753, 854, 788),
        _lr("NARRATION:", 212, 861, 420, 912),
        _lr("MOBILE NO. :", 212, 974, 443, 1033),
        _lr("SOURCE OF FUNDS:UNKNOWN", 214, 1036, 673, 1109),
        _lr("NOTES", 206, 1177, 329, 1235),
        _lr("VALUE", 394, 1159, 508, 1213),
        _lr("AMOUNT", 821, 1146, 943, 1190),
        _lr("DEPOSIT AMOUNT:", 217, 1390, 520, 1465),
        _lr("LKR", 589, 1374, 664, 1422),
        _lr("6,100.00", 784, 1371, 948, 1415),
    ]
    r = extract(lines)

    assert r.doc_type == "cash_deposit_slip"
    assert r.fields["ACCOUNT NUMBER"] == "1001096962"
    assert r.fields["DEPOSIT AMOUNT"] == "6,100.00"
    assert r.fields["TRANSACTION"] == "CARDLESS DEPOSIT"
    assert r.fields["CUSTOMER NAME"] == "LAK ARTHA SERVICES"
    assert r.fields["SOURCE OF FUNDS"] == "UNKNOWN"
    assert r.fields["TRACE"] == "5107"
    # 空值字段不误取面额表表头 / 下一标签
    assert "MOBILE NO." not in r.fields
    assert "NARRATION" not in r.fields


def test_cdm_deposit_amount_with_space_after_comma():
    """CDM 无卡存款凭条：OCR 把 '5,000.00' 读成 '5, 000.00'（逗号后有空格）。"""
    rows = [
        ("COMMERCIAL BANK OF CEYLON PLC", 40),
        ("KATUKURU-CRM1 BR", 80),
        ("DATE 18/08/26", 120),
        ("TIME 16:14", 160),
        ("TERMINAL ID RKATUKU1HT", 200),
        ("TRACE 8495", 240),
        ("TRANSACTION CARDLESS DEPOSIT", 280),
        ("ACCOUNT NUMBER 1001096962", 320),
        ("CUSTOMER NAME LAK ARTHA SERVICES", 360),
        ("NOTES VALUE AMOUNT", 400),
        ("1 LKR 5, 000.00 5, 000.00", 440),
        ("DEPOSIT AMOUNT LKR 5, 000.00", 500),
        ("TRANSACTION STATUS SUCCESSFUL", 540),
    ]
    r = extract(_make(rows))
    assert r.bank == "commercial_bank"
    assert r.doc_type == "cash_deposit_slip"
    assert r.amount == 5000.0
    assert r.total_debit == 5000.0
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.datetime == "2026-08-18T16:14:00"
    # 明细加总 == 总额，无警告
    assert not any("加总" in w for w in r.warnings)


def test_cdm_deposit_amount_comma_read_as_dot():
    """CDM 无卡存款凭条：OCR 把千分位逗号读成点（'5.000.00'）。"""
    rows = [
        ("COMMERCIAL BANK OF CEYLON PLC", 40),
        ("KATUKURU-CRM1 BR", 80),
        ("DATE 18/08/26", 120),
        ("TIME 16:14", 160),
        ("TRANSACTION CARDLESS DEPOSIT", 280),
        ("ACCOUNT NUMBER 1001096962", 320),
        ("CUSTOMER NAME LAK ARTHA SERVICES", 360),
        ("DEPOSIT AMOUNT LKR 5.000.00", 500),
        ("TRANSACTION STATUS SUCCESSFUL", 540),
    ]
    r = extract(_make(rows))
    assert r.amount == 5000.0
    assert r.total_debit == 5000.0


def test_cdm_datetime_split_lines():
    """CDM 凭条：OCR 把 DATE/TIME 标签和值拆成独立行，时间仍应被提取。"""
    rows = [
        ("COMMERCIAL BANK OF CEYLON PLC", 40),
        ("NARAHENP-CRM1 BR", 80),
        ("DATE", 120),
        ("25/09/26", 125),
        ("TIME", 120),
        ("16:22", 125),
        ("TERMINAL ID", 120),
        ("RNARAHN1HT", 125),
        ("TRANSACTION CARDLESS DEPOSIT", 280),
        ("ACCOUNT NUMBER 1001096962", 320),
        ("CUSTOMER NAME LAK ARTHA SERVICES", 360),
        ("DEPOSIT AMOUNT LKR 5,000.00", 500),
        ("TRANSACTION STATUS SUCCESSFUL", 540),
    ]
    r = extract(_make(rows))
    assert r.datetime == "2026-09-25T16:22:00"
    assert r.amount == 5000.0
    assert r.payee.name == "Lak Artha (Pvt) Ltd"


def test_cdm_date_time_terminal_header_fields():
    """CDM 凭条：DATE/TIME/TERMINAL ID 为并排表头、值在各自下方，应分别提取。"""
    lines = [
        _lr("DATE", 416, 493, 521, 541),
        _lr("30/10/26", 421, 546, 612, 586),
        _lr("TIME", 702, 497, 806, 546),
        _lr("09:28", 702, 546, 828, 592),
        _lr("TERMINAL ID", 962, 499, 1221, 555),
        _lr("RAKKARA1HT", 962, 545, 1199, 602),
        _lr("TRACE", 416, 632, 543, 681),
        _lr("1480", 702, 632, 806, 683),
        _lr("TRANSACTION", 421, 774, 684, 812),
        _lr(": CARDLESS DEPOSIT", 743, 774, 1173, 817),
        _lr("ACCOUNT NUMBER: 1001096962", 414, 859, 1035, 908),
        _lr("CUSTOMER NAME :LAK ARTHA SERVICES", 414, 954, 1199, 999),
        _lr("SOURCE OF FUNDS:UNKNOWN", 408, 1331, 965, 1369),
        _lr("DEPOSIT AMOUNT:", 394, 1809, 762, 1843),
        _lr("LKR", 856, 1797, 944, 1846),
        _lr("7,900.00", 1100, 1793, 1298, 1835),
        _lr("TRANSACTION STATUS : SUCCESSFUL", 473, 1900, 1220, 1926),
    ]
    r = extract(lines)

    assert r.doc_type == "cash_deposit_slip"
    assert r.terminal_id == "RAKKARA1HT"
    assert r.trace_no == "1480"
    assert r.datetime == "2026-10-30T09:28:00"
    assert r.fields["TERMINAL ID"] == "RAKKARA1HT"
    assert r.fields["TIME"] == "09:28"
    assert r.fields["DATE"] == "2026-10-30 00:00:00"


def test_cdm_amount_with_notes_header():
    """CDM 凭条：含 NOTES VALUE AMOUNT 表头行，不应取错金额。"""
    rows = [
        ("COMMERCIAL BANK OF CEYLON PLC", 40),
        ("TRANSACTION CARDLESS DEPOSIT", 280),
        ("ACCOUNT NUMBER 1001096962", 320),
        ("CUSTOMER NAME LAK ARTHA SERVICES", 360),
        ("NOTES VALUE AMOUNT", 400),
        ("1 LKR 5.000.00 5.000.00", 440),
        ("DEPOSIT AMOUNT LKR 5.000.00", 500),
        ("TRANSACTION STATUS SUCCESSFUL", 540),
    ]
    r = extract(_make(rows))
    assert r.amount == 5000.0
    assert r.total_debit == 5000.0
    assert not any("加总" in w for w in r.warnings)


def test_cdm_real_ocr_noise():
    """CDM 凭条实际 OCR 噪声：损坏标签/日期行不影响金额和时间提取。"""
    rows = [
        ("COMMERCIAL BANK OF CEYLON PLC", 590),
        ("NARAHENP-CRM1 BR", 670),
        ("DATE", 785),
        ("2509/26", 815),
        ("25/09/26", 815),
        ("TIME", 770),
        ("16:22", 805),
        ("TERMINAL ID", 755),
        ("RNARAHN1HT", 790),
        ("TRACE", 880),
        ("9122", 870),
        ("TRANSACTION CARDLESS DEPOSIT", 960),
        ("ACCOUNT NUMBER 1001096962", 1030),
        ("CUSTOMER NAME LAK ARTHA SERVICES", 1090),
        ("NARRATION TRECORY", 1200),
        ("MOBILE NO.", 1300),
        ("SOURCE OF FUNDS UNKNOWN", 1370),
        ("NOTES", 1475),
        ("VALUE", 1475),
        ("AMOUNT", 1465),
        ("LKR 5.000.00", 1540),
        ("5.000.00", 1535),
        ("DEPOSIT AMOUNT", 1620),
        ("5.000.00", 1610),
        ("JF11jS11 AMOUNT", 1615),  # OCR 损坏标签行，应产生 11.0 噪声
        ("TRANSACTION STATUS SUCCESSFUL", 1685),
    ]
    r = extract(_make(rows))
    assert r.bank == "commercial_bank"
    assert r.doc_type == "cash_deposit_slip"
    assert r.amount == 5000.0
    assert r.total_debit == 5000.0
    assert r.datetime == "2026-09-25T16:22:00"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert not any("加总" in w for w in r.warnings)


def test_cdm_transaction_type_not_amount_label():
    """CDM 凭条：'CARDLESS DEPOSIT' 是交易类型不是金额标签，其右下方的收据外噪点
    数字（如 '13'）不应被当作金额。"""
    from app.ocr_engine import OcrLine

    def _at(text: str, x: float, y: float, h: float = 60.0) -> OcrLine:
        w = len(text) * 22
        return OcrLine(text=text, confidence=0.95, box=[
            [x, y - h / 2], [x + w, y - h / 2], [x + w, y + h / 2], [x, y + h / 2],
        ])

    lines = [
        _at("COMMERCIAL BANK OF CEYLON PLC", 450, 630),
        _at("WARAKAPO-CRM1 BR", 850, 750),
        _at("DATE", 786, 931),
        _at("26/09/26", 786, 993),
        _at("TIME", 1168, 928),
        _at("11:31", 1161, 988),
        _at("TERMINAL ID", 1512, 926),
        _at("RWARAKAIHT", 1512, 988),
        _at("TRACE", 786, 1115),
        _at("3785", 1162, 1111),
        _at("TRANSACTION", 789, 1299),
        _at("CARDLESS DEPOSIT", 1289, 1292),
        _at("13", 2289, 1429),  # 收据外的噪点数字
        _at("ACCOUNT NUMBER:1001096962", 783, 1418),
        _at("CUSTOMER NAME :LAK ARTHA SERVICES", 780, 1542),
        _at("DEPOSIT AMOUNT", 767, 2569),
        _at("LKR", 1388, 2566),
        _at("5.100.00", 1719, 2561),
        _at("TRANSACTION STATUS :SUCCESSFUL", 872, 2700),
    ]
    r = extract(lines)
    assert r.doc_type == "cash_deposit_slip"
    assert r.amount == 5100.0
    assert r.total_debit == 5100.0
    assert not any("加总" in w for w in r.warnings)


def test_cdm_denom_ocr_letter_misread_and_total_noise():
    """CDM 凭条：面额行字母误读（1.000.0Q）+ 总额读成前导零串（000008）。

    真实面额：1000 x 3 + 5000 x 1 = 8000
    OCR 损坏：LKR1.000.0Q（Q 是 0 的误读）、LKR 5.00000（丢了小数点）、
    总额 8,000.00 读成 000008。
    """
    from app.ocr_engine import OcrLine

    def _at(text: str, x: float, y: float, h: float = 60.0) -> OcrLine:
        w = len(text) * 22
        return OcrLine(text=text, confidence=0.95, box=[
            [x, y - h / 2], [x + w, y - h / 2], [x + w, y + h / 2], [x, y + h / 2],
        ])

    lines = [
        _at("COMMERCIAL BANK OF CEYLON PLC", 249, 786),
        _at("MAHARAGA-CRMI BR", 416, 880),
        _at("DATE", 162, 1011),
        _at("07/10/26", 160, 1061),
        _at("TIME", 462, 1021),
        _at("17:01", 461, 1069),
        _at("TERMINAL ID", 734, 1030),
        _at("RMAHARATHT", 728, 1080),
        _at("TRACE", 162, 1156),
        _at("2519", 453, 1165),
        _at("TRANSACTION", 163, 1292),
        _at("CARDLESS DEPOSIT", 546, 1306),
        _at("ACCOUNT NUMBER1001096962", 157, 1390),
        _at("CUSTOMER NAMELAK ARTHA SERVICES", 151, 1486),
        _at("NARRATION:UDAYANGA", 145, 1623),
        _at("MOBILE NO", 137, 1764),
        _at("SOURCE OF FUNDSUNKNOWN", 136, 1860),
        _at("NOTES", 130, 1997),
        _at("VALUE", 352, 2000),
        _at("AMOUNT", 877, 1995),
        _at("3", 254, 2088),
        _at("LKR1.000.0Q", 352, 2089),
        _at("3.000.00", 825, 2079),
        _at("LKR 5.00000", 346, 2135),
        _at("5.000.00", 816, 2122),
        _at("DEPOSIT AMOUNT", 128, 2217),
        _at("LKR", 583, 2215),
        _at("000008", 809, 2195),
        _at("TRANSACTION STATUS", 210, 2298),
        _at("SUCCESSFUL", 692, 2279),
    ]
    r = extract(lines)
    assert r.doc_type == "cash_deposit_slip"
    assert r.amount == 8000.0
    assert r.total_debit == 8000.0
    denoms = {(d.denomination, d.quantity) for d in r.deposit_breakdown}
    assert (1000.0, 3) in denoms
    assert (5000.0, 1) in denoms
    assert not any("加总" in w for w in r.warnings)


def test_cdm_quantity_ocr_duplicate_variant():
    """CDM 凭条：同一数量被 OCR 识别成多个变体（"8" 和 "18"），
    应按 y 去重保留置信度最高的，避免与面额行按索引配对时错位。

    真实面额：100 x 8 + 500 x 1 + 1000 x 3 + 5000 x 1 = 9300
    OCR 损坏：数量 "8" 被同时识别为 "8"（conf 0.984）和 "18"（conf 0.574）。
    """
    from app.ocr_engine import OcrLine

    def _at(text: str, x: float, y: float, h: float = 32.0, conf: float = 0.95) -> OcrLine:
        w = len(text) * 16
        return OcrLine(text=text, confidence=conf, box=[
            [x, y - h / 2], [x + w, y - h / 2], [x + w, y + h / 2], [x, y + h / 2],
        ])

    lines = [
        _at("COMMERCIAL BANK OF CEYLON PLC", 329, 412),
        _at("RATNAPUR-CRM1 BR", 440, 476),
        _at("DATE", 278, 574),
        _at("30/06/26", 276, 606),
        _at("TIME", 474, 571),
        _at("17:30", 476, 603),
        _at("TERMINAL ID", 652, 566),
        _at("RRATNARIHT", 649, 600),
        _at("TRACE", 281, 670),
        _at("5581", 474, 667),
        _at("TRANSACTION", 283, 764),
        _at("CARDLESS DEPOSIT", 540, 761),
        _at("ACCOUNT NUMBER", 283, 827),
        _at("1001096962", 537, 824),
        _at("CUSTOMER NAME LAK ARTHA SERVICES", 281, 888),
        _at("NARRATION:NIMESH 811002542V", 281, 984),
        _at("MOBILE NO", 281, 1080),
        _at("SOURCE OF FUNDS:UNKNOWN", 285, 1144),
        _at("NOTES", 281, 1239),
        _at("VALUE", 424, 1240),
        _at("AMOUNT", 784, 1241),
        # 数量列："8" 被 OCR 识别成两个变体
        _at("8", 360, 1302, conf=0.984),
        _at("18", 358, 1302, conf=0.574),
        _at("1", 358, 1335),
        _at("3", 360, 1365),
        # 面额列
        _at("100.00", 527, 1303),
        _at("500.00", 522, 1335),
        _at("LKR 1.000.00", 423, 1366),
        _at("LKR5.000.00", 423, 1398),
        # 金额列
        _at("800.00", 784, 1304),
        _at("500.00", 786, 1337),
        _at("3.000.00", 752, 1368),
        _at("5.000.00", 750, 1400),
        _at("DEPOSIT AMOUNT", 283, 1457),
        _at("LKR", 583, 1461),
        _at("9.300.00", 750, 1463),
        _at("TRANSACTION STATUS", 333, 1520),
        _at("SUCCESSFUL", 664, 1524),
    ]
    r = extract(lines)
    assert r.doc_type == "cash_deposit_slip"
    assert r.amount == 9300.0
    assert r.total_debit == 9300.0
    denoms = {(d.denomination, d.quantity) for d in r.deposit_breakdown}
    assert (100.0, 8) in denoms
    assert (500.0, 1) in denoms
    assert (1000.0, 3) in denoms
    assert (5000.0, 1) in denoms
    assert not any("加总" in w for w in r.warnings)


def test_parse_denomination_rejects_ocr_noise():
    """面额解析：含字母的 OCR 损坏行应返回 None，避免误解析。"""
    from repayment_slip_ocr.extractor import _parse_denomination
    assert _parse_denomination("LKR 5.000.00") == 5000.0
    assert _parse_denomination("LKR5.000.00") == 5000.0
    assert _parse_denomination("LKR 5 0OU OO") is None  # OCR 把 000 读成 0OU
    assert _parse_denomination("5 000 0U") is None
    assert _parse_denomination("LKR 1,000.00") == 1000.0


def test_parse_datetime_mm_dd_fallback():
    """美式 MM/DD 日期（如 "10.27.2026"）在 DD/MM 解析失败时应兜底解析。"""
    from repayment_slip_ocr.extractor import _parse_datetime
    assert _parse_datetime("10.27.2026 , 01:38 PM") == "2026-10-27T13:38:00"
    assert _parse_datetime("10.08.2026 , 06:45 PM") == "2026-08-10T18:45:00"  # 仍按 DD/MM


def test_app_loan_page_is_rejected():
    """还款 App 的「发起还款」页面不是银行凭证，应返回 success=false。"""
    rows = [
        ("Total amount Due", 200),
        ("5000", 240),
        ("Loan amount: 5000", 300),
        ("Due Date: 2026-06-03", 340),
        ("Upload repayment screenshot", 420),
        ("Repayment screenshot", 500),
        ("Camera", 600),
        ("Album", 640),
        ("Cancel", 680),
    ]
    r = extract(_make(rows))
    assert r.doc_type == "unknown"
    assert r.success is False
    assert any("不是银行交易凭证" in w for w in r.warnings)


def test_amount_mismatch_warns():
    rows = [
        ("Amount (LKR) 6,900.00", 100),
        ("Fee Amount (LKR) 25.00", 140),
        ("Total debit amount (LKR) 6,900.00", 180),  # 少了手续费
    ]
    r = extract(_make(rows))
    assert r.amount == 6900.0
    assert r.fee == 25.0
    assert r.total_debit == 6900.0
    assert any("金额校验不一致" in w for w in r.warnings)


def _lr(text: str, x0: float, y0: float, x1: float, y1: float, conf: float = 0.9) -> OcrLine:
    return OcrLine(text=text, confidence=conf, box=[[x0, y0], [x1, y0], [x1, y1], [x0, y1]])


def test_commercial_bank_e_receipt_two_column():
    """真实 Commercial Bank e-Receipt：左列标签、右列值两栏布局。"""
    lines = [
        # 左列标签
        _lr("Sender's Name", 40, 535, 219, 566),
        _lr("Bank Reference Number", 41, 446, 326, 488),
        _lr("Sender's Account Number", 40, 496, 349, 524),
        _lr("Beneficiary Name", 41, 649, 251, 686),
        _lr("Beneficiary Account Number", 40, 730, 384, 767),
        _lr("Transfer Amount", 43, 574, 251, 605),
        _lr("Transfer Currency", 41, 610, 263, 647),
        _lr("Beneficiary's Account Currency", 41, 688, 413, 728),
        _lr("Beneficiary's Account Narration", 43, 772, 418, 800),
        _lr("Transaction Date/Time", 41, 805, 320, 839),
        _lr("Payment Date", 43, 847, 213, 878),
        _lr("Status", 43, 884, 124, 914),
        # 右列值
        _lr("MRS ABDUL CARDER FATHIMA SIMAYA", 588, 530, 1044, 566),
        _lr("0600069434117", 591, 452, 796, 482),
        _lr("81******36", 587, 484, 730, 530),
        _lr("LAK ARTHA SERVICES (PVT) LTD", 588, 655, 963, 683),
        _lr("1001096962", 588, 733, 747, 764),
        _lr("5,000.00", 588, 574, 704, 605),
        _lr("LKR", 586, 613, 640, 647),
        _lr("yhbbn", 588, 772, 672, 803),
        _lr("08/10/2026 11:44 AM", 588, 806, 865, 842),
        _lr("08-10-26", 584, 836, 708, 882),
        _lr("Completed", 591, 884, 727, 914),
        # 其它
        _lr("e-Receipt", 133, 376, 231, 407),
        _lr("[e-Receipt Reference 855D-1263-BAE1-F237]", 38, 937, 479, 964),
        _lr("Transfer within ComBank", 352, 365, 802, 404),
    ]
    r = extract(lines)

    assert r.doc_type == "e_receipt"
    assert r.status == "success"
    assert r.payer.name == "MRS ABDUL CARDER FATHIMA SIMAYA"
    assert r.payer.account == "81******36"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.amount == 5000.0
    assert r.datetime == "2026-10-08T11:44:00"
    assert r.references.bank_reference_number == "0600069434117"
    assert r.references.e_receipt_reference == "855D-1263-BAE1-F237"
    assert r.references.remarks == "yhbbn"

    # 扁平字段：key 用单据原始英文字段名，value 为原文
    assert r.fields["Bank Reference Number"] == "0600069434117"
    assert r.fields["Sender's Account Number"] == "81******36"
    assert r.fields["Sender's Name"] == "MRS ABDUL CARDER FATHIMA SIMAYA"
    assert r.fields["Transfer Amount"] == "5,000.00"
    assert r.fields["Beneficiary Account Number"] == "1001096962"
    assert r.fields["Beneficiary's Account Narration"] == "yhbbn"
    assert r.fields["Status"] == "Completed"


def test_commercial_bank_e_receipt_ocr_colon_amount():
    """Commercial Bank e-Receipt：金额小数点被 OCR 误读为冒号（"2,500:00"），
    且 Beneficiary's Account Currency 应纳入输出、Narration 不应串入后续字段值。"""
    L = lambda txt, x0, x1, y: _lr(txt, x0, y - 14, x1, y + 14)
    lines = [
        L("e-Receipt", 133, 231, 390),
        L("Transfer within ComBank", 352, 802, 400),
        L("Bank Reference Number", 41, 326, 446),
        L("O600072786183", 588, 800, 446),
        L("Sender's Account Number", 40, 349, 496),
        L("80******82", 587, 730, 496),
        L("Sender's Name", 40, 219, 535),
        L("MRN P C HN SANJEEWA ABERATHNE", 588, 1044, 535),
        L("Transfer Amount", 43, 251, 574),
        L("2,500:00", 588, 704, 574),
        L("Transfer Currency", 41, 263, 610),
        L("LKR", 586, 640, 610),
        L("Beneficiary Name", 41, 251, 649),
        L("LAK ARTHA SERVICES (PVT)LTD", 588, 963, 649),
        L("Beneficiary's Account Currency", 41, 413, 688),
        L("LKR", 586, 640, 688),
        L("Beneficiary Account Number", 40, 384, 730),
        L("1001096962", 588, 747, 730),
        L("Beneficiary's Account Narration", 43, 418, 772),
        L("Z5B379", 588, 672, 772),
        L("Transaction Date/Time", 41, 320, 805),
        L("21/10/202604.04AM", 588, 865, 805),
        L("Payment Date", 43, 213, 847),
        L("21-10-26", 584, 708, 847),
        L("Status", 43, 124, 884),
        L("Completed", 591, 727, 884),
    ]
    r = extract(lines)

    assert r.bank == "commercial_bank"
    assert r.doc_type == "e_receipt"
    assert r.amount == 2500.0
    assert r.fields["Bank Reference Number"] == "O600072786183"
    assert r.fields["Transfer Amount"] == "2,500.00"  # 冒号还原为小数点
    assert r.fields["Beneficiary's Account Currency"] == "LKR"
    assert r.fields["Beneficiary Account Number"] == "1001096962"
    # 不串值：Narration 只应包含 Z5B379
    assert r.fields["Beneficiary's Account Narration"] == "Z5B379"
    assert r.fields["Status"] == "Completed"


def test_commercial_bank_e_receipt_dedup_ocr_variants():
    """同一视觉行的多个 OCR 变体（0↔O、冒号↔小数点、截断掩码）应按 y 去重，只保留一个。"""
    L = lambda txt, x0, x1, y, conf=0.9: _lr(txt, x0, y - 14, x1, y + 14, conf)
    lines = [
        L("e-Receipt", 133, 231, 390),
        L("Bank Reference Number", 41, 326, 446),
        L("O600072786183", 588, 800, 446, 0.99),
        L("0600072786183", 588, 800, 447, 0.95),
        L("Sender's Account Number", 40, 349, 496),
        L("80******82", 587, 730, 496, 0.99),
        L("80****82", 587, 730, 497, 0.91),
        L("**82", 587, 730, 498, 0.89),
        L("Transfer Amount", 43, 251, 574),
        L("2,500:00", 588, 704, 574, 0.99),
        L("2,500.00", 588, 704, 575, 0.95),
        L("Status", 43, 124, 884),
        L("Completed", 591, 727, 884),
    ]
    r = extract(lines)

    assert r.fields["Bank Reference Number"] == "O600072786183"
    assert r.fields["Sender's Account Number"] == "80******82"
    assert r.fields["Transfer Amount"] == "2,500.00"
    assert r.fields["Status"] == "Completed"


def test_commercial_bank_e_receipt_apostrophe_account():
    """ComBank e-Receipt：'Beneficiary's Account Number'（带撇号 s）应识别账号。"""
    L = lambda txt, x0, x1, y: _lr(txt, x0, y - 14, x1, y + 14)
    lines = [
        L("e-Receipt", 133, 231, 390),
        L("Beneficiary's Account Number", 134, 1369, 1504),
        L("1001096962", 1986, 2490, 1504),
    ]
    r = extract(lines)
    assert r.bank == "commercial_bank"
    assert r.fields["Beneficiary's Account Number"] == "1001096962"


def test_sampath_vishwa_two_column_fields():
    """Sampath Vishwa 回执应返回图片原始字段名 -> 原文值映射。"""
    lines = [
        _lr("Sampath Vishwa Mobile - Online Transfer", 220, 150, 720, 190),
        _lr("Status", 48, 332, 168, 368),
        _lr("Success", 430, 332, 560, 368),
        _lr("Transaction ID", 48, 390, 260, 426),
        _lr("89101292", 430, 390, 570, 426),
        _lr("Date & Time", 48, 448, 246, 484),
        _lr("09/10/2026 01:19 PM", 430, 448, 720, 484),
        _lr("Source Account Number", 48, 506, 344, 542),
        _lr("*******2918", 430, 506, 620, 542),
        _lr("Amount", 48, 564, 170, 600),
        _lr("LKR 5,500.00", 430, 564, 640, 600),
        _lr("Beneficiary Name", 48, 622, 290, 658),
        _lr("Lak Artha Pvt Ltd", 430, 622, 710, 658),
        _lr("Beneficiary Account No.", 48, 680, 372, 716),
        _lr("1001096962", 430, 680, 610, 716),
        _lr("Beneficiary Remarks", 48, 738, 336, 774),
        _lr("913171047v", 430, 738, 610, 774),
        _lr("Destination Bank", 48, 796, 286, 832),
        _lr("COMMERCIAL BANK OF", 430, 796, 760, 832),
        _lr("CEYLON", 430, 840, 570, 876),
        _lr("VISHWA", 690, 140, 810, 190),
    ]
    r = extract(lines)

    assert r.bank == "vishwa"
    assert r.fields["Status"] == "Success"
    assert r.fields["Transaction ID"] == "89101292"
    assert r.fields["Date & Time"] == "2026-10-09 13:19:00"
    assert r.fields["Source Account Number"] == "*******2918"
    assert r.fields["Amount"] == "LKR 5,500.00"
    assert r.fields["Beneficiary Name"] == "Lak Artha Pvt Ltd"
    assert r.fields["Beneficiary Account No."] == "1001096962"
    assert r.fields["Beneficiary Remarks"] == "913171047v"
    assert r.fields["Destination Bank"] == "COMMERCIAL BANK OF CEYLON"


def test_sampath_vishwa_real_ocr_noise():
    """真实 Vishwa 回执 OCR 行：含重复变体（同 y 带冒号前缀）与值换行（gap 更大），
    字段应一个不漏，且不把重复变体或下一字段的值误拼进来。"""
    lines = [
        _lr("VISHWA", 1282, 226, 1404, 254),
        _lr("Status", 57, 414, 181, 462),
        _lr(": Success", 740, 422, 919, 459),
        _lr(": Success", 737, 419, 919, 460),  # 重复变体，不应重复拼接
        _lr("Transaction ID", 57, 491, 330, 532),
        _lr("89101292", 737, 494, 947, 531),
        _lr(": 89101292", 738, 494, 947, 531),  # 重复变体
        _lr("Date & Time", 56, 562, 294, 607),
        _lr(": 09/10/2026 01:19 PM", 738, 567, 1160, 602),
        _lr("Source Account Number", 60, 641, 514, 676),
        _lr("*2918", 869, 636, 986, 679),
        _lr("Amount", 56, 713, 206, 751),
        _lr(": LKR 5,500.00", 737, 711, 1015, 752),
        _lr("Beneficiary Name", 60, 786, 387, 827),
        _lr(": Lak Artha Pyt Ltd", 740, 787, 1078, 820),
        _lr("Beneficiary Account No", 62, 859, 497, 896),
        _lr(": 1001096962", 738, 859, 993, 896),
        _lr("Beneficiary Remarks", 62, 934, 443, 971),
        _lr(": 913171047v", 737, 933, 991, 969),
        _lr("Destination Bank", 62, 1006, 377, 1043),
        _lr(": COMMERCIAL BANK OF", 738, 1005, 1238, 1040),
        _lr("CEYLON", 737, 1067, 910, 1104),  # 续行，与上值 y 间距 > 55
    ]
    r = extract(lines)

    assert r.bank == "vishwa"
    assert r.fields["Status"] == "Success"
    assert r.fields["Transaction ID"] == "89101292"
    assert r.fields["Date & Time"] == "2026-10-09 13:19:00"
    assert r.fields["Source Account Number"] == "*2918"
    assert r.fields["Amount"] == "LKR 5,500.00"
    assert r.fields["Beneficiary Name"] == "Lak Artha Pyt Ltd"
    assert r.fields["Beneficiary Account No."] == "1001096962"
    assert r.fields["Beneficiary Remarks"] == "913171047v"
    assert r.fields["Destination Bank"] == "COMMERCIAL BANK OF CEYLON"


def test_peoples_bank_one_time_transfer():
    """People's Bank「One Time Transfer」确认回执：标签在上、值在下，字段应完整。"""
    L = _lr
    lines = [
        L("PEOPLE'S", 525, 164, 839, 222),
        L("BANK", 519, 219, 689, 278),
        L("One Time Transfer", 288, 331, 851, 386),
        L("ACKNOWLEDGEMENT", 291, 558, 909, 606),
        L("Beneficiary Account Number", 63, 686, 695, 733),
        L("1001096962", 61, 750, 366, 806),
        L("Beneficiary Name", 63, 858, 453, 906),
        L("LAK ARTHA PVT LTD", 61, 925, 580, 972),
        L("Transfer Amount", 61, 1361, 433, 1417),
        L("LKR 9,200.00", 58, 1428, 401, 1484),
        L("Fee & Charges", 58, 1547, 398, 1603),
        L("LKR 25.00", 58, 1631, 323, 1681),
        L("Debit Amount", 61, 1736, 372, 1784),
        L("LKR 9,200.00", 61, 1803, 395, 1850),
        L("Total Debit Amount", 63, 1906, 490, 1953),
        L("LKR 9,225.00", 58, 1967, 395, 2022),
        L("Transfer On", 61, 2075, 323, 2122),
        L("10-10-2026", 63, 2142, 335, 2189),
        L("Transfer Description", 55, 2239, 508, 2298),
        L("pay", 53, 2307, 160, 2379),
    ]
    r = extract(lines)

    assert r.bank == "peoples_bank"
    assert r.success is True
    assert r.fields["Beneficiary Account Number"] == "1001096962"
    assert r.fields["Beneficiary Name"] == "LAK ARTHA PVT LTD"
    assert r.fields["Transfer Amount"] == "LKR 9,200.00"
    assert r.fields["Fee & Charges"] == "LKR 25.00"
    assert r.fields["Debit Amount"] == "LKR 9,200.00"
    assert r.fields["Total Debit Amount"] == "LKR 9,225.00"
    assert r.fields["Transfer On"] == "10-10-2026"
    assert r.fields["Transfer Description"] == "pay"


def test_nsb_online_banking():
    """NSB Online Banking 回执：三栏（Source / Receiver / Transaction Details）。"""
    L = _lr
    lines = [
        L("NSB Online Banking", 432, 148, 762, 184),
        # Source Account Details（左栏）
        L("Source Account Details", 75, 364, 382, 387),
        L("Account No.", 68, 442, 204, 470),
        L("107******815", 332, 440, 477, 470),
        L("Account Type", 67, 488, 220, 522),
        L("Savings Account", 336, 495, 517, 518),
        L("Transfer Type", 66, 539, 220, 571),
        L("CEFT", 334, 543, 409, 568),
        # Receiver Account Details（中栏）
        L("Receiver Account Details", 73, 847, 404, 870),
        L("Account No.", 68, 915, 204, 943),
        L("1001096962", 336, 918, 473, 941),
        L("Beneficiary Name", 68, 966, 258, 990),
        L("Lak Artha (pvt). Ltd", 338, 968, 540, 991),
        L("Benefi. Bank Name", 70, 1018, 274, 1041),
        L("Commercial Bank PLC", 338, 1018, 576, 1041),
        L("Benefi. Branch Name", 70, 1068, 297, 1091),
        L("Digital Branch", 338, 1068, 488, 1091),
        L("Benefi. Account Type", 70, 1114, 300, 1144),
        L("Savings Account", 336, 1119, 517, 1142),
        # Transaction Details（右栏）
        L("Transaction Reference", 571, 443, 814, 467),
        L("IB7261584996", 872, 442, 1030, 465),
        L("Transaction Date/Time", 571, 495, 812, 516),
        L("2026-10-09 18:14:33", 872, 491, 1092, 515),
        L("Transfer Amount", 571, 543, 752, 566),
        L("Rs 10,000.00", 874, 543, 1021, 566),
        L("Fee & Charges", 568, 589, 731, 621),
        L("Rs 25.00", 874, 594, 978, 618),
        L("Total Amount", 568, 639, 719, 671),
        L("Rs 10,025.00", 874, 644, 1021, 667),
        L("Transaction Type", 568, 691, 760, 721),
        L("Thirdparty Account", 871, 691, 1078, 721),
        L("Status", 567, 738, 645, 773),
        L("Success", 871, 740, 974, 772),
        L("Payment Type", 569, 794, 726, 822),
        L("Immediate Payment", 872, 795, 1086, 819),
        L("Beneficiary Reference", 571, 845, 807, 868),
        L("20261009383976153", 874, 845, 1097, 868),
        L("Transaction Purpose", 572, 946, 796, 968),
        L("Loan Repayment", 872, 943, 1060, 971),
    ]
    r = extract(lines)

    assert r.bank == "nsb"
    assert r.success is True
    assert r.amount == 10000.0
    assert r.fields["Transaction Reference"] == "IB7261584996"
    assert r.fields["Transaction Date/Time"] == "2026-10-09 18:14:33"
    assert r.fields["Transfer Amount"] == "Rs 10,000.00"
    assert r.fields["Fee & Charges"] == "Rs 25.00"
    assert r.fields["Total Amount"] == "Rs 10,025.00"
    assert r.fields["Transaction Type"] == "Thirdparty Account"
    assert r.fields["Status"] == "Success"
    assert r.fields["Payment Type"] == "Immediate Payment"
    assert r.fields["Beneficiary Reference"] == "20261009383976153"
    assert r.fields["Transaction Purpose"] == "Loan Repayment"
    assert r.fields["Source Account No."] == "107******815"
    assert r.fields["Account Type"] == "Savings Account"
    assert r.fields["Transfer Type"] == "CEFT"
    assert r.fields["Receiver Account No."] == "1001096962"
    assert r.fields["Beneficiary Name"] == "Lak Artha (pvt). Ltd"
    assert r.fields["Benefi. Bank Name"] == "Commercial Bank PLC"
    assert r.fields["Benefi. Branch Name"] == "Digital Branch"
    assert r.fields["Benefi. Account Type"] == "Savings Account"


def test_peoples_pay_two_column():
    """真实 People's Bank People's Pay 回执：左标右值两栏版式。

    含 pay to 的 Name / Account No 标签漏识别、Remarks 带 "Max 16 characters"
    占位提示且值在下一行等真实情况。
    """
    lines = [
        _lr("PEOPLE'S", 521, 157, 700, 180),
        _lr("Receipt", 506, 369, 600, 400),
        _lr("Your payment has been successfully completed", 71, 578, 700, 610),
        # Pay from
        _lr("Pay from", 86, 759, 180, 790),
        _lr("Bank", 81, 850, 130, 880),
        _lr("People's Bank", 851, 847, 1010, 880),
        _lr("Account No", 90, 922, 190, 950),
        _lr("012200******84", 798, 907, 940, 940),
        _lr("Account Currency", 86, 992, 230, 1020),
        _lr("LKR", 1016, 981, 1050, 1010),
        _lr("Name", 81, 1058, 130, 1085),
        _lr("MS VINDYA NADEESHANI DE SILVA", 491, 1052, 800, 1085),
        # Pay to（Name / Account No 标签漏识别）
        _lr("Pay to", 90, 1266, 180, 1295),
        _lr("Lak Artha (Pvt) Ltd.", 731, 1355, 950, 1385),
        _lr("Bank Name", 90, 1432, 200, 1460),
        _lr("Commercial Bank PLC", 716, 1423, 900, 1455),
        _lr("1001096962", 862, 1495, 960, 1525),
        # 金额 / 时间 / 追踪 / 备注
        _lr("Amount (LKR)", 101, 1708, 250, 1738),
        _lr("7,900.00", 941, 1697, 1020, 1728),
        _lr("Fee", 94, 1914, 130, 1940),
        _lr("Fee Amount (LKR)", 101, 2009, 280, 2039),
        _lr("25.00", 998, 2002, 1040, 2030),
        _lr("Total debit amount (LKR)", 101, 2079, 320, 2110),
        _lr("7,925.00", 952, 2070, 1030, 2100),
        _lr("Date & Time", 101, 2281, 200, 2310),
        _lr("2026/10/08 12:02:53", 739, 2276, 950, 2310),
        _lr("Trace No", 105, 2489, 180, 2515),
        _lr("2026100800600901", 758, 2476, 950, 2510),
        _lr("Remarks - Max 16 characters", 109, 2693, 340, 2720),
        _lr("loan", 109, 2793, 150, 2820),
    ]
    r = extract(lines)

    assert r.bank == "peoples_bank"
    assert r.status == "success"
    assert r.payer.name == "MS VINDYA NADEESHANI DE SILVA"
    assert r.payer.account == "012200******84"
    assert r.payer.bank == "People's Bank"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank PLC"
    assert r.amount == 7900.0
    assert r.fee == 25.0
    assert r.total_debit == 7925.0
    assert r.datetime == "2026-10-08T12:02:53"
    assert r.references.remarks == "loan"
    assert r.trace_no == "2026100800600901"
    assert r.fields["Payer Name"] == "MS VINDYA NADEESHANI DE SILVA"
    assert r.fields["Payer Bank"] == "People's Bank"
    assert r.fields["Payer Account No"] == "012200******84"
    assert r.fields["Account Currency"] == "LKR"
    assert r.fields["Payee Name"] == "Lak Artha (Pvt) Ltd"
    assert r.fields["Payee Bank"] == "Commercial Bank PLC"
    assert r.fields["Payee Account No"] == "1001096962"
    assert r.fields["Amount (LKR)"] == "7,900.00"
    assert r.fields["Fee Amount (LKR)"] == "25.00"
    assert r.fields["Total debit amount (LKR)"] == "7,925.00"
    assert r.fields["Date & Time"] == "2026-10-08 12:02:53"
    assert r.fields["Trace No"] == "2026100800600901"
    assert r.fields["Remarks"] == "loan"


def test_boc_app_rotated_watermark_filtered():
    """BOC App 回执带斜向水印（如 "-Huyanmin (324)"），不应抢占字段值。"""
    L = lambda txt, x0, x1, y0, y1: OcrLine(
        text=txt, confidence=0.9, box=[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    )
    lines = [
        L("Transaction Successful", 502, 971, 114, 165),
        L("Account Information", 58, 402, 521, 562),
        L("Transaction Type", 53, 355, 802, 856),
        L("CASA Transfer", 849, 1111, 813, 864),
        L("Account Number", 53, 344, 876, 925),
        L("1001098982", 892, 1107, 889, 931),
        L("Transfer bank", 51, 292, 946, 993),
        L("Commercial Bank Of Ceylon", 617, 1109, 954, 1005),
        L("Reference/Remarks", 51, 396, 1074, 1126),
        L("J9V2VX", 965, 1108, 1092, 1130),
        L("Amount", 45, 190, 1258, 1310),
        L("LKR 5,000.00", 863, 1102, 1273, 1318),
        L("Other Charges", 46, 304, 1345, 1394),
        L("Fund Transfer/Card", 44, 384, 1414, 1464),
        L("LKR 20", 967, 1104, 1423, 1467),
        L("Settlement Service Charge", 46, 504, 1476, 1527),
        L("Total Amount", 42, 282, 1541, 1590),
        L("LKR 5,020.00", 857, 1100, 1556, 1603),
        # 斜向水印（旋转框）
        OcrLine(text="-Huyanmin (324)", confidence=0.9,
                box=[[368.0, 883.0], [666.0, 777.0], [681.0, 821.0], [384.0, 927.0]]),
        OcrLine(text="uyaomin (324)", confidence=0.9,
                box=[[387.0, 1421.0], [662.0, 1324.0], [677.0, 1368.0], [402.0, 1465.0]]),
    ]
    r = extract(lines)

    assert r.bank == "boc"
    assert r.fields["Transaction Type"] == "CASA Transfer"
    assert r.fields["Account Number"] == "1001098982"
    assert r.fields["Transfer bank"] == "Commercial Bank Of Ceylon"
    assert r.fields["Reference/Remarks"] == "J9V2VX"
    assert r.fields["Amount"] == "LKR 5,000.00"
    assert r.fields["Other Charges"] == "LKR 20"
    assert r.fields["Total Amount"] == "LKR 5,020.00"
    assert r.amount == 5000.0
    assert r.fee == 20.0
    assert r.total_debit == 5020.0


def test_boc_app_transaction_successful():
    """真实 BOC 手机银行 Transaction Successful 回执：Account Information 卡片两栏版式。

    收款账户在卡片内（Account Number / Transfer bank / Reference/Remarks），付款来源
    在底部 "My bank account" -> "People's Bank"；"Other Charges" 的值标签在左、值在
    下一行右列；参考号 UFT... 无标签；日期 "10.08.2026" 为 DD.MM.YYYY。
    """
    lines = [
        _lr("Transaction Successful", 519, 440, 780, 468),
        _lr("Lak chash", 620, 510, 700, 540),
        _lr("UFT7304438337322", 574, 580, 760, 605),
        _lr("10.08.2026 , 06:45 PM", 557, 650, 720, 675),
        _lr("Account Information", 92, 836, 250, 865),
        _lr("Transaction Type", 86, 900, 230, 930),
        _lr("CASA Transfer", 860, 902, 980, 930),
        _lr("Account Number", 89, 970, 230, 1000),
        _lr("1001096962", 900, 971, 980, 1000),
        _lr("Transfer bank", 92, 1040, 210, 1070),
        _lr("Commercial Bank Of Ceylon", 640, 1040, 860, 1070),
        _lr("PLC", 1033, 1095, 1070, 1120),
        _lr("Reference/Remarks", 86, 1160, 250, 1190),
        _lr("Nikesh ayeshan", 839, 1162, 940, 1192),
        _lr("Amount", 80, 1340, 145, 1370),
        _lr("LKR 6,000.00", 871, 1340, 980, 1370),
        _lr("Other Charges", 89, 1422, 220, 1452),
        _lr("LKR 40.00", 929, 1476, 980, 1506),
        _lr("Fund Transfer/Card", 89, 1490, 260, 1520),
        _lr("Settlement Service Charge", 86, 1545, 330, 1575),
        _lr("Total Amount", 89, 1612, 210, 1642),
        _lr("LKR 6,040.00", 877, 1612, 980, 1642),
        _lr("My bank account 1", 606, 1835, 760, 1865),
        _lr("PEOPLES", 95, 1876, 170, 1906),
        _lr("People's Bank", 606, 1890, 720, 1920),
    ]
    r = extract(lines)

    assert r.bank == "boc"
    assert r.doc_type == "fund_transfer_receipt"
    assert r.status == "success"
    assert r.amount == 6000.0
    assert r.fee == 40.0
    assert r.total_debit == 6040.0
    assert r.datetime == "2026-08-10T18:45:00"
    assert r.payer.bank == "People's Bank"
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank Of Ceylon"
    assert r.references.transaction_id == "UFT7304438337322"
    assert r.references.remarks == "Nikesh ayeshan"
    assert r.trace_no == "UFT7304438337322"
    assert r.fields["Account Number"] == "1001096962"
    assert r.fields["Transfer bank"] == "Commercial Bank Of Ceylon"
    assert r.fields["Reference/Remarks"] == "Nikesh ayeshan"
    assert r.fields["Other Charges"] == "LKR 40.00"
    assert r.fields["Total Amount"] == "LKR 6,040.00"
    assert r.fields["Date & Time"] == "2026-08-10 18:45:00"


def test_boc_flex_fund_transfer():
    """BOC Flex 网页版转账回执：Transaction Details + Sender/Beneficiary A/C Details 分区，
    单行 "Label : Value" 格式，应完整提取所有字段（含两个不同的 Account Number / Account No）。"""
    rows = [
        ("BOC", 40),
        ("Flex Online Banking", 80),
        ("Fund Transfer", 120),
        ("Transaction Details", 160),
        ("Transaction Amount : LKR 5,700.00", 200),
        ("Transaction Date & Time : 09-10-2026 01:47 PM", 240),
        ("Transaction ID : FX10858294700000", 280),
        ("Charges & Fee : LKR 25.00", 320),
        ("Remarks : sss", 360),
        ("Transaction Status : SUCCESS", 400),
        ("Sender A/C Details", 440),
        ("Account Number : **3943", 480),
        ("Sender's Name : MR A MEVIN", 520),
        ("Sender's Bank : Bank of Ceylon", 560),
        ("Beneficiary A/C Details", 600),
        ("Account No : 1001096962", 640),
        ("Beneficiary Name : Lakartha", 680),
        ("Beneficiary Bank : Commercial Bank", 720),
    ]
    r = extract(_make(rows))

    assert r.bank == "boc"
    assert r.fields["Transaction Amount"] == "LKR 5,700.00"
    assert r.fields["Transaction Date & Time"] == "2026-10-09 13:47:00"
    assert r.fields["Transaction ID"] == "FX10858294700000"
    assert r.fields["Charges & Fee"] == "LKR 25.00"
    assert r.fields["Remarks"] == "sss"
    assert r.fields["Transaction Status"] == "SUCCESS"
    assert r.fields["Account Number"] == "**3943"
    assert r.fields["Sender's Name"] == "MR A MEVIN"
    assert r.fields["Sender's Bank"] == "Bank of Ceylon"
    assert r.fields["Account No"] == "1001096962"
    assert r.fields["Beneficiary Name"] == "Lakartha"
    assert r.fields["Beneficiary Bank"] == "Commercial Bank"


def test_commercial_bank_to_only_transfer_successful():
    """Commercial Bank 手机 App「转账成功」回执：仅收款方（To）、无付款方区。

    收款方结构化堆叠：姓名 -> 账号 -> 银行；时间 "1.43PM" 点号分隔；
    参考号 "Transaction reference-416444/154352389" 用 "-" 而非冒号衔接。
    """
    lines = [
        _lr("13:44", 63, 43, 378, 43),
        _lr("Transfer Successful!", 254, 867, 946, 867),
        _lr("LKR 6,400.00", 340, 971, 819, 971),
        _lr("To", 560, 1097, 609, 1097),
        _lr("Lak Artha Services.", 378, 1223, 816, 1223),
        _lr("1001096962", 459, 1293, 744, 1293),
        _lr("Commercial Bank PLC.", 381, 1514, 819, 1514),
        _lr("Transaction reference-416444/154352389", 193, 1666, 992, 1666),
        _lr("Date/Time-09/10/2026:1.43PM", 303, 1752, 929, 1752),
        _lr("Beneficiary Notified", 415, 1886, 788, 1886),
        _lr("Make Another Payment", 176, 2161, 638, 2161),
    ]
    r = extract(lines)

    assert r.bank == "commercial_bank"
    assert r.doc_type == "fund_transfer_receipt"
    assert r.status == "success"
    assert r.amount == 6400.0
    assert r.datetime == "2026-10-09T13:43:00"
    assert r.payer.name is None
    assert r.payer.bank is None
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank PLC"
    assert r.references.txn_ref == "416444/154352389"


def test_lb_finance_fund_transfer_acknowledgement():
    """LB Finance「Cash In Mobile」转账确认回执：From/To 两栏，付款方账号用 X 掩码，
    付款方姓名为独立的 "From" 标签，参考号为 "Reference No."。"""
    L = lambda txt, x0, x1, y: _lr(txt, x0, y - 14, x1, y + 14)
    lines = [
        L("FUND TRANSFER", 62, 355, 532),
        L("ACKNOWLEDGEMENT", 62, 438, 577),
        L("From", 100, 190, 1018),
        L("D M P Madushanka", 510, 835, 1018),
        L("From Bank", 102, 275, 1058),
        L("LB Finance PLC", 510, 788, 1060),
        L("From Account", 103, 320, 1099),
        L("XXXX XXXX 2851", 510, 810, 1099),
        L("To Bank", 99, 238, 1138),
        L("Commercial Bank", 510, 805, 1139),
        L("To Account", 100, 283, 1176),
        L("1001096962", 510, 727, 1178),
        L("Beneficiary Name", 97, 375, 1217),
        L("Lak Artha Pvt", 510, 742, 1217),
        L("Amount", 100, 232, 1259),
        L("5,555.00 LKR", 510, 745, 1258),
        L("Remarks", 103, 245, 1298),
        L("Pradeep", 507, 665, 1298),
        L("Transaction Date & Time : 09/10/2026 09.42 AM", 103, 862, 1336),
        L("Reference No.", 100, 325, 1375),
        L("0056146132", 510, 727, 1376),
        L("Status", 99, 208, 1415),
        L("Successful", 510, 703, 1414),
    ]
    r = extract(lines)

    assert r.bank == "lb_finance"
    assert r.doc_type == "fund_transfer_receipt"
    assert r.status == "success"
    assert r.amount == 5555.0
    assert r.datetime == "2026-10-09T09:42:00"
    assert r.payer.name == "D M P Madushanka"
    assert r.payer.account == "XXXXXXXX2851"
    assert r.payer.bank == "LB Finance PLC"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank"
    assert r.references.bank_reference_number == "0056146132"
    assert r.references.remarks == "Pradeep"


def test_lb_finance_field_labels():
    """LB Finance 回执：两栏布局（label 左、value 右带冒号前缀）应完整提取所有字段。"""
    lines = [
        _lr("From", 100, 995, 191, 1042),
        _lr(": D M P Madushanka.", 510, 1001, 835, 1036),
        _lr("From Bank", 102, 1041, 275, 1076),
        _lr(": LB Finance PLC", 510, 1041, 788, 1076),
        _lr("From Account", 102, 1081, 322, 1117),
        _lr(": XXXX XXXX 2851", 510, 1081, 810, 1117),
        _lr("To Bank", 101, 1116, 238, 1160),
        _lr(": Commercial Bank.", 510, 1122, 805, 1157),
        _lr("To Account", 101, 1154, 283, 1198),
        _lr(": 1001096962", 508, 1162, 728, 1195),
        _lr("Beneficiary Name", 98, 1195, 378, 1240),
        _lr(": Lak Artha Pvt", 510, 1200, 742, 1235),
        _lr("Amount", 98, 1238, 232, 1281),
        _lr(": 5,555.00 LKR", 510, 1240, 745, 1276),
        _lr("Remarks", 100, 1281, 242, 1316),
        _lr(": Pradeep", 508, 1278, 665, 1319),
        _lr("Transaction Date & Time : 09/10/2026 09.42 AM", 102, 1318, 862, 1354),
        _lr("Reference No.", 101, 1353, 328, 1397),
        _lr(": 0056146132", 510, 1359, 728, 1394),
        _lr("Status", 102, 1393, 208, 1438),
        _lr(": Successfu!", 508, 1397, 702, 1432),
    ]
    r = extract(lines)

    assert r.bank == "lb_finance"
    assert r.fields["From"] == "D M P Madushanka"
    assert r.fields["From Bank"] == "LB Finance PLC"
    assert r.fields["From Account"] == "XXXX XXXX 2851"
    assert r.fields["To Bank"] == "Commercial Bank"
    assert r.fields["To Account"] == "1001096962"
    assert r.fields["Beneficiary Name"] == "Lak Artha Pvt"
    assert r.fields["Amount"] == "5,555.00 LKR"
    assert r.fields["Remarks"] == "Pradeep"
    assert r.fields["Reference No."] == "0056146132"
    assert r.fields["Status"] == "Successfu!"
    assert r.fields["Transaction Date & Time"] == "2026-10-09 09:42:00"


def test_commercial_bank_cash_credit_slip():
    """Commercial Bank 纸质现金存款凭条（CASH CREDIT SLIP）。

    版式特征：左上 Logo、右上标题、ACCOUNT NUMBER 右栏、中部存款人字段、
    右侧 NOTES/RS./CTS 面额表、底部机打户名/账号/金额。
    """
    L = lambda txt, x0, x1, y: _lr(txt, x0, y - 14, x1, y + 14)
    lines = [
        # 顶部
        L("COMMERCIAL BANK", 40, 280, 60),
        L("Name of Account Holder", 300, 620, 80),
        L("Lak Artha Pvt Ltd", 300, 560, 115),
        L("CASH CREDIT SLIP", 680, 940, 60),
        # 账号与日期（右栏）
        L("ACCOUNT NUMBER", 640, 820, 150),
        L("1001096962", 830, 1010, 150),
        L("DATE", 640, 700, 190),
        L("09-10-2026", 710, 870, 190),
        # 中部表单字段
        L("DEPOSIT BY - ACCOUNT HOLDER", 40, 360, 240),
        L("NAME AND ADDRESS OF THE DEPOSITOR", 40, 460, 290),
        L("John Doe Perera", 40, 260, 325),
        L("PURPOSE AND SOURCE OF FUNDS", 40, 420, 400),
        # 右侧面额表 NOTES | RS. | CTS
        L("NOTES", 640, 720, 260),
        L("RS.", 760, 820, 260),
        L("CTS", 870, 930, 260),
        L("5000 X", 640, 730, 300),
        L("5,000", 760, 820, 300),
        L("00", 870, 930, 300),
        L("2000 X", 640, 730, 335),
        L("0", 760, 800, 335),
        L("00", 870, 930, 335),
        L("1000 X", 640, 730, 370),
        L("0", 760, 800, 370),
        L("00", 870, 930, 370),
        L("500 X", 640, 720, 405),
        L("0", 760, 800, 405),
        L("00", 870, 930, 405),
        L("100 X", 640, 720, 440),
        L("300", 760, 820, 440),
        L("00", 870, 930, 440),
        L("50 X", 640, 710, 475),
        L("0", 760, 800, 475),
        L("00", 870, 930, 475),
        L("20 X", 640, 710, 510),
        L("0", 760, 800, 510),
        L("00", 870, 930, 510),
        L("COINS", 640, 720, 545),
        L("TOTAL", 640, 720, 580),
        L("5,300", 760, 820, 580),
        L("00", 870, 930, 580),
        # 底部机打区
        L("THANK YOU FOR BANKING WITH US", 40, 420, 620),
        L("29-10-26 09:24:16", 40, 260, 660),
        L("LAK ARTHA SERVICES", 420, 680, 660),
        L("09-10-26 E/D", 40, 200, 695),
        L("1001096962", 420, 580, 695),
        L("LKR", 40, 80, 730),
        L("5,300.00", 90, 210, 730),
        L("CDBS NC001", 280, 420, 730),
        L("0111 CURRENT ACCOUNT - CASH DEPOSIT", 40, 420, 770),
    ]
    r = extract(lines)

    assert r.bank == "commercial_bank"
    assert r.doc_type == "cash_deposit_slip"
    assert r.status is None  # The paper form has no explicit transaction status.
    # 收款方：账户持有人（含 Lak Artha 归一化）
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank"
    # 付款方：存款人
    assert r.payer.name == "John Doe Perera"
    # 金额：TOTAL 行或 LKR 行
    assert r.amount == 5300.0
    assert r.total_debit == 5300.0
    # 日期时间
    assert r.datetime == "2026-10-29T09:24:16"
    # 纸币明细
    denoms = {(d.denomination, d.quantity) for d in r.deposit_breakdown}
    assert (5000.0, 1) in denoms
    assert (100.0, 3) in denoms
    total = sum(d.amount for d in r.deposit_breakdown)
    assert abs(total - 5300.0) < 0.05
    assert r.success is True


def test_cash_credit_slip_missing_handwriting_does_not_invent_values():
    lines = [
        _lr("CASH CREDIT SLIP", 740, 40, 1100, 70),
        _lr("ACCOUNT NUMBER 1001096962", 740, 100, 1100, 130),
        _lr("NAME AND ADORESS CFTHE DEPOSITOR", 40, 250, 600, 275),
        _lr("5.REFNUMSER", 40, 490, 260, 515),
        _lr("NOTES", 740, 260, 820, 280),
        _lr("RS.", 940, 260, 980, 280),
        _lr("CTS", 1100, 260, 1150, 280),
        _lr("TOTAL", 740, 620, 820, 650),
        _lr("65", 950, 675, 990, 700),  # Below TOTAL, not its currency cell.
    ]
    for i, denom in enumerate((5000, 2000, 1000, 500, 100, 50, 20)):
        lines.append(_lr(f"{denom} X", 740, 310 + i * 40, 825, 335 + i * 40))
    r = extract(lines, include_lines=True)
    assert r.payee.account == "1001096962"
    assert r.payee.name is None
    assert r.payer.name is None
    assert r.amount is None
    assert r.total_debit is None
    assert r.deposit_breakdown == []
    assert len(r.warnings) >= 3
    assert len(r.lines) == len(lines)


def test_cash_credit_slip_printed_fields_override_form_noise():
    lines = [
        _lr("CASH CREDIT SLIP", 740, 40, 1100, 70),
        _lr("DATE 09-10-20", 740, 140, 1100, 170),
        _lr("5.REFNUMSER", 40, 490, 260, 515),
        _lr("LAK ARTHA SERVICES", 320, 600, 580, 620),
        _lr("1001096962", 320, 635, 520, 655),
        _lr("09-10-26 09:24:16", 40, 600, 270, 620),
        _lr("LKR", 280, 665, 330, 685),
        _lr("5, 300. 00", 450, 665, 580, 685),
        _lr("TOTAL", 740, 620, 820, 650),
        _lr("65", 950, 675, 990, 700),
        _lr("CURRENT ACCOUNT - CASH DEPOSIT", 40, 720, 600, 745),
    ]
    r = extract(lines)
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.amount == 5300
    assert r.total_debit == 5300
    assert r.datetime == "2026-10-09T09:24:16"
    assert r.deposit_breakdown == []


def test_cash_credit_slip_ocr_dot_instead_of_comma():
    """OCR 把千分位逗号识别成点：5.300.00 应解析为 5300。"""
    lines = [
        _lr("CASH CREDIT SLIP", 740, 40, 1100, 70),
        _lr("LKR", 40, 640, 100, 660),
        _lr("5.300.00", 110, 640, 260, 660),
        _lr("TOTAL", 740, 600, 820, 630),
        _lr("CURRENT ACCOUNT - CASH DEPOSIT", 40, 700, 400, 720),
    ]
    r = extract(lines)
    assert r.amount == 5300.0
    assert r.total_debit == 5300.0


def test_cash_credit_slip_uses_real_machine_print_coordinates():
    """Real OCR layout: printed holder overlaps the account below it."""
    lines = [
        _lr("C / /CASH CREDIT SLIP", 1005, 198, 1622, 239),
        _lr("CESSHC:OOL", 85, 883, 254, 922),
        _lr("LAK ARTHA SERVICES", 445, 818, 761, 859),
        _lr("1001096962", 581, 850, 761, 884),
        _lr("LKR", 382, 870, 440, 904),
        _lr("5,300.00", 616, 879, 762, 911),
        _lr("2026100909:24167", 157, 958, 451, 1010),
        _lr("2026100909:2416", 157, 981, 432, 1033),
        _lr("CURRENT ACCOUNT", 157, 937, 395, 977),
        _lr("CASH DEPOSIT", 433, 951, 639, 990),
    ]
    r = extract(lines)
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.amount == 5300.0
    assert r.datetime == "2026-10-09T09:24:16"


def test_cash_credit_slip_title_corrupted_uses_denomination_table():
    """OCR 把 'CASH CREDIT SLIP' 标题读坏，但面额表能识别。
    应仍命中 cash_credit_slip 分支，正确提取户名/账号/金额。"""
    L = lambda txt, x0, x1, y: _lr(txt, x0, y - 14, x1, y + 14)
    lines = [
        L("COMMERCIAL BANK", 50, 290, 250),
        L(" /  /CASH CREDIT SLIP", 1005, 1620, 210),  # 标题被读坏
        L("ACCOUNT NUMBER", 1003, 1184, 300),
        L("1001096962", 1003, 1184, 340),
        L("NAME AND ADDRESS OF THE DEPOSITOR", 52, 375, 480),
        # 面额表（结构化印刷体，识别率高）
        L("5000 X", 1016, 1113, 460),
        L("2000 X", 1016, 1113, 510),
        L("1000 X", 1017, 1115, 555),
        L("500 X", 1032, 1115, 600),
        L("100 X", 1036, 1113, 645),
        L("50 X", 1045, 1113, 686),
        L("20 X", 1046, 1113, 732),
        L("TOTAL", 1023, 1090, 884),
        # 底部机打区
        L("LAK ARTHA SERVICES", 446, 761, 830),
        L("1001096962", 582, 761, 860),
        L("LKR", 382, 440, 880),
        L("5,000.00", 616, 762, 890),
        L("02-10-26 11:11:04", 80, 340, 810),
        L("CURRENT ACCOUNT", 157, 395, 940),
        L("CASH DEPOSIT", 433, 639, 960),
    ]
    r = extract(lines)
    assert r.bank == "commercial_bank"
    assert r.doc_type == "cash_deposit_slip"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank"
    assert r.amount == 5000.0
    assert r.total_debit == 5000.0


def test_hnb_fund_transfer_receipt():
    """HNB 手机 App「Fund Transfer Receipt」：From/To 居中标签、值堆叠在下方，
    收款方「姓名-账号」合并一行，底部 "Receiver reference" 与 "This is an auto generated receipt"。"""
    L = lambda txt, x0, x1, y: _lr(txt, x0, y - 14, x1, y + 14)
    lines = [
        L("HNB", 438, 684, 482),
        L("Fund Transfer Receipt", 274, 929, 625),
        L("LKR 5,050.00", 395, 805, 805),
        L("From", 553, 653, 1153),
        L("DIASWUC", 453, 750, 1251),
        L("To", 569, 631, 1343),
        L("Lak Artha Pvt Ltd-1001096962", 219, 972, 1439),
        L("COMMERCIAL BANK", 519, 675, 1570),
        L("Commercial Bank PLC", 398, 799, 1685),
        L("Receiver reference-Champika Dias 751251866V", 176, 1021, 1790),
        L("Transaction Reference-189359/154299101", 225, 972, 1864),
        L("Date/Time-09/10/2026:9.30AM", 312, 891, 1944),
        L("This is an auto generated receipt", 311, 889, 2114),
    ]
    r = extract(lines)

    assert r.bank == "hnb"
    assert r.doc_type == "fund_transfer_receipt"
    assert r.amount == 5050.0
    assert r.datetime == "2026-10-09T09:30:00"
    assert r.payer.name == "DIASWUC"
    assert r.payer.bank == "HNB"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank PLC"
    assert r.references.txn_ref == "189359/154299101"
    assert r.references.receiver_ref == "Champika Dias 751251866V"


def test_ipay_fund_transfer():
    """iPay 转账回执：左列标签 / 右列值两栏，From 下姓名+银行、To 下银行+账号，
    头部 "Rs.5,512.00" 为交易金额。"""
    L = lambda txt, x0, x1, y: _lr(txt, x0, y - 18, x1, y + 18)
    lines = [
        L("Rs.5,512.00", 509, 691, 612),
        L("Transaction Summary", 426, 772, 417),
        L("Transaction Date", 75, 297, 780),
        L("2026-10-09 14:16:09", 603, 868, 783),
        L("Transaction ID", 78, 265, 875),
        L("2026100908460800001", 600, 903, 869),
        L("Type", 75, 147, 951),
        L("Fund Transfer", 595, 785, 948),
        L("From", 72, 154, 1044),
        L("Sameera", 601, 724, 1021),
        L("Bank of Ceylon ****1089", 600, 913, 1081),
        L("To", 75, 118, 1173),
        L("Commercial Bank PLC", 600, 892, 1146),
        L("1001096962", 596, 767, 1194),
        L("Recipient", 75, 204, 1284),
        L("LAK artha pvt Ltd", 597, 825, 1270),
        L("Remarks", 74, 199, 1381),
        L("0714362384", 598, 767, 1378),
        L("Status", 74, 167, 1481),
        L("SUCCESS", 600, 745, 1484),
        L("This transaction was performed using iPay", 343, 854, 1584),
        L("www.ipay.lk", 72, 490, 1790),
    ]
    r = extract(lines)

    assert r.bank == "ipay"
    assert r.doc_type == "fund_transfer_receipt"
    assert r.status == "success"
    assert r.success is True
    assert r.amount == 5512.0
    assert r.datetime == "2026-10-09T14:16:09"
    assert r.payer.name == "Sameera"
    assert r.payer.account == "****1089"
    assert r.payer.bank == "Bank of Ceylon"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank PLC"
    assert r.references.transaction_id == "2026100908460800001"
    assert r.references.remarks == "0714362384"
    assert r.fields["Transaction Date"] == "2026-10-09 14:16:09"
    assert r.fields["Transaction ID"] == "2026100908460800001"
    assert r.fields["Type"] == "Fund Transfer"
    assert r.fields["From"] == "Sameera Bank of Ceylon ****1089"
    assert r.fields["To"] == "Commercial Bank PLC 1001096962"
    assert r.fields["Recipient"] == "LAK artha pvt Ltd"
    assert r.fields["Remarks"] == "0714362384"
    assert r.fields["Status"] == "SUCCESS"

