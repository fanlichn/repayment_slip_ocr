import os
from app.config import get_settings
from app.ocr_engine import create_engine
from app.preprocessing import build_variants, load_image

DIR = r"c:\Users\1\.trae-cn\attachments\6ac7329daa0ff9b00df25f37"
EXTS = (".jpg", ".png", ".jpeg")

settings = get_settings()
engine = create_engine(settings)
engine.warmup()


def cy(box):
    ys = [p[1] for p in box]
    return sum(ys) / len(ys)


for name in sorted(os.listdir(DIR)):
    if not name.lower().endswith(EXTS):
        continue
    path = os.path.join(DIR, name)
    try:
        with open(path, "rb") as f:
            img = load_image(f.read())
    except Exception as e:
        print(f"\n=== {name} LOAD ERROR {e} ===")
        continue
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
    print(f"\n===== {name} ({len(unique)} lines) =====")
    for ln in sorted(unique, key=lambda l: cy(l.box)):
        x = min(p[0] for p in ln.box)
        print(f"y={cy(ln.box):7.1f} x={x:7.1f} conf={ln.confidence:.3f} | {ln.text!r}")