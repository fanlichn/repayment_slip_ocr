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

old = {}
for ln in lines:
    k = ln.text.strip().lower()
    if not k:
        continue
    if k not in old or ln.confidence > old[k].confidence:
        old[k] = ln
old_lines = sorted(old.values(), key=lambda l: l.confidence, reverse=True)

def cx(box):
    return sum(p[0] for p in box) / len(box)
def cy(box):
    return sum(p[1] for p in box) / len(box)

print("=== OLD lines with 'amount'/'deposit' ===")
ordered = E._sorted_by_y(old_lines)
for i, ln in enumerate(ordered):
    low = ln.text.lower()
    if "amount" in low or "deposit" in low:
        side = E._value_to_right(i, ordered, ln)
        print(f"y={cy(ln.box):7.1f} cx={cx(ln.box):7.1f} | {ln.text!r} money={E._parse_money(ln.text)} side={side!r}")

print("\n=== OLD lines with 'lkr' (fallback scan) ===")
for ln in ordered:
    low = ln.text.lower()
    if "lkr" in low or "rs." in low or low.startswith("rs"):
        print(f"y={cy(ln.box):7.1f} cx={cx(ln.box):7.1f} | {ln.text!r} money={E._parse_money(ln.text)}")