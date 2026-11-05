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


def test_cdm_header_right_column_should_not_steal_terminal():
    """真实 WELLAWAY CDM：DATE/TIME 值略偏下且 TERMINAL 值 y 更靠近标签行，
    不能把 RWELAWA2HT 抢给 DATE/TIME。"""
    lines = [
        _lr("COMMERCIAL BANK OF CEYLON PLC", 400, 1100, 1200, 1160),
        _lr("WELLAWAY-CRM2 BR", 677, 1305, 1085, 1378),
        _lr("DATE", 442, 1486, 550, 1533),
        _lr("TIME", 729, 1462, 847, 1523),
        _lr("TERMINAL ID", 1005, 1437, 1300, 1511),
        _lr("03/11/26", 434, 1518, 649, 1593),
        _lr("10:49", 731, 1512, 868, 1572),
        _lr("RWELAWA2HT", 1005, 1495, 1273, 1558),
        _lr("TRACE", 441, 1617, 582, 1688),
        _lr("762", 763, 1615, 847, 1669),
        _lr("TRANSACTION", 452, 1764, 726, 1826),
        _lr(": CARDLESS DEPOSIT", 789, 1747, 1253, 1809),
        _lr("ACCOUNT NUMBER: 1001096962", 452, 1849, 1104, 1925),
        _lr("CUSTOMER NAME :LAK ARTHA SERVICES", 455, 1951, 1286, 2020),
        _lr("SOURCE OF FUNDS:UNKNOWN", 456, 2373, 1040, 2424),
        _lr("DEPOSIT AMOUNT", 459, 2744, 830, 2791),
        _lr("LKR", 942, 2737, 1033, 2791),
        _lr("4,000.00", 1212, 2734, 1431, 2781),
        _lr("TRANSACTION STATUS : SUCCESSFUL", 536, 2825, 1344, 2894),
    ]
    r = extract(lines)

    assert r.fields["DATE"] == "2026-11-03 00:00:00"
    assert r.fields["TIME"] == "10:49"
    assert r.fields["TERMINAL ID"] == "RWELAWA2HT"
    assert r.datetime == "2026-11-03T10:49:00"
    assert r.fields["TRACE"] == "762"
    assert r.fields["Date & Time"] == "2026-11-03 10:49:00"
    assert r.fields["Transaction Date/Time"] == "2026-11-03 10:49:00"


def test_cdm_trace_value_under_time_column_not_stolen():
    """CDM：TRACE 值印在 TIME 列正下方时，TIME 仍应取 HH:MM，不能取 TRACE 号。"""
    lines = [
        _lr("DATE", 183, 751, 262, 785),
        _lr("TIME", 399, 747, 481, 787),
        _lr("TERMINAL ID", 600, 745, 801, 785),
        _lr("02/11/26", 181, 785, 335, 822),
        _lr("19:28", 404, 785, 496, 818),
        _lr("RMATCIT2HT", 600, 785, 781, 816),
        _lr("TRACE", 181, 851, 280, 891),
        _lr("2197", 400, 849, 480, 889),
        _lr("TRANSACTION CARDLESS DEPOSIT", 180, 950, 700, 990),
        _lr("ACCOUNT NUMBER 1001096962", 180, 1020, 700, 1060),
        _lr("DEPOSIT AMOUNT LKR 4,000.00", 180, 1200, 700, 1240),
        _lr("TRANSACTION STATUS SUCCESSFUL", 180, 1300, 700, 1340),
    ]
    r = extract(lines)
    assert r.fields["DATE"] == "2026-11-02 00:00:00"
    assert r.fields["TIME"] == "19:28"
    assert r.fields["TERMINAL ID"] == "RMATCIT2HT"
    assert r.fields["TRACE"] == "2197"
    assert r.datetime == "2026-11-02T19:28:00"


def test_cdm_rotated_photo_values_left_of_tall_labels():
    """竖拍 CDM：DATE/TIME/TERMINAL 为竖排高框、值在左侧；右侧银行名不得抢占 TIME。"""
    lines = [
        _lr("3760", 2512, 961, 2584, 1128),
        _lr("02/11/26", 2640, 592, 2724, 874),
        _lr("TERMINAL ID", 2704, 1342, 2780, 1728),
        _lr("TRACE", 2516, 588, 2588, 766),
        _lr("DATE", 2716, 592, 2776, 735),
        _lr("TIME", 2712, 981, 2772, 1132),
        _lr("14:13", 2640, 985, 2712, 1159),
        _lr("COMMERCIAL BANK OF CEYLON PLC", 3024, 683, 3104, 1668),
        _lr("CUSTOMER NAME :LAK ARTHA SERVICES", 2035, 559, 2153, 1684),
        _lr(" SOURCE OF FUNDS: UNKNOWN", 1531, 539, 1633, 1331),
        _lr("SUCCESSFUL", 911, 1289, 1017, 1693),
        _lr("TRANSACTION : CARDLESS DEPOSIT", 2308, 576, 2400, 1648),
        _lr("TRANSACTION STATUS", 940, 639, 1020, 1267),
        _lr("ACCOUNT NUMBER: 1001096962", 2180, 571, 2272, 1450),
        _lr("RCINNAMTHT", 2627, 1334, 2709, 1684),
        _lr(" COLOMBO7 CRM1 BR", 2888, 901, 2976, 1469),
        _lr("CD COMMERCIAL BANK", 3188, 651, 3332, 1811),
        _lr("DEPOSIT AMOUNT:", 1067, 523, 1165, 1037),
        _lr("5, 000. 00", 1043, 1492, 1137, 1811),
        _lr("LKR 5, 000. 00", 1199, 817, 1293, 1263),
    ]
    r = extract(lines)

    assert r.fields["DATE"] == "2026-11-02 00:00:00"
    assert r.fields["TIME"] == "14:13"
    assert r.fields["TERMINAL ID"] == "RCINNAMTHT"
    assert r.fields["TRACE"] == "3760"
    assert r.fields["TRANSACTION STATUS"] == "SUCCESSFUL"
    assert r.fields["Date & Time"] == "2026-11-02 14:13:00"
    assert r.datetime == "2026-11-02T14:13:00"
    assert r.terminal_id == "RCINNAMTHT"
    assert r.trace_no == "3760"
    assert r.amount == 5000.0
    assert r.fields["ACCOUNT NUMBER"] == "1001096962"


def test_cdm_rotated_time_not_stolen_from_date_ocr():
    """竖拍 Commercial CARDLESS：TIME 同带右侧 19:11/19.11，不得被 DATE 列 01:11.26 抢走；
    TRACE 取高置信 6399 而非噪点 6359；ACCOUNT/TRANSACTION 不得绑银行名。"""
    lines = [
        _lr("6399", 2032, 1613, 2110, 1768, 0.999),
        _lr("19.11", 1915, 1600, 1976, 1751, 0.999),
        _lr("1001096962", 2339, 1273, 2417, 1625, 0.999),
        _lr("TRACE", 2045, 1977, 2110, 2158),
        _lr("DATE", 1855, 2003, 1915, 2172),
        _lr("01/11/26", 1907, 1870, 1985, 2167, 0.996),
        _lr("TIME", 1850, 1618, 1920, 1755, 0.992),
        _lr("19:11", 1911, 1609, 1976, 1751, 0.923),
        _lr("CARDLESS DEPOSIT", 2196, 1092, 2283, 1633),
        _lr("TRANSACTION", 2223, 1760, 2301, 2144),
        _lr("ORBUSNE1HT", 1893, 1065, 1954, 1395),
        _lr("TERMINAL", 1823, 1097, 1888, 1389),
        _lr("ACCOUNT NUMBER", 2339, 1646, 2426, 2165),
        _lr("COMMERCIAL BANK OF CEYLON PLC", 1512, 1104, 1599, 2078),
        _lr("(IL) COMMERCIAL BANK", 1278, 962, 1426, 2132, 0.916),
        _lr("NARRATION AWA5JG", 2669, 1601, 2743, 2161),
        _lr("01:11.26", 1911, 1870, 1985, 2167, 0.929),
        _lr("11:61", 1911, 1609, 1976, 1751, 0.794),
        _lr("6359", 2037, 1626, 2102, 1764, 0.547),
        _lr("LKR 5,000.00", 3344, 1404, 3435, 1862),
        _lr("SUCCESSFUL", 3631, 966, 3709, 1325),
    ]
    r = extract(lines)

    assert r.fields["TIME"] == "19:11"
    assert r.fields["TRACE"] == "6399"
    assert r.fields["ACCOUNT NUMBER"] == "1001096962"
    assert r.fields["TRANSACTION"] == "CARDLESS DEPOSIT"
    assert r.fields["TERMINAL ID"] == "ORBUSNE1HT"
    assert r.fields["NARRATION"] == "AWA5JG"
    assert r.fields.get("MOBILE NO.") in (None, "", "-", "–", "—")
    assert r.fields["Date & Time"] == "2026-11-01 19:11:00"
    assert r.datetime == "2026-11-01T19:11:00"
    assert r.amount == 5000.0


