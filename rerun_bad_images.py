"""重跑 44 张有问题的图片，验证修复效果。

独立脚本，不依赖任何项目文件，直接调用本地 OCR 服务。
用法: python rerun_bad_images.py
"""
import os
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ===== 写死的配置 =====
OCR_URL = "http://127.0.0.1:8000/ocr"
OUTPUT = "/root/clf/temp/rerun_bad_result.json"
WORKERS = 1  # 并发数

# 44 张有问题的图片路径（写死）
IMAGES = [
    "/root/clf/temp/3100406840/202607/3100406840_1785219254578_28723052.jpg",
    "/root/clf/temp/3100406846/202609/3100406846_1790320787568_ceb8293d.jpg",
    "/root/clf/temp/3100406846/202609/3100406846_1790320841386_818eb503.jpg",
    "/root/clf/temp/3100406846/202609/3100406846_1790322488268_399b0f70.jpg",
    "/root/clf/temp/3100410218/202608/3100410218_1786608092352_5e6f4120.jpg",
    "/root/clf/temp/3100410218/202608/3100410218_1786609287305_03776bce.jpg",
    "/root/clf/temp/3100410261/202608/3100410261_1786447819348_b8f9a614.jpg",
    "/root/clf/temp/3100410309/202610/3100410309_1790832281033_21a27390.jpg",
    "/root/clf/temp/3100410309/202610/3100410309_1790837141516_d7d39f05.jpg",
    "/root/clf/temp/3100411677/202608/3100411677_1788150649780_72c1cc79.jpg",
    "/root/clf/temp/3100411797/202608/3100411797_1786173107117_ff0661e5.jpg",
    "/root/clf/temp/3100411797/202608/3100411797_1786173122973_393d1bfa.jpg",
    "/root/clf/temp/3100411797/202608/3100411797_1786177587263_3afc2fee.jpg",
    "/root/clf/temp/3100411797/202608/3100411797_1786179571244_d668f657.jpg",
    "/root/clf/temp/3100414113/202610/3100414113_1791957631579_0e17f93a.jpg",
    "/root/clf/temp/3100414441/202608/3100414441_1786950649230_fe359716.jpg",
    "/root/clf/temp/3100414441/202608/3100414441_1786950667979_9412eb06.jpg",
    "/root/clf/temp/3100415645/202608/3100415645_1787037963373_b84915b5.jpg",
    "/root/clf/temp/3100415645/202608/3100415645_1787039486402_e40faa96.jpg",
    "/root/clf/temp/3100415645/202608/3100415645_1787054491774_44555d9f.jpg",
    "/root/clf/temp/3100415645/202608/3100415645_1787054563921_98e237d1.jpg",
    "/root/clf/temp/3100416270/202608/3100416270_1787031730113_2a89074e.jpg",
    "/root/clf/temp/3100424676/202609/3100424676_1788848603500_712041d6.jpg",
    "/root/clf/temp/3100424676/202609/3100424676_1788849308871_3f3d534c.jpg",
    "/root/clf/temp/3100424489/202609/3100424489_1788506289698_f7bd5a2d.jpg",
    "/root/clf/temp/3100424763/202609/3100424763_1788590415508_df4bbdad.jpg",
    "/root/clf/temp/3100429630/202609/3100429630_1790432604969_f1b1f256.jpg",
    "/root/clf/temp/3100435365/202609/3100435365_1790268875642_4743c44f.jpg",
    "/root/clf/temp/3100435365/202609/3100435365_1790268883396_2694e726.jpg",
    "/root/clf/temp/3100435365/202609/3100435365_1790268900064_5403dcec.jpg",
    "/root/clf/temp/3100435365/202610/3100435365_1790793746166_5d27218e.jpg",
    "/root/clf/temp/3100435365/202610/3100435365_1790793746342_532b75f0.jpg",
    "/root/clf/temp/3100435365/202610/3100435365_1790793746344_1ddc5231.jpg",
    "/root/clf/temp/3100435365/202610/3100435365_1790822913442_922b20ab.jpg",
    "/root/clf/temp/3100435365/202610/3100435365_1790822918151_7ef9814d.jpg",
    "/root/clf/temp/3100435365/202610/3100435365_1790830596726_58e19d8e.jpg",
    "/root/clf/temp/3100435365/202610/3100435365_1790837349530_832f1a55.jpg",
    "/root/clf/temp/3100435365/202610/3100435365_1790837349600_6556c0d4.jpg",
    "/root/clf/temp/3100435365/202610/3100435365_1790837349665_0353cd04.jpg",
    "/root/clf/temp/3100435365/202610/3100435365_1790837349773_4aac96b8.jpg",
    "/root/clf/temp/3100435365/202610/3100435365_1790837350070_90d74001.jpg",
    "/root/clf/temp/3100439015/202610/3100439015_1790923576656_f2c0ff14.jpg",
    "/root/clf/temp/3100443246/202610/3100443246_1791374592083_daad7ae3.jpg",
    "/root/clf/temp/3100443246/202610/3100443246_1791394314997_24ade888.jpg",
]


