import re
from app.config import get_settings
from app.ocr_engine import create_engine
from app.preprocessing import build_variants, load_image
import repayment_slip_ocr.extractor as E

IMG = r"c:\Users\1\.trae-cn\attachments\6ac7329daa0ff9b00df25f37\266d2cdc-fcad-4791-86f0-a14f107ac8fc_d695a2fc-3433-40dc-9099-fdd3180d9399_image.png"

settings = get_settings()
engine = create_engine(settings)
engine.warmup()

with open(IMG, "rb") as f:
    img = load_image(f.read())

lines = []
for variant in build_variants(img):
    lines.extend(engine.recognize(variant["img"]))

dedup = {}
for ln in lines:
    key = ln.text.strip().lower()
    if not key:
        continue
    if key not in dedup or ln.confidence > dedup[key].confidence:
        dedup[key] = ln
unique = sorted(dedup.values(), key=lambda l: l.confidence, reverse=True)

def cx(box):
    return sum(p[0] for p in box) / len(box)
def cy(box):
    return sum(p[1] for p in box) / len(box)

print("=== deduped unique lines (breakdown region y>1150) ===")
for ln in sorted(unique, key=lambda l: cy(l.box)):
    if cy(ln.box) > 1150:
        print(f"y={cy(ln.box):7.1f} cx={cx(ln.box):7.1f} conf={ln.confidence:.3f} | {ln.text!r}")

# reproduce _breakdown_from_columns internals
ordered = E._sorted_by_y(unique)
headers = {}
for ln in ordered:
    t = ln.text.strip().lower().rstrip(":.")
    if t in ("notes", "value", "amount") and t not in headers:
        headers[t] = (ln, E._line_center_x(ln.box), E._line_center_y(ln.box))
print("\nheaders:", {k: (v[1], v[2]) for k, v in headers.items()})
if all(k in headers for k in ("notes", "value", "amount")):
    notes_cx, value_cx, amount_cx = headers["notes"][1], headers["value"][1], headers["amount"][1]
    b1 = (notes_cx + value_cx) / 2
    b2 = (value_cx + amount_cx) / 2
    header_y = min(headers[k][2] for k in headers)
    print(f"b1={b1:.1f} b2={b2:.1f} header_y={header_y:.1f}")
    qty_rows, denom_rows, amount_rows = [], [], []
    for ln in ordered:
        y = E._line_center_y(ln.box)
        if y <= header_y + 2:
            continue
        t = ln.text.strip().lower().rstrip(":.")
        if t in ("notes", "value", "amount") or "deposit amount" in t:
            continue
        c = E._line_center_x(ln.box)
        text = ln.text.strip()
        if c < b1:
            m = re.fullmatch(r"\d{1,3}", text)
            if m:
                qty_rows.append((y, int(m.group(0))))
        elif c < b2:
            val = E._parse_money(text)
            print(f"  [value col] y={y:.1f} cx={c:.1f} text={text!r} money={val}")
            if val is not None and val in E._COMMON_DENOMS:
                denom_rows.append((y, val))
        else:
            val = E._parse_money(text)
            print(f"  [amount col] y={y:.1f} cx={c:.1f} text={text!r} money={val}")
            if val is not None:
                amount_rows.append((y, val))
    print("\nqty_rows:", sorted(qty_rows))
    print("denom_rows:", sorted(denom_rows))
    print("amount_rows:", sorted(amount_rows))