def test_cdm_without_cardless_keyword_still_extracts_headers():
    """OCR 漏读 CARDLESS DEPOSIT 时，凭 DATE/TIME/TERMINAL/DEPOSIT AMOUNT 仍应按 CDM 提取。"""
    lines = [
        _lr("DATE", 432, 1687, 500, 1720),
        _lr("TIME", 750, 1668, 820, 1700),
        _lr("TERMINAL ID", 1100, 1636, 1300, 1680),
        _lr("30/10/26", 430, 1740, 560, 1780),
        _lr("16:37", 760, 1723, 850, 1760),
        _lr("RVEYANG1HT", 1100, 1700, 1280, 1740),
        _lr("TRACE", 430, 1800, 520, 1840),
        _lr("1677", 760, 1800, 850, 1840),
        _lr("DEPOSIT AMOUNT", 430, 2000, 700, 2040),
        _lr("6,000.00", 900, 2000, 1100, 2040),
        _lr("TRANSACTION STATUS SUCCESSFUL", 430, 2200, 900, 2240),
    ]
    r = extract(lines)
    assert r.bank == "commercial_bank"
    assert r.fields["DATE"] == "2026-10-30 00:00:00"
    assert r.fields["TIME"] == "16:37"
    assert r.fields["TERMINAL ID"] == "RVEYANG1HT"
    assert r.fields["DEPOSIT AMOUNT"] == "6,000.00"


def test_ipay_preferred_over_peoples_bank_marker():
    """iPay 回执正文含 People's Bank 付款来源时，应识别为 ipay 并抽出 Amount。"""
    rows = [
        ("Transaction Summary", 40),
        ("iPay", 60),
        ("Type Fund Transfer", 100),
        ("Transaction Date 2026-11-03 10:42:56", 140),
        ("Transaction ID 2026110305125500001", 180),
        ("From People's Bank **0867", 220),
        ("To Commercial Bank PLC", 260),
        ("1001096962", 300),
        ("Recipient Lak Artha service", 340),
        ("Rs.17,420.00", 380),
        ("Status SUCCESS", 420),
        ("Remarks 6XT74B", 460),
        ("For more information, visit www.ipay.lk", 500),
    ]
    r = extract(_make(rows))
    assert r.bank == "ipay"
    assert r.fields["Amount"] == "Rs.17,420.00"
    assert r.fields["Payment Reference"] == "2026110305125500001"
    assert r.amount == 17420.0


def test_vishwa_beneficiary_account_without_no_suffix():
    """Vishwa：标签为 Beneficiary Account :（无 No.）也应抽出收款账号。"""
    lines = [
        _lr("Status :", 40, 100, 120, 130),
        _lr("Success", 200, 100, 300, 130),
        _lr("Transaction ID :", 40, 150, 200, 180),
        _lr("92228514", 250, 150, 400, 180),
        _lr("Date & Time :", 40, 200, 180, 230),
        _lr("02/11/2026 03:26 PM", 250, 200, 500, 230),
        _lr("Amount :", 40, 250, 140, 280),
        _lr("LKR 5,000.00", 250, 250, 420, 280),
        _lr("Beneficiary Account :", 40, 300, 240, 330),
        _lr("1001096962", 250, 300, 420, 330),
        _lr("Beneficiary Remarks :", 40, 350, 240, 380),
        _lr("AjE858", 250, 350, 360, 380),
        _lr("VISHWA", 40, 50, 140, 80),
    ]
    r = extract(lines)
    assert r.bank == "vishwa"
    assert r.fields["Beneficiary Account"] == "1001096962"
    assert r.fields.get("Payment Reference") != "e"


def test_hnb_app_transaction_reference_dash_fields():
    """HNB App：Transaction Reference -xxxx 同行写法，并补 Payment Reference 别名。"""
    rows = [
        ("Fund Transfer Receipt", 40),
        ("This is an auto generated receipt", 80),
        ("HNB", 100),
        ("Transaction Reference -1233928/158560281", 140),
        ("Date/ Time -02/11/2026 : 10.27 PM", 180),
        ("LKR 5,850.00", 220),
        ("To", 260),
        ("Lak Cash - 1001096962", 300),
        ("Commercial Bank PLC", 340),
        ("Receiver reference -G4ws43", 380),
    ]
    r = extract(_make(rows))
    assert r.bank == "hnb"
    assert r.fields["Transaction Reference"] == "1233928/158560281"
    assert r.fields["Payment Reference"] == "1233928/158560281"
    assert r.fields["Amount"] == "LKR 5,850.00"


def test_nsb_mobile_payment_colon_fields():
    """NSB Online Payment Mobile：冒号分隔字段应完整提取。"""
    rows = [
        ("NSB Online Payment - Mobile", 40),
        ("Transaction ID : 1568907733", 80),
        ("Transaction Date/Time : 31/10/2026 09:21 AM", 120),
        ("Transaction Type : Fund Transfer", 160),
        ("Transaction Amount : LKR 8,800.00", 200),
        ("Bank Charges : LKR 25.00", 240),
        ("Status : Success", 280),
        ("Sender's Name : Ruwan Nalaka", 320),
        ("Source Bank Name : National Savings Bank", 360),
        ("Source Bank Account Number : ****3075", 400),
        ("Beneficiary Name : lakartha(pvt)ltd.", 440),
        ("Destination Bank : Commercial Bank PLC", 480),
        ("Destination Account No. : 1001096962", 520),
        ("Remarks : ruwan nalaka", 560),
    ]
    r = extract(_make(rows))
    assert r.bank == "nsb"
    assert r.fields["Transaction ID"] == "1568907733"
    assert r.fields["Transaction Date/Time"] == "2026-10-31 09:21:00"
    assert r.fields["Destination Account No."] == "1001096962"
    assert r.amount == 8800.0


def test_boc_flex_ocr_typo_date_1t():
    """BOC Flex：日期 OCR 把 11 读成 1t 时应仍能解析。"""
    rows = [
        ("Flex Online Banking", 40),
        ("Fund Transfer", 60),
        ("Transaction Amount : LKR 3,000.00", 100),
        ("Transaction Date & Time : 02-1t-2026 04:41 PM", 140),
        ("Transaction ID : FX11843998900000", 180),
        ("Charges & Fee : LKR 25.00", 220),
        ("Transaction Status : SUCCESS", 260),
        ("Account Number : **6975", 300),
        ("Sender's Name : MS WM PERERA", 340),
        ("Sender's Bank : Bank of Ceylon", 380),
        ("Account No : 1001096962", 420),
        ("Beneficiary Name : lak Artha services", 460),
    ]
    r = extract(_make(rows))
    assert r.fields["Transaction Date & Time"] == "2026-11-02 16:41:00"
    assert r.datetime == "2026-11-02T16:41:00"


