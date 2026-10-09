from app.config import get_settings
from app.ocr_engine import create_engine
from app.preprocessing import build_variants, load_image

IMG = r"c:\Users\1\.trae-cn\attachments\6ac7329daa0ff9b00df25f37\266d2cdc-fcad-4791-86f0-a14f107ac8fc_d695a2fc-3433-40dc-9099-fdd3180d9399_image.png"

settings = get_settings()
engine = create_engine(settings)
engine.warmup()

with open(IMG, "rb") as f:
    img = load_image(f.read())

lines = []
for vi, variant in enumerate(build_variants(img)):
    for ln in engine.recognize(variant["img"]):
        lines.append((vi, ln))


def cy(box):
    ys = [p[1] for p in box]
    return sum(ys) / len(ys)


for vi, ln in sorted(lines, key=lambda t: (cy(t[1].box), min(p[0] for p in t[1].box))):
    x0 = min(p[0] for p in ln.box)
    x1 = max(p[0] for p in ln.box)
    y = cy(ln.box)
    print(f"v={vi} y={y:7.1f} x0={x0:7.1f} x1={x1:7.1f} conf={ln.confidence:.3f} | {ln.text!r}")