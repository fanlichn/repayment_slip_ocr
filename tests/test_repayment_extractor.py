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
    assert r.fields["Bank"] == "People's Bank"
    assert r.fields["Account No"] == "012200******84"
    assert r.fields["Bank Name"] == "Commercial Bank PLC"
    assert r.fields["Amount (LKR)"] == "7,900.00"
    assert r.fields["Fee Amount (LKR)"] == "25.00"
    assert r.fields["Total debit amount (LKR)"] == "7,925.00"
    assert r.fields["Trace No"] == "2026100800600901"


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