def test_cdm_incomplete_notes_table_should_not_invent_amount():
    """CDM：NOTES 有两行数量但 VALUE 只认出一个面额时，不能把 4×500 当成存款总额。"""
    lines = [
        _lr("DATE", 221, 1430, 421, 1524),
        _lr("03/11/26", 226, 1519, 596, 1604),
        _lr("TIME", 758, 1404, 950, 1502),
        _lr("09:30", 750, 1493, 998, 1582),
        _lr("TERMINAL ID", 1244, 1383, 1744, 1472),
        _lr("RPOLGAHIHT", 1244, 1472, 1702, 1557),
        _lr("TRACE", 235, 1680, 465, 1774),
        _lr("6157", 758, 1655, 954, 1753),
        _lr("TRANSACTION", 252, 1939, 749, 2024),
        _lr("NOTES", 290, 3197, 533, 3291),
        _lr("VALUE", 690, 3168, 932, 3275),
        _lr("AMOUNT", 1673, 3105, 1945, 3198),
        _lr("4", 532, 3366, 587, 3442),
        _lr("LKR", 695, 3358, 879, 3439),
        _lr("500.00", 973, 3334, 1254, 3423),
        _lr("3", 528, 3451, 595, 3540),
        _lr("DEPOSIT AMOUNT :", 332, 3626, 990, 3715),
        _lr("LKR", 1154, 3593, 1324, 3695),
    ]
    r = extract(lines)

    assert r.bank == "commercial_bank"
    assert r.fields["DATE"] == "2026-11-03 00:00:00"
    assert r.fields["TIME"] == "09:30"
    assert r.fields["TERMINAL ID"] == "RPOLGAHIHT"
    assert r.fields["TRACE"] == "6157"
    assert r.fields["TRANSACTION"] == "CARDLESS DEPOSIT"
    # 面额表不完整时不得捏造 2,000.00
    assert r.amount is None
    assert "DEPOSIT AMOUNT" not in r.fields or r.fields.get("DEPOSIT AMOUNT") != "2,000.00"
    assert r.deposit_breakdown == []


def test_peoples_otp_acknowledgement_status_reference():
    """People's OTP 成功回执页：Status/Reference/From/Beneficiary 标签在上值在下。"""
    lines = [
        _lr("PEOPLE'S", 525, 114, 842, 169),
        _lr("BANK", 525, 167, 684, 217),
        _lr("One Time Transfer", 271, 267, 857, 322),
        _lr("ACKNOWLEDGEMENT", 274, 481, 926, 536),
        _lr("Status", 49, 564, 228, 611),
        _lr("Successful", 55, 636, 352, 695),
        _lr("Reference Number", 58, 747, 537, 803),
        _lr("2610302087625086", 58, 831, 614, 886),
        _lr("From Account", 55, 945, 421, 1000),
        _lr("LKR 055-2-001-2-3595355", 55, 1028, 802, 1083),
        _lr("Payment Option", 58, 1142, 470, 1197),
        _lr("LANKAPAY - ONLINE", 55, 1222, 638, 1278),
        _lr("Beneficiary Account Bank", 61, 1339, 718, 1386),
        _lr("7056 - Commercial Bank PLC", 61, 1417, 860, 1472),
        _lr("Beneficiary Branch Name", 58, 1531, 710, 1586),
        _lr("00000 - Head Office", 58, 1611, 606, 1667),
        _lr("Beneficiary Account Number", 58, 1722, 793, 1781),
        _lr("1001096962", 58, 1803, 407, 1867),
        _lr("Beneficiary Name", 55, 1917, 517, 1981),
        _lr("LAK ARTHA SERVICES PVT LTD", 58, 2006, 897, 2053),
        _lr("MAKE ANOTHER TRANSFER", 214, 2409, 984, 2467),
    ]
    r = extract(lines)

    assert r.bank == "peoples_bank"
    assert r.fields["Status"] == "Successful"
    assert r.fields["Reference Number"] == "2610302087625086"
    assert r.fields["Payment Reference"] == "2610302087625086"
    assert r.fields["From Account"] == "LKR 055-2-001-2-3595355"
    assert r.fields["Payment Option"] == "LANKAPAY - ONLINE"
    assert r.fields["Beneficiary Account Bank"] == "7056 - Commercial Bank PLC"
    assert r.fields["Beneficiary Branch Name"] == "00000 - Head Office"
    assert r.fields["Beneficiary Account Number"] == "1001096962"
    assert r.fields["Beneficiary Name"] == "LAK ARTHA SERVICES PVT LTD"
    assert "Payer Bank" not in r.fields
    # 账号行不能被解析成金额
    assert r.amount is None
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank PLC"


def test_cdm_deposit_amcunt_ocr_typo_and_amount_backfill():
    """CDM：DEPOSIT AMCUNT 拼写损坏仍应匹配；有可靠金额时回填 DEPOSIT AMOUNT。"""
    lines = [
        _lr("COMMERCIAL BANK OF CEYLON PLC", 200, 1000, 900, 1060),
        _lr("DATE", 200, 1200, 300, 1250),
        _lr("03/11/26", 200, 1260, 400, 1310),
        _lr("TIME", 450, 1200, 550, 1250),
        _lr("09:30", 450, 1260, 560, 1310),
        _lr("TERMINAL ID", 700, 1200, 900, 1250),
        _lr("RPOLGAHIHT", 700, 1260, 950, 1310),
        _lr("TRACE", 200, 1350, 320, 1400),
        _lr("6157", 450, 1350, 550, 1400),
        _lr("TRANSACTION", 200, 1500, 500, 1550),
        _lr("CARDLESS DEPOSIT", 520, 1500, 900, 1550),
        _lr("ACCOUNT NUMBER", 200, 1600, 500, 1650),
        _lr("1001096962", 520, 1600, 800, 1650),
        _lr("CUSTOMER NAME", 200, 1700, 480, 1750),
        _lr("LAK ARTHA SERVICES", 500, 1700, 900, 1750),
        _lr("DEPOSIT AMCUNT:", 200, 2000, 520, 2050),
        _lr("LKR", 560, 2000, 640, 2050),
        _lr("5,000.00", 700, 2000, 900, 2050),
        _lr("TRANSACTION STATUS SUCCESSFUL", 200, 2200, 900, 2250),
    ]
    r = extract(lines)
    assert r.fields["DEPOSIT AMOUNT"] == "5,000.00"
    assert r.amount == 5000.0
    assert r.fields["ACCOUNT NUMBER"] == "1001096962"
    assert r.fields["CUSTOMER NAME"] == "LAK ARTHA SERVICES"


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
    # OCR 把首字母 O 读成 0 时应还原为 O6000…
    assert r.references.bank_reference_number == "O600069434117"
    assert r.references.e_receipt_reference == "855D-1263-BAE1-F237"
    assert r.references.remarks == "yhbbn"

    # 扁平字段：key 用单据原始英文字段名，value 为原文
    assert r.fields["Bank Reference Number"] == "O600069434117"
    assert r.fields["Payment Reference"] == "O600069434117"
    assert r.fields["Sender's Account Number"] == "81******36"
    assert r.fields["Sender's Name"] == "MRS ABDUL CARDER FATHIMA SIMAYA"
    assert r.fields["Transfer Amount"] == "5,000.00"
    assert r.fields["Beneficiary Account Number"] == "1001096962"
    assert r.fields["Beneficiary's Account Narration"] == "yhbbn"
    assert r.fields["Status"] == "Completed"


def test_commercial_bank_eref_leading_o_not_zero():
    """ComBank e-Receipt：Bank Reference 首字母是 O；OCR 成 0 且粘 logo「COMMERAL BANK」时应还原。"""
    L = lambda txt, x0, x1, y: _lr(txt, x0, y - 14, x1, y + 14)
    lines = [
        L("e-Receipt", 133, 231, 390),
        L("Transfer within ComBank", 352, 802, 400),
        L("COMMERAL BANK", 820, 1080, 420),
        L("Bank Reference Number", 41, 326, 446),
        L("0600069688024", 588, 800, 446),
        L("Sender's Account Number", 40, 349, 496),
        L("81******48", 587, 730, 496),
        L("Sender's Name", 40, 219, 535),
        L("MR MOHAMED NAZEER MOHAMED MURSHID", 588, 1044, 535),
        L("Transfer Amount", 43, 251, 574),
        L("5,300.00", 588, 704, 574),
        L("Transfer Currency", 41, 263, 610),
        L("LKR", 586, 640, 610),
        L("Beneficiary Name", 41, 251, 649),
        L("LAK ARTHA SERVICES (PVT) LTD", 588, 963, 649),
        L("Beneficiary Account Number", 40, 384, 730),
        L("1001096962", 588, 747, 730),
        L("Beneficiary's Account Narration", 43, 418, 772),
        L("199005101337", 588, 672, 772),
        L("Transaction Date/Time", 41, 320, 805),
        L("09/10/2026 10:36 AM", 588, 865, 805),
        L("Payment Date", 43, 213, 847),
        L("09-10-26", 584, 708, 847),
        L("Status", 43, 124, 884),
        L("Completed", 591, 727, 884),
    ]
    r = extract(lines)

    assert r.bank == "commercial_bank"
    assert r.fields["Bank Reference Number"] == "O600069688024"
    assert r.fields["Payment Reference"] == "O600069688024"
    assert r.fields["Transaction Reference"] == "O600069688024"
    assert r.references.bank_reference_number == "O600069688024"
    assert r.amount == 5300.0
    assert r.payee.account == "1001096962"


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


