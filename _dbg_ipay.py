import sys
sys.path.insert(0, ".")

from app.ocr_engine import OcrLine
from repayment_slip_ocr.extractor import extract


def L(t, x0, y0, x1, y1):
    return OcrLine(text=t, confidence=0.9, box=[[x0, y0], [x1, y0], [x1, y1], [x0, y1]])


lines = [
    L("Transaction Summary", 426, 417, 772, 458),
    L("Rs.5,512.00", 509, 612, 691, 650),
    L("Transaction Date", 75, 780, 297, 815),
    L("2026-10-09 14:16:09", 603, 783, 868, 810),
    L("Transaction ID", 78, 875, 265, 905),
    L("2026100908460800001", 600, 869, 903, 905),
    L("Type", 75, 951, 147, 991),
    L(" Fund Transfer", 595, 948, 785, 992),
    L("From", 72, 1044, 154, 1092),
    L("Sameera", 601, 1021, 724, 1059),
    L("Bank of Ceylon ****1089", 600, 1081, 913, 1116),
    L("To", 75, 1173, 118, 1208),
    L("Commercial Bank PLC", 600, 1146, 892, 1181),
    L("1001096962", 596, 1194, 767, 1238),
    L("Recipient", 75, 1284, 204, 1322),
    L("LAK artha pvt Ltd", 597, 1270, 825, 1305),
    L("Remarks", 74, 1381, 199, 1425),
    L("0714362384", 598, 1378, 767, 1422),
    L("Status", 74, 1481, 167, 1526),
    L("SUCCESS", 600, 1484, 745, 1522),
    L("This transaction was performed using iPay", 343, 1584, 854, 1620),
    L("For more information, visit www.ipay.lk", 72, 1790, 490, 1817),
]

r = extract(lines)
print("bank =", r.bank)
print("success =", r.success)
print("amount =", r.amount)
print("payee.account =", r.payee.account)
print("fields =", r.fields)
