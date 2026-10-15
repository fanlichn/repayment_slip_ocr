"""重跑 OCR 警告记录，对比新旧结果。

独立脚本，不依赖项目代码，直接调用本地 OCR 服务。
只需：旧 JSON 文件 + 本地图片 + 运行中的 OCR 服务。

用法:
    python rerun_failed.py
"""
import os
import json
import requests
import time

# ===== 写死的配置 =====
OLD_JSON = "/root/clf/temp/OCR成功且有警告.json"   # 旧结果 JSON
OCR_URL = "http://127.0.0.1:8000/ocr"              # OCR 服务地址
OUTPUT = "/root/clf/temp/rerun_result.json"        # 输出对比结果


def load_old():
    with open(OLD_JSON, "r", encoding="utf-8") as f:
        text = f.read()
    # 文件开头缺 '['，多个 JSON 对象拼接
    return json.loads("[" + text)


def bsum(bd):
    return sum(d.get("amount", 0) for d in (bd or []))


def bstr(bd):
    if not bd:
        return "(空)"
    return " + ".join(f"{int(d['denomination'])}x{d['quantity']}" for d in bd)


def do_ocr(image_path):
    with open(image_path, "rb") as f:
        resp = requests.post(
            OCR_URL,
            files={"file": (os.path.basename(image_path), f, "image/jpeg")},
            timeout=120,
        )
    return resp.json()


def main():
    old_items = load_old()
    print(f"旧结果共 {len(old_items)} 条")

    results = []
    t0 = time.time()

    for i, item in enumerate(old_items):
        old = item["result"]
        old_amt = old.get("amount")
        old_bd = old.get("deposit_breakdown", [])
        old_bs = bsum(old_bd)
        old_dt = old.get("datetime", "")
        old_w = old.get("warnings", [])
        img_path = item["image"]

        print(f"\n[{i}/{len(old_items)}] {os.path.basename(img_path)}")
        print(f"  旧: amount={old_amt} bd_sum={old_bs} bd={bstr(old_bd)} dt={old_dt}")

        try:
            new = do_ocr(img_path)
            new_amt = new.get("amount")
            new_bd = new.get("deposit_breakdown", [])
            new_bs = bsum(new_bd)
            new_dt = new.get("datetime", "")
            new_w = new.get("warnings", [])

            print(f"  新: amount={new_amt} bd_sum={new_bs} bd={bstr(new_bd)} dt={new_dt}")
            print(f"  新警告: {new_w}")

            # 判断是否修复
            fixed = False
            if old_amt is not None and old_amt < 100 and old_bs > 100:
                if new_amt is not None and abs(new_amt - new_bs) < 0.01 and new_amt >= 100:
                    fixed = True
            elif any("加总" in w for w in old_w):
                still = any("加总" in w for w in new_w)
                if not still and new_amt is not None and abs(new_amt - new_bs) < 0.01:
                    fixed = True

            status = "FIXED" if fixed else ("SAME" if new_w else "NO_WARNING_NOW")
            print(f"  状态: {status}")

            results.append({
                "idx": i,
                "image": os.path.basename(img_path),
                "status": status,
                "old_amount": old_amt, "new_amount": new_amt,
                "old_bd_sum": old_bs, "new_bd_sum": new_bs,
                "old_breakdown": old_bd, "new_breakdown": new_bd,
                "old_datetime": old_dt, "new_datetime": new_dt,
                "old_warnings": old_w, "new_warnings": new_w,
            })
        except Exception as e:
            print(f"  异常: {e}")
            results.append({
                "idx": i,
                "image": os.path.basename(img_path),
                "error": str(e),
                "old_amount": old_amt, "old_bd_sum": old_bs,
                "old_breakdown": old_bd, "old_datetime": old_dt,
                "old_warnings": old_w,
            })

        # 每 20 条保存一次
        if (i + 1) % 20 == 0:
            with open(OUTPUT, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0
    print(f"\n完成，耗时 {elapsed:.1f}s")

    fc = sum(1 for r in results if r.get("status") == "FIXED")
    sc = sum(1 for r in results if r.get("status") == "SAME")
    nc = sum(1 for r in results if r.get("status") == "NO_WARNING_NOW")
    ec = sum(1 for r in results if r.get("error"))
    print(f"修复: {fc}, 仍有警告: {sc}, 无警告: {nc}, 异常: {ec}")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"结果写入: {OUTPUT}")


if __name__ == "__main__":
    main()