def test_cdm_branch_split_ekala_crm_br():
    """CDM：网点 OCR 拆成 EKALA-CRM1 + BR 时应拼回 EKALA-CRM1 BR，并写入 fields。"""
    lines = [
        _lr("COMMERCIAL BANK OF CEYLON PLC", 200, 400, 900, 460),
        _lr("EKALA-CRM1", 440, 657, 831, 754),
        _lr("BR", 988, 665, 1082, 755),
        _lr("DATE", 27, 886, 210, 968),
        _lr("30/10/26", 25, 962, 376, 1068),
        _lr("TIME", 518, 894, 700, 989),
        _lr("11:37", 518, 985, 732, 1062),
        _lr("TERMINAL ID", 954, 903, 1395, 981),
        _lr("REKALAO1HT", 949, 981, 1354, 1054),
        _lr("TRACE", 35, 1121, 260, 1227),
        _lr("9950", 526, 1140, 700, 1221),
        _lr("TRANSACTION", 58, 1376, 509, 1449),
        _lr(": CARDLESS DEPOSIT", 566, 1368, 1324, 1446),
        _lr("ACCOUNT NUMBER: 1001096962", 58, 1500, 900, 1560),
        _lr("CUSTOMER NAME :LAK ARTHA SERVICES", 58, 1600, 1000, 1660),
        _lr("SOURCE OF FUNDS:UNKNOWN", 58, 1800, 700, 1860),
        _lr("DEPOSIT AMOUNT:", 339, 2842, 683, 2915),
        _lr("LKR 5,000.00", 834, 2829, 1200, 2915),
        _lr("TRANSACTION STATUS : SUCCESSFUL", 325, 3006, 1453, 3079),
    ]
    r = extract(lines)
    assert r.branch == "EKALA-CRM1 BR"
    assert r.fields["BRANCH"] == "EKALA-CRM1 BR"
    assert r.fields["ACCOUNT NUMBER"] == "1001096962"
    assert r.fields["CUSTOMER NAME"] == "LAK ARTHA SERVICES"
    assert r.fields["TIME"] == "11:37"
    assert r.amount == 5000.0


def test_cdm_empty_narration_not_label_echo_and_midband_party():
    """EKALA CDM：空 NARRATION/MOBILE 的 OCR 残片 IARRATION/IOBILE 不得当值；
    中间带补回的 ACCOUNT/CUSTOMER 应写入 fields。"""
    lines = [
        _lr("EKALA-CRM1", 440, 657, 831, 754),
        _lr("BR", 988, 665, 1082, 755),
        _lr("DATE", 27, 886, 210, 968),
        _lr("30/10/26", 25, 962, 376, 1068),
        _lr("TIME", 518, 894, 700, 989),
        _lr("11:37", 518, 985, 732, 1062),
        _lr("TERMINAL ID", 954, 903, 1395, 981),
        _lr("REKALAO1HT", 949, 981, 1354, 1054),
        _lr("TRACE", 35, 1121, 260, 1227),
        _lr("9950", 526, 1140, 700, 1221),
        _lr("TRANSACTION", 58, 1376, 509, 1449),
        _lr(": CARDLESS DEPOSIT", 566, 1368, 1324, 1446),
        # 首轮漏读账号/户名；中间带复检补回（模拟）
        _lr("ACCOUNT NUMBER: 1001096962", 58, 1500, 900, 1560),
        _lr("CUSTOMER NAME :LAK ARTHA SERVICES", 58, 1680, 1100, 1740),
        _lr("NARRATION:", 62, 1914, 463, 1991, 0.996),
        _lr("IARRATION:", 99, 1927, 456, 1990, 0.953),
        _lr("MOBILE NO. :", 66, 2146, 507, 2224, 0.987),
        _lr("IOBILE NO.:", 100, 2157, 507, 2225, 0.899),
        _lr("SOURCE OF FUNDS:UNKNOWN", 58, 2300, 700, 2360),
        _lr("DEPOSIT AMOUNT:", 339, 2842, 683, 2915),
        _lr("LKR 5,000.00", 834, 2829, 1200, 2915),
        _lr("TRANSACTION STATUS : SUCCESSFUL", 325, 3006, 1453, 3079),
    ]
    r = extract(lines)
    assert r.fields["ACCOUNT NUMBER"] == "1001096962"
    assert r.fields["CUSTOMER NAME"] == "LAK ARTHA SERVICES"
    assert r.fields.get("NARRATION") in (None, "", "-")
    assert r.fields.get("MOBILE NO.") in (None, "", "-", "–", "—")
    assert r.fields.get("Remarks") in (None, "", "-")
    assert "IARRATION" not in str(r.fields.get("NARRATION") or "")
    assert "IOBILE" not in str(r.fields.get("MOBILE NO.") or "")
    assert "5,000.00" in str(r.fields.get("DEPOSIT AMOUNT") or "").replace(" ", "")
    assert r.amount == 5000.0


def test_cdm_recover_account_without_label_from_midband_digits():
    """EKALA：首轮完全漏掉 ACCOUNT/CUSTOMER 标签，中间带只补出纯数字与户名行。"""
    lines = [
        _lr("DATE", 27, 886, 210, 968),
        _lr("30/10/26", 25, 962, 376, 1068),
        _lr("TIME", 518, 894, 700, 989),
        _lr("11:37", 518, 985, 732, 1062),
        _lr("TERMINAL ID", 954, 903, 1395, 981),
        _lr("REKALAO1HT", 949, 981, 1354, 1054),
        _lr("TRACE", 35, 1121, 260, 1227),
        _lr("9950", 526, 1140, 700, 1221),
        _lr("TRANSACTION", 58, 1376, 509, 1449),
        _lr(": CARDLESS DEPOSIT", 566, 1368, 1324, 1446),
        # 无标签，仅中间带数字/户名
        _lr("1001096962", 400, 1520, 900, 1580, 0.99),
        _lr("LAK ARTHA SERVICES", 60, 1680, 900, 1740, 0.95),
        _lr("NARRATION:", 62, 1914, 463, 1991),
        _lr("IARRATION:", 99, 1927, 456, 1990, 0.95),
        _lr("DEPOSIT AMOUNT:", 339, 2842, 683, 2915),
        _lr("LKR 5,000.00", 834, 2829, 1200, 2915),
        _lr("TRANSACTION STATUS : SUCCESSFUL", 325, 3006, 1453, 3079),
    ]
    r = extract(lines)
    assert r.fields["ACCOUNT NUMBER"] == "1001096962"
    assert "LAK ARTHA" in r.fields["CUSTOMER NAME"].upper()
    assert r.fields.get("NARRATION") in (None, "", "-")
    assert r.amount == 5000.0