def bsum(bd):
    return sum(d.get("amount", 0) for d in (bd or []))


def bstr(bd):
    if not bd:
        return "(空)"
    return " + ".join(f"{int(d['denomination'])}x{d['quantity']}" for d in bd)


lock = Lock()


def do_ocr(image_path):
    with open(image_path, "rb") as f:
        resp = requests.post(
            OCR_URL,
            files={"file": (os.path.basename(image_path), f, "image/jpeg")},
            timeout=120,
        )
    return resp.json()


def process_one(i, img_path):
    """单张图片处理，返回结果 dict。"""
    try:
        r = do_ocr(img_path)
        amt = r.get("amount")
        fee = r.get("fee")
        total = r.get("total_debit")
        bd = r.get("deposit_breakdown", [])
        bs = bsum(bd)
        warns = r.get("warnings", [])
        return {
            "idx": i,
            "image": os.path.basename(img_path),
            "amount": amt,
            "fee": fee,
            "total_debit": total,
            "bd_sum": bs,
            "breakdown": bd,
            "warnings": warns,
            "still_bad": bool(warns),
        }
    except Exception as e:
        return {
            "idx": i,
            "image": os.path.basename(img_path),
            "error": str(e),
            "still_bad": True,
        }


def save(results):
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def main():
    print(f"共 {len(IMAGES)} 张图片，并发数 {WORKERS}")
    results = []

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(process_one, i, img): (i, img)
            for i, img in enumerate(IMAGES)
        }

        for count, future in enumerate(as_completed(futures), 1):
            i, img_path = futures[future]
            result = future.result()
            with lock:
                results.append(result)
                # 每 5 张保存一次
                if count % 5 == 0:
                    save(results)

            print(f"\n[{count}/{len(IMAGES)}] {result['image']}")
            if result.get("error"):
                print(f"  异常: {result['error']}")
            else:
                print(f"  amount={result['amount']} fee={result['fee']} total={result['total_debit']} bd_sum={result['bd_sum']}")
                print(f"  bd={bstr(result.get('breakdown', []))}")
                print(f"  warnings={result['warnings']}")

    # 统计
    results.sort(key=lambda x: x["idx"])
    fixed = sum(1 for r in results if not r.get("still_bad"))
    still = sum(1 for r in results if r.get("still_bad"))
    print(f"\n{'='*50}")
    print(f"已修复: {fixed}, 仍有问题: {still}")
    print(f"{'='*50}")

    if still > 0:
        print("\n仍有问题的图片:")
        for r in results:
            if r.get("still_bad"):
                print(f"  {r['image']} | amount={r.get('amount')} | warns={r.get('warnings')}")

    save(results)
    print(f"\n结果写入: {OUTPUT}")


if __name__ == "__main__":
    main()
