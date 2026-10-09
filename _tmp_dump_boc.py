import sys
from app.config import get_settings
from app.ocr_engine import create_engine
from app.preprocessing import build_variants, load_image

IMG = r"c:\Users\1\.trae-cn\attachments\6ac7329daa0ff9b00df25f37\7711ef9e-7f7d-4e4f-899b-8527d56bb811_ca48fbd0-26e8-4dea-86e9-17167712dcad_3100433519_1791467540808_74540366.jpg.disp.jpg"

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
unique = list(dedup.values())


def cy(box):
    ys = [p[1] for p in box]
    return sum(ys) / len(ys)


for ln in sorted(unique, key=lambda l: cy(l.box)):
    x = min(p[0] for p in ln.box)
    print(f"y={cy(ln.box):7.1f} x={x:7.1f} conf={ln.confidence:.3f} | {ln.text!r}")