def test_kalutara_rotated_sparse_ocr_completes_account_and_scrub():
    """KALUTARA 远距竖排：账号截成 00109696、CARDLESS 串 NARRATION/MOBILE、
    日期残片不当 TRACE；户名命中时补全 1001096962；金额带补总额。"""
    lines = [
        _lr("RANSACTION", 756, 1181, 785, 1272, 0.994),
        _lr("0109696", 727, 1317, 747, 1370, 0.968),
        _lr("MOBILE NO.", 600, 1172, 629, 1256, 0.956),
        _lr("ACCOUNT NUMBER:", 721, 1170, 753, 1295, 0.955),
        _lr("KALUTARA-CRM2 BR", 894, 1236, 923, 1395, 0.954),
        _lr("MOUNT", 537, 1425, 557, 1464, 0.953),
        _lr("NOTES VALUE", 522, 1178, 554, 1292, 0.949),
        _lr("NARRATION:", 646, 1175, 675, 1261, 0.936),
        _lr("TRACE", 799, 1172, 831, 1228, 0.931),
        _lr("DEPUSIT", 415, 1183, 438, 1236, 0.928),
        _lr("CUSTOMER NAME LAK ARTHA SERVICES", 686, 1167, 730, 1436, 0.924),
        _lr("CARDLESS DEPOSIT", 744, 1276, 791, 1432, 0.917),
        _lr("KAI U1ARA CRM2 BR", 894, 1236, 926, 1384, 0.910),
        _lr("SOURCE OF FUNDS:UNKNOWN", 571, 1175, 603, 1359, 0.898),
        _lr("ACCOUNT NUMISE H", 722, 1166, 759, 1298, 0.853),
        _lr("00109696", 730, 1306, 753, 1370, 0.790),
        _lr("8888", 455, 1446, 522, 1479, 0.769),
        _lr("D0710/26ERERLYAHIO", 825, 1162, 877, 1450, 0.540),
    ]
    r = extract(lines)
    assert r.fields["ACCOUNT NUMBER"] == "1001096962"
    assert "LAK ARTHA" in r.fields["CUSTOMER NAME"].upper()
    assert r.fields["TRANSACTION"] == "CARDLESS DEPOSIT"
    assert r.fields.get("NARRATION") in (None, "", "-")
    assert r.fields.get("MOBILE NO.") in (None, "", "-", "–", "—")
    assert r.fields.get("Remarks") in (None, "", "-")
    assert r.fields.get("TRACE") not in {"0710", "8888", "660"}
    assert r.fields["BRANCH"] == "KALUTARA-CRM2 BR"
    # 金额带复检补到总额
    lines_amt = lines + [_lr("DEPOSIT AMOUNT LKR 7,600.00", 400, 1400, 560, 1480, 0.96)]
    r2 = extract(lines_amt)
    assert r2.amount == 7600.0
    assert "7,600.00" in str(r2.fields.get("DEPOSIT AMOUNT") or "").replace(" ", "")


def test_cdm_crease_sparse_ocr_not_row_amount():
    """NAWALAPI：折痕导致漏读 CARDLESS/账号/总额时，不得把行小计 400 当存款额，
    仍应识别为 CDM 并抽出 DATE/TIME/TRACE。"""
    lines = [
        _lr("DATE", 500, 1238, 682, 1320),
        _lr("TIME", 981, 1211, 1157, 1305),
        _lr("TRACE", 513, 1461, 734, 1554),
        _lr("3528", 999, 1429, 1183, 1523),
        _lr("0803", 984, 1282, 1194, 1376, 0.99),
        _lr("08:03", 983, 1287, 1193, 1381, 0.92),
        _lr("l2 11 26", 504, 1319, 843, 1397, 0.79),
        _lr("NOTES", 604, 2874, 831, 2972),
        _lr("VALUE", 979, 2843, 1198, 2937),
        _lr("AMOUNT", 1873, 2770, 2131, 2864),
        _lr("4", 829, 3029, 881, 3098),
        _lr("100.00", 1238, 2988, 1493, 3069),
        _lr("400.00", 1888, 2933, 2156, 3022),
        _lr("1", 833, 3115, 890, 3183, 0.78),
        _lr("1.000.00", 1813, 3023, 2160, 3112),
        _lr("2", 847, 3200, 890, 3264),
        _lr("LKR", 1413, 3309, 1561, 3395),
        _lr("HOTES", 608, 2874, 831, 2968, 0.88),
    ]
    r = extract(lines)

    assert r.bank == "commercial_bank"
    assert r.doc_type == "cash_deposit_slip"
    assert r.fields.get("TRANSACTION") == "CARDLESS DEPOSIT"
    assert r.fields.get("TRACE") == "3528"
    assert r.fields.get("TIME") == "08:03"
    assert "2026-11-02" in str(r.fields.get("DATE") or "") or "02/11/26" in str(
        r.fields.get("DATE") or ""
    )
    # 不得把 4×100 的行小计当成存款总额
    assert r.amount != 400.0
    assert r.fields.get("DEPOSIT AMOUNT") != "400.00"


def test_cdm_missing_deposit_label_recovers_notes_band_amount():
    """MAHARAGA：OCR 漏掉 DEPOSIT AMOUNT 标签，但仍有 NOTES 表与 15.000.00。"""
    lines = [
        _lr("DATE", 549, 1103, 743, 1190),
        _lr("30/10/26", 552, 1186, 909, 1289),
        _lr("TIME", 1057, 1117, 1236, 1208),
        _lr("17:19", 1060, 1195, 1271, 1284),
        _lr("TERMINAL ID", 1500, 1125, 1943, 1200),
        _lr("RMAHARA3HT", 1499, 1205, 1906, 1288),
        _lr("TRACE", 566, 1352, 781, 1437),
        _lr("5253", 1057, 1354, 1244, 1446),
        _lr("TRANSACTION", 575, 1600, 1044, 1671),
        _lr(": CARDLESS DEPOSIT", 1120, 1604, 1866, 1675),
        _lr("ACC0UNT NUMBER: 1001096962", 575, 1763, 1628, 1834),
        _lr("CUSTOMER NAME :LAK ARTHA SERVICES", 575, 1913, 1914, 1996),
        _lr("MAHARAGA-CRM3 BR", 973, 879, 1620, 976),
        _lr("NOTES", 600, 2770, 850, 2860),
        _lr("VALUE", 964, 2777, 1192, 2869),
        _lr("AMOUNT", 1831, 2716, 2085, 2814),
        _lr("3", 810, 2967, 878, 3058),
        _lr("LKR", 1360, 3052, 1509, 3137),
        _lr("15.000.00", 1723, 2866, 2085, 2963, 0.989),
        _lr("15.000.00", 1728, 3020, 2081, 3109, 0.990),
        _lr("COMMERCIAL BANK OF CEYLON PLC", 683, 708, 1859, 813),
    ]
    r = extract(lines)
    assert r.amount == 15000.0
    assert "15,000.00" in str(r.fields.get("DEPOSIT AMOUNT") or "").replace(" ", "")
    assert r.fields["ACCOUNT NUMBER"] == "1001096962"
    assert r.fields["BRANCH"] == "MAHARAGA-CRM3 BR"


def test_cdm_rotated_deposit_amount_not_denom_face():
    """竖排 KANDANA CDM：DEPOSIT AMOUNT 总额 10,200，不得误取面额表 5,000。"""
    lines = [
        _lr("DATE", 1109, 1309, 1169, 1464),
        _lr("30/10/26", 1151, 1188, 1238, 1461),
        _lr("TIME", 1105, 947, 1169, 1084),
        _lr("18:03", 1165, 924, 1225, 1084),
        _lr("TERMINAL ID", 1087, 408, 1161, 748),
        _lr("RKANDAN2HT", 1142, 436, 1230, 762),
        _lr("TRACE", 1289, 1274, 1348, 1446),
        _lr("1731", 1280, 955, 1344, 1079),
        _lr("TRANSACTION", 1455, 1036, 1536, 1451),
        _lr("CARDLESS DEPOSIT", 1446, 465, 1528, 982),
        _lr("ACCOUNT NUMBER:1001096962", 1570, 628, 1651, 1451),
        _lr("CUSTOMER NAME :LAK ARTHA SERVICES", 1676, 425, 1775, 1456),
        _lr("NARRAT1ON:0784535930", 1873, 823, 1946, 1446),
        _lr("SOURCE OF FUNDS: UNKNOWN", 2154, 722, 2253, 1447),
        _lr("NOTES", 2364, 1274, 2428, 1446),
        _lr("VALUE", 2355, 1004, 2419, 1168),
        _lr("AMOUNT", 2334, 292, 2411, 495),
        _lr("100.00", 2475, 787, 2539, 982),
        _lr("200.00", 2463, 277, 2540, 492),
        _lr("LKR 5.000.00", 2520, 777, 2612, 1169, 0.941),
        _lr("10,000.00", 2516, 281, 2604, 572, 0.932),
        _lr("DEPOSIT AMOUNT:", 2658, 979, 2740, 1451, 0.961),
        _lr("LKR", 2658, 752, 2722, 858, 0.998),
        _lr("10.200.00", 2641, 271, 2723, 576, 0.945),
        _lr("TRANSACTION STATUS", 2773, 745, 2864, 1345),
        _lr("SUCCESSFUL", 2778, 380, 2837, 712),
        _lr("THANK YOU FOR BANKING WITH US", 2828, 386, 2928, 1328),
        _lr("KANDANA-CRM2 BR", 917, 641, 990, 1159),
        _lr("COMMERCIAL BANK OF CEYLON PLC", 789, 465, 879, 1376),
    ]
    r = extract(lines)
    assert r.amount == 10200.0
    assert "10,200.00" in str(r.fields.get("DEPOSIT AMOUNT") or "").replace(" ", "")
    assert r.fields.get("DEPOSIT AMOUNT") != "5,000.00"
    assert r.fields["ACCOUNT NUMBER"] == "1001096962"
    assert r.fields["TRANSACTION"] == "CARDLESS DEPOSIT"
    assert r.fields["TRANSACTION STATUS"] == "SUCCESSFUL"
    assert "THANK YOU" not in str(r.fields.get("TRANSACTION STATUS") or "")


