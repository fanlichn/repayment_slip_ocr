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

def cy(box):
    return sum(p[1] for p in box) / len(box)

# OLD text-only dedup
old = {}
for ln in lines:
    k = ln.text.strip().lower()
    if not k:
        continue
    if k not in old or ln.confidence > old[k].confidence:
        old[k] = ln
old_lines = sorted(old.values(), key=lambda l: l.confidence, reverse=True)

# NEW position dedup
new_lines = E.dedup_lines(lines)

for name, ls in (("OLD", old_lines), ("NEW", new_lines)):
    a, f, t = E._extract_amounts(ls)
    print(f"\n=== {name} dedup: amount={a} fee={f} total={t} ===")