def test_ntb_description_strips_watermark_junk():
    """NTB：水印把 Description 粘成 NatiPU8QAW / 3 Nat PU8QAW 时，应保留短码 PU8QAW。"""
    lines = [
        _lr("Transaction summary", 379, 196, 818, 237),
        _lr("LKR 6,600.00", 482, 364, 716, 398),
        _lr("Fund transfer", 493, 415, 709, 444),
        _lr("From account", 58, 531, 285, 560),
        _lr("XXXXXXXX9246", 902, 531, 1142, 560),
        _lr("To account", 58, 598, 242, 627),
        _lr("1001096962", 960, 596, 1142, 625),
        _lr("To account name", 58, 662, 344, 693),
        _lr("Lak Artha services", 852, 661, 1140, 690),
        _lr("Bank", 56, 724, 143, 761),
        _lr("Commercial Bank PLC", 788, 727, 1139, 756),
        _lr("Service charge", 58, 789, 298, 828),
        _lr("LKR 25.00", 992, 789, 1144, 825),
        _lr("Date", 56, 850, 139, 892),
        _lr("30-Oct-2026", 934, 855, 1142, 884),
        _lr("Time", 55, 919, 141, 956),
        _lr("18:55", 1062, 920, 1144, 953),
        _lr("Reference number.", 60, 989, 356, 1018),
        _lr("2630306102752552", 842, 989, 1140, 1012),
        _lr("Status", 56, 1048, 164, 1090),
        _lr("Success", 1009, 1053, 1144, 1084),
        _lr("Description", 58, 1117, 242, 1152),
        _lr("PU8QAW", 1002, 1118, 1144, 1149, 0.999),
        _lr("NatiPU8QAW", 919, 1113, 1146, 1154, 0.996),
        _lr("NationsTrustBank", 642, 1117, 867, 1146, 0.991),
        _lr("NationsTrustBank", 361, 1117, 588, 1146, 0.986),
    ]
    r = extract(lines)
    assert r.bank == "ntb"
    assert r.fields.get("Description") == "PU8QAW"
    assert r.fields.get("Remarks") == "PU8QAW"
    assert "Nati" not in str(r.fields.get("Description") or "")
    assert "Nat" not in str(r.fields.get("Description") or "")
    assert r.fields["To account"] == "1001096962"
    assert r.amount == 6600.0
    # 复检若读成「3 Nat PU8QAW」仍应剥成 PU8QAW
    r2 = extract(lines + [_lr("3 Nat PU8QAW", 900, 1114, 1145, 1152, 0.95)])
    assert r2.fields["Description"] == "PU8QAW"
    assert r2.fields["Remarks"] == "PU8QAW"


def test_peoples_pay_sinhala_positional_fields():
    """僧伽罗语 People's Pay：英文 Pay from/to 标签缺失，按 People's Bank/Commercial Bank 锚点提取。"""
    lines = [
        _lr("O MM CHANDIKA BANDARA WIJERATHNA", 110, 464, 1088, 509),
        _lr("People's Bank", 788, 557, 1093, 602),
        _lr("149200xxxxxxx84", 713, 638, 1093, 697),
        _lr("LKR", 996, 731, 1096, 784),
        _lr("CeG9 CGQ@9", 107, 990, 576, 1045),
        _lr("LAK ARTHA SCVICE. PVT LTD", 402, 1124, 1087, 1169),
        _lr("Commercial Bank PLC", 613, 1216, 1090, 1261),
        _lr("1001096962", 793, 1306, 1090, 1359),
        _lr("9gC(LKR)", 104, 1570, 414, 1636),
        _lr("5,050.00", 876, 1575, 1090, 1623),
        _lr("Ges", 115, 1815, 225, 1863),
        _lr("GeD (LKR)", 105, 1920, 445, 1987),
        _lr("25.00", 962, 1931, 1096, 1979),
        _lr("G3y6Osi qQ3o ge @cC(LKR) 5,075.00", 107, 2010, 1096, 2077),
        _lr("Eocs a gSea", 115, 2248, 525, 2311),
        _lr("2026-10-30 14:17:13", 646, 2256, 1090, 2301),
    ]
    r = extract(lines)

    assert r.bank == "peoples_bank"
    assert r.payer.name == "MM CHANDIKA BANDARA WIJERATHNA"
    assert r.payer.bank == "People's Bank"
    assert r.payer.account == "149200xxxxxxx84"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.bank == "Commercial Bank PLC"
    assert r.payee.account == "1001096962"
    assert r.amount == 5050.0
    assert r.fee == 25.0
    assert r.total_debit == 5075.0
    assert r.datetime == "2026-10-30T14:17:13"
    assert r.fields["Payer Bank"] == "People's Bank"
    assert r.fields["Payer Bank"] != "PLC"
    assert r.fields["Amount (LKR)"] == "5,050.00"
    assert r.fields["Fee Amount (LKR)"] == "25.00"
    assert r.fields["Total debit amount (LKR)"] == "5,075.00"
    assert r.fields["Date & Time"] == "2026-10-30 14:17:13"


def test_union_ubgo_fund_transfer_receipt():
    """Union Bank UBgo FUND TRANSFER RECEIPT：冒号字段 + Amount 上下 + 收款行居中。"""
    lines = [
        _lr("UNIONBANK", 155, 65, 591, 117),
        _lr("UBgO", 931, 43, 1128, 136),
        _lr("FUND TRANSFER RECEIPT", 161, 232, 1066, 287),
        _lr("Amount", 519, 389, 674, 435),
        _lr("LKR 5,000.00", 384, 456, 800, 514),
        _lr("COMMERCIAL BANK OF CEYLON PLC", 245, 545, 945, 575),
        _lr("Transaction Status:Success", 64, 620, 473, 652),
        _lr("Paid From:", 64, 704, 230, 734),
        _lr("***6011", 353, 700, 454, 736),
        _lr("Pay To: 1001096962", 63, 765, 365, 806),
        _lr("Branch: -", 57, 832, 187, 868),
        _lr("Beneficiary Name: Lak artha.", 61, 901, 454, 931),
        _lr("Service Charge: LKR 25.00", 62, 971, 454, 1001),
        _lr("Remarks: UBGo trnx", 62, 1041, 370, 1071),
        _lr("Date & Time: 02-Nov-2026 | 02:09 PM", 59, 1100, 602, 1137),
        _lr("Reference Number: FC1250140934", 65, 1170, 575, 1205),
        _lr("Union Bank of Colombo PLC", 812, 1511, 1127, 1536),
        _lr("This is a system generated receipt", 61, 1607, 429, 1633),
    ]
    r = extract(lines)

    assert r.bank == "union_bank"
    assert r.amount == 5000.0
    assert r.fee == 25.0
    assert r.total_debit == 5025.0
    assert r.datetime == "2026-11-02T14:09:00"
    assert r.payer.account == "***6011"
    assert r.payer.bank == "Union Bank of Colombo PLC"
    assert r.payee.account == "1001096962"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert "COMMERCIAL BANK" in (r.payee.bank or "").upper()
    assert r.fields["Amount"] == "LKR 5,000.00"
    assert r.fields["Pay To"] == "1001096962"
    assert r.fields["Paid From"] == "***6011"
    assert r.fields["Service Charge"] == "LKR 25.00"
    assert r.fields["Date & Time"] == "2026-11-02 14:09:00"
    assert r.fields["Reference Number"] == "FC1250140934"
    assert r.fields["Payment Reference"] == "FC1250140934"
    assert r.fields["Status"] == "Success"
    assert r.fields["Remarks"] == "UBGo trnx"
    assert "Branch" not in r.fields  # Branch: - 为空，不得串下一字段


def test_peoples_pay_without_logo_text_still_extracts():
    """People's Pay：Logo/行名 OCR 漏读、标题截成 Transaction confirmat... 时仍应识别。

    仅剩 Pay to + Amount(LKR) + Trace No + Remarks Max 16 characters 版式特征。
    """
    lines = [
        _lr("Transaction confirmat...", 228, 194, 995, 256),
        _lr("Pay to", 95, 470, 268, 539),
        _lr("Name", 98, 589, 239, 642),
        _lr("L.a.k Artha", 834, 592, 1096, 642),
        _lr("Bank Name", 99, 669, 355, 725),
        _lr("Commercial Bank PLC", 617, 678, 1093, 717),
        _lr("Account No", 104, 758, 358, 806),
        _lr("1001096962", 796, 756, 1102, 811),
        _lr("Amount (LKR)", 98, 975, 490, 1036),
        _lr("7,900.00", 897, 975, 1099, 1033),
        _lr("Fee", 96, 1191, 203, 1263),
        _lr("Fee Amount (LKR )", 101, 1308, 528, 1364),
        _lr("25.00", 969, 1311, 1102, 1361),
        _lr("Total debit amount ( LKR )", 101, 1395, 669, 1442),
        _lr("7,925.00", 909, 1392, 1099, 1442),
        _lr("Date & Time", 99, 1603, 416, 1667),
        _lr("2026/10/30 14:21:53", 632, 1614, 1093, 1653),
        _lr("Trace No", 98, 1828, 335, 1886),
        _lr("2026103000769043", 649, 1831, 1096, 1878),
        _lr("Remarks - Max 16 characters", 107, 2053, 848, 2100),
        _lr("loan", 96, 2155, 206, 2221),
    ]
    r = extract(lines)

    assert r.bank == "peoples_bank"
    assert r.doc_type == "payment_confirmation"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank PLC"
    assert r.amount == 7900.0
    assert r.fee == 25.0
    assert r.total_debit == 7925.0
    assert r.datetime == "2026-10-30T14:21:53"
    assert r.trace_no == "2026103000769043"
    assert r.fields["Amount (LKR)"] == "7,900.00"
    assert r.fields["Fee Amount (LKR)"] == "25.00"
    assert r.fields["Total debit amount (LKR)"] == "7,925.00"
    assert r.fields["Date & Time"] == "2026-10-30 14:21:53"
    assert r.fields["Trace No"] == "2026103000769043"
    assert r.fields["Payee Name"] == "Lak Artha (Pvt) Ltd"
    assert r.fields["Payee Account No"] == "1001096962"
    assert r.fields["Remarks"] == "loan"


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


def test_boc_mobile_txn_details_upright_hero_amount_and_kak_artha():
    """正拍 BOC Transaction Details：顶部 LKR 5,000 主金额；Kak Artha→Lak Artha；
    Sender's Name 取同行高置信全大写。"""
    lines = [
        _lr("Transaction Details", 385, 192, 856, 240, 0.999),
        _lr("LKR 5,000.00", 400, 350, 750, 450, 0.95),
        _lr("Receiver's Account No", 166, 659, 570, 696, 0.999),
        _lr("1001096962", 811, 644, 1044, 689, 0.999),
        _lr("Receiver's Bank", 161, 833, 450, 870, 0.96),
        _lr("Commercial Bank", 693, 823, 1044, 867, 0.98),
        _lr("Receiver's Name", 153, 1001, 464, 1048, 0.999),
        _lr("Kak Artha", 836, 1004, 1045, 1048, 0.977),
        _lr("Sender's Account No", 150, 1185, 528, 1222, 0.999),
        _lr("******8417", 845, 1179, 1042, 1230, 0.96),
        _lr("Sender's Name", 145, 1361, 431, 1398, 0.999),
        _lr("mR e s m h I SenevIratne", 475, 1361, 1037, 1408, 0.67),
        _lr("Sender's NameMR E S M HI SENEVIRATNE", 140, 1355, 1037, 1411, 0.927),
        _lr("Sender's Bank Name", 135, 1534, 528, 1587, 0.972),
        _lr("Bank of Ceylon", 730, 1544, 1040, 1603, 0.971),
        _lr("Remarks", 125, 1712, 301, 1769, 0.999),
        _lr("loan", 943, 1743, 1046, 1798, 0.991),
        _lr("Fees & Charges", 120, 1899, 416, 1963, 0.999),
        _lr("LKR 25.00", 826, 1933, 1040, 1989, 0.944),
    ]
    r = extract(lines)
    assert r.bank == "boc"
    assert r.fields["Transfer Amount"] == "LKR 5,000.00"
    assert r.amount == 5000.0
    assert r.fee == 25.0
    assert r.fields["Receiver's Name"] == "Lak Artha (Pvt) Ltd"
    assert "SENEVIRATNE" in r.fields["Sender's Name"].upper()
    assert r.fields["Remarks"] == "loan"
    assert r.fields["Fees & Charges"] == "LKR 25.00"


def test_boc_mobile_txn_fee_not_used_as_transfer_when_hero_missing():
    """顶部大额漏读时，不得把 Fees 25 当成 Transfer Amount；amount 应先置空。"""
    lines = [
        _lr("Transaction Details", 385, 192, 856, 240, 0.999),
        _lr("Receiver's Account No", 166, 659, 570, 696, 0.999),
        _lr("1001096962", 811, 644, 1044, 689, 0.999),
        _lr("Receiver's Bank", 161, 833, 450, 870, 0.96),
        _lr("Commercial Bank", 693, 823, 1044, 867, 0.98),
        _lr("Receiver's Name", 153, 1001, 464, 1048, 0.999),
        _lr("Kak Artha", 836, 1004, 1045, 1048, 0.977),
        _lr("Sender's Account No", 150, 1185, 528, 1222, 0.999),
        _lr("******8417", 845, 1179, 1042, 1230, 0.96),
        _lr("Sender's NameMR E S M HI SENEVIRATNE", 140, 1355, 1037, 1411, 0.927),
        _lr("Sender's Bank Name", 135, 1534, 528, 1587, 0.972),
        _lr("Bank of Ceylon", 730, 1544, 1040, 1603, 0.971),
        _lr("Remarks", 125, 1712, 301, 1769, 0.999),
        _lr("loan", 943, 1743, 1046, 1798, 0.991),
        _lr("Fees & Charges", 120, 1899, 416, 1963, 0.999),
        _lr("LKR 25.00", 826, 1933, 1040, 1989, 0.944),
    ]
    r = extract(lines)
    assert r.fee == 25.0
    assert r.fields.get("Transfer Amount") is None
    assert r.amount is None or abs(r.amount - 25.0) > 0.01
    assert r.fields["Receiver's Name"] == "Lak Artha (Pvt) Ltd"
    assert "SENEVIRATNE" in r.fields["Sender's Name"].upper()


def test_boc_mobile_txn_details_rotated_phone():
    """竖拍 BOC 手机 Transaction Details：值在标签上方同列，不得把下一标签当值。"""
    lines = [
        _lr("2026.11.01", 2967, 1369, 3157, 1414, 0.999),
        _lr("Receiver's Bank", 1000, 974, 1047, 1254, 0.999),
        _lr("Sender's Account No", 1383, 878, 1430, 1241, 0.999),
        _lr("Bank of Ceylon", 1807, 208, 1864, 508, 0.999),
        _lr("Sender's Name", 1594, 960, 1641, 1232, 0.999),
        _lr("Remarks", 1971, 1063, 2017, 1219, 0.999),
        _lr("1001096962", 763, 184, 819, 428, 0.999),
        _lr("Sender's Bank Name", 1797, 867, 1844, 1228, 0.999),
        _lr("5,000.00", 502, 441, 622, 885, 0.999),
        _lr("Fees & Charges", 2151, 947, 2197, 1219, 0.999),
        _lr("Commercial Bank", 973, 187, 1029, 550, 0.999),
        _lr("LKR 25.00", 2181, 215, 2227, 409, 0.995),
        _lr("Receiver's Account No", 789, 853, 840, 1261, 0.992),
        _lr("kumara", 1627, 209, 1673, 376, 0.991),
        _lr("Fees&Charges", 2148, 944, 2204, 1219, 0.990),
        _lr("Receiver's Name", 1193, 942, 1240, 1244, 0.985),
        _lr("bathme wadanage ruwan chamara", 1577, 206, 1624, 865, 0.981),
        _lr("deepika priyadarshani", 1994, 212, 2047, 637, 0.979),
        _lr("Lak Artha pvt Itd", 1176, 197, 1236, 534, 0.961),
        _lr("LKR", 543, 845, 607, 990, 0.960),
        _lr("90********00", 1377, 199, 1433, 431, 0.881),
        _lr("00********6", 1377, 199, 1433, 431, 0.833),
    ]
    r = extract(lines)

    assert r.bank == "boc"
    assert r.fields["Receiver's Account No"] == "1001096962"
    assert r.fields["Receiver's Bank"] == "Commercial Bank"
    assert r.fields["Receiver's Name"] == "Lak Artha (Pvt) Ltd"
    assert r.fields["Sender's Name"] == "bathme wadanage ruwan chamara kumara"
    assert r.fields["Sender's Bank Name"] == "Bank of Ceylon"
    assert r.fields["Remarks"] == "deepika priyadarshani"
    assert r.fields["Fees & Charges"] == "LKR 25.00"
    assert r.fields["Sender's Name"] != "Sender's Account No"
    assert r.fields["Remarks"] != "Fees&Charges"
    assert r.fields["Sender's Account No"] == "90********00"
    assert r.amount == 5000.0
    assert r.fee == 25.0
    assert r.payee.account == "1001096962"
    assert r.payer.name == "bathme wadanage ruwan chamara kumara"


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
    assert r.fields["Beneficiary Name"] == "Lak Artha (Pvt) Ltd"
    assert r.fields["Beneficiary Account Number"] == "1001096962"
    assert r.fields["Beneficiary Bank"] == "Commercial Bank PLC"
    assert r.fields["Status"] == "Beneficiary Notified"


def test_commercial_bank_to_only_lk_loan_nickname():
    """ComBank Transfer Successful：收款昵称 LK loan；Transaction reference 标签与值分行。"""
    L = lambda txt, x0, x1, y: _lr(txt, x0, y - 18, x1, y + 18)
    lines = [
        L("Transfer Successful!", 251, 946, 911),
        L("LKR 1,000.00", 334, 824, 1016),
        L("To", 554, 612, 1142),
        L("LK loan", 506, 693, 1266),
        L("1001096962", 456, 738, 1340),
        L("Commercial Bank PLC", 381, 819, 1562),
        L("Receiver Reference -lakcach", 320, 865, 1686),
        L("Transaction reference", 384, 799, 1771),
        L("-1391031/158604737", 390, 791, 1816),
        L("Date/Time -03/11/2026 : 10.07 AM", 303, 949, 1902),
        L("Beneficiary Notified", 412, 788, 2038),
    ]
    r = extract(lines)

    assert r.bank == "commercial_bank"
    assert r.amount == 1000.0
    assert r.payee.name == "LK loan"
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank PLC"
    assert r.fields["Beneficiary Name"] == "LK loan"
    assert r.fields["To"] == "LK loan"
    assert r.fields["Beneficiary Account Number"] == "1001096962"
    assert r.fields["Account Number"] == "1001096962"
    assert r.fields["Beneficiary Bank"] == "Commercial Bank PLC"
    assert r.fields["Amount"] == "LKR 1,000.00"
    assert r.fields["Receiver Reference"] == "lakcach"
    assert r.fields["Payment Reference"] == "1391031/158604737"
    assert r.fields["Date/Time"] == "2026-11-03 10:07:00"
    assert r.fields["Status"] == "Beneficiary Notified"


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
    assert r.fields["From"] == "DIASWUC"
    assert r.fields["Sender's Name"] == "DIASWUC"
    assert r.fields["Beneficiary Name"] == "Lak Artha (Pvt) Ltd"
    assert r.fields["Beneficiary Account Number"] == "1001096962"
    assert r.fields["Beneficiary Bank"] == "Commercial Bank PLC"


def test_hnb_fund_transfer_lak_cash_nickname():
    """HNB Fund Transfer Receipt：From 姓名 + To「Lak Cash - 账号」须写入扁平字段。"""
    L = lambda txt, x0, x1, y: _lr(txt, x0, y - 14, x1, y + 14)
    lines = [
        L("HNB", 438, 684, 482),
        L("Fund Transfer Receipt", 274, 929, 625),
        L("LKR 5,850.00", 395, 805, 805),
        L("From", 553, 653, 1153),
        L("THASTHIKANTH K", 400, 850, 1251),
        L("To", 569, 631, 1343),
        L("Lak Cash - 1001096962", 219, 972, 1439),
        L("Commercial Bank PLC", 398, 799, 1685),
        L("Receiver reference-G4WS43", 176, 1021, 1790),
        L("Transaction Reference-1233928/158560281", 225, 972, 1864),
        L("Date/Time-02/11/2026 : 10.27 PM", 312, 891, 1944),
        L("This is an auto generated receipt", 311, 889, 2114),
    ]
    r = extract(lines)

    assert r.bank == "hnb"
    assert r.amount == 5850.0
    assert r.payer.name == "THASTHIKANTH K"
    assert r.payee.name == "Lak Cash"
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank PLC"
    assert r.fields["From"] == "THASTHIKANTH K"
    assert r.fields["Sender's Name"] == "THASTHIKANTH K"
    assert r.fields["To"] == "Lak Cash"
    assert r.fields["Beneficiary Name"] == "Lak Cash"
    assert r.fields["Beneficiary Account Number"] == "1001096962"
    assert r.fields["Account Number"] == "1001096962"
    assert r.fields["Beneficiary Bank"] == "Commercial Bank PLC"
    assert r.fields["Amount"] == "LKR 5,850.00"
    assert r.fields["Receiver Reference"] == "G4WS43"
    assert r.fields["Payment Reference"] == "1233928/158560281"


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


def test_ipay_hnb_payer_not_misclassified_as_hnb_app():
    """iPay 付款行为 Hatton National 时不得误判成 HNB App，金额/收付款方应齐全。

    真实样本：logo 拆成 "pay"、Recipient 为 "lak artha pvt Itd"。
    """
    L = lambda txt, x0, x1, y: _lr(txt, x0, y - 18, x1, y + 18)
    lines = [
        L("ipay_2026103012043...", 153, 822, 190),
        L("Transaction Summary", 441, 759, 443),
        L("Rs.1,100.00", 513, 687, 620),
        L("Transaction Date", 115, 320, 774),
        L("2026-10-30 17:34:37", 600, 848, 772),
        L("Transaction ID", 115, 288, 857),
        L("2026103012043700001", 597, 883, 857),
        L("Type", 110, 186, 932),
        L("Fund Transfer", 600, 770, 932),
        L("From", 112, 186, 1025),
        L("Jayan", 600, 678, 1002),
        L("Hatton National Bank PLC ********1172", 597, 1059, 1052),
        L("To", 112, 156, 1138),
        L("Commercial Bank PLC", 603, 868, 1111),
        L("1001096962", 600, 750, 1166),
        L("Recipient", 115, 231, 1240),
        L("lak artha pvt Itd", 600, 785, 1226),
        L(" Remarks", 111, 232, 1334),
        L("N/A", 597, 658, 1336),
        L("Status", 115, 197, 1425),
        L("SUCCESS", 600, 733, 1426),
        L("This transaction was performed using", 358, 840, 1518),
        L("pay", 871, 947, 1505),
        L("For more information, visit www.ipay.lk", 112, 502, 1706),
    ]
    r = extract(lines)

    assert r.bank == "ipay"
    assert r.amount == 1100.0
    assert r.payer.name == "Jayan"
    assert r.payer.bank == "Hatton National Bank PLC"
    assert r.payer.account == "********1172"
    assert r.payee.name == "Lak Artha (Pvt) Ltd"
    assert r.payee.account == "1001096962"
    assert r.payee.bank == "Commercial Bank PLC"
    assert r.fields["Amount"] == "Rs.1,100.00"
    assert r.fields["Type"] == "Fund Transfer"
    assert r.fields["From"] == "Jayan Hatton National Bank PLC ********1172"
    assert r.fields["To"] == "Commercial Bank PLC 1001096962"
    assert r.fields["Recipient"] == "lak artha pvt Itd"
    assert r.fields["Status"] == "SUCCESS"
    assert r.fields["Transaction ID"] == "2026103012043700001"
