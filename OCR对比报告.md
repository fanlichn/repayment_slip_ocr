# OCR 结果对比报告

总记录数: 505

报告生成时间: 2026-08-14


## 问题分类统计

| 类别 | 数量 | 说明 |
|------|------|------|
| 金额明显错误 (amount<100) | 169 | amount 被 OCR 读成个位数，正确值=明细加总 |
| 日期错误 (年份非20xx) | 5 | 日期解析问题 |
| 明细加总>金额 (金额≥100) | 150 | 金额通常正确，明细有幻影行或数量偏大 |
| 金额>明细加总 (金额≥100) | 136 | 金额通常正确，明细有行丢失或数量偏小 |
| 其他警告 | 45 | 需单独检查 |

## 一、金额明显错误 (169条)

**问题**: `amount` 被 OCR 错误识别为个位数（如 LKR→1.KR→1.0，5,000→5），但明细加总正常。

**正确金额**: 等于 `deposit_breakdown` 各项之和。

**修复状态**: 最新代码已有 `_parse_money` 过滤短串 + 明细加总优先覆盖逻辑，部署后应修复。


| idx | 图片 | OCR amount | 正确金额(明细加总) | 明细 |
|-----|------|-----------|-------------------|------|
| [18](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406788/202607/3100406788_1785208590263_f86e41cc.jpg) | 3100406788_1785208590263_f86e41cc.jpg | 5.0 | **5000.0** | 5000×1 |
| [27](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407388/202607/3100407388_1785147087137_5bbcff8f.jpg) | 3100407388_1785147087137_5bbcff8f.jpg | 1.0 | **5000.0** | 1000×5 |
| [28](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407388/202607/3100407388_1785147116347_ff50d87d.jpg) | 3100407388_1785147116347_ff50d87d.jpg | 1.0 | **5000.0** | 1000×5 |
| [29](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407388/202607/3100407388_1785147124356_d3d5a55d.jpg) | 3100407388_1785147124356_d3d5a55d.jpg | 1.0 | **5000.0** | 1000×5 |
| [39](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407592/202607/3100407592_1785216761902_552a7663.jpg) | 3100407592_1785216761902_552a7663.jpg | 4.0 | **5000.0** | 5000×1 |
| [40](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407592/202607/3100407592_1785216804383_91631f6e.jpg) | 3100407592_1785216804383_91631f6e.jpg | 4.0 | **5000.0** | 5000×1 |
| [47](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407731/202608/3100407731_1787038793824_325d1d82.jpg) | 3100407731_1787038793824_325d1d82.jpg | 11.0 | **3200.0** | 100×2 + 500×2 + 1000×2 |
| [54](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407731/202608/3100407731_1787467851834_712db923.jpg) | 3100407731_1787467851834_712db923.jpg | 14.6 | **49600.0** | 100×6 + 500×2 + 1000×8 + 5000×8 |
| [55](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407731/202608/3100407731_1787467872149_f18f8b58.jpg) | 3100407731_1787467872149_f18f8b58.jpg | 14.6 | **49600.0** | 100×6 + 500×2 + 1000×8 + 5000×8 |
| [56](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407872/202610/3100407872_1791034960535_7bd3a3c1.jpg) | 3100407872_1791034960535_7bd3a3c1.jpg | 53.0 | **15300.0** | 100×3 + 5000×3 |
| [57](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408027/202608/3100408027_1785576250785_faaac3ba.jpg) | 3100408027_1785576250785_faaac3ba.jpg | 1.0 | **5000.0** | 5000×1 |
| [58](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408027/202608/3100408027_1785576277055_7747b7c6.jpg) | 3100408027_1785576277055_7747b7c6.jpg | 1.0 | **5000.0** | 5000×1 |
| [61](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408664/202608/3100408664_1786364661172_8c576a5e.jpg) | 3100408664_1786364661172_8c576a5e.jpg | 7.3 | **10300.0** | 100×3 + 5000×2 |
| [62](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408353/202609/3100408353_1790065088239_4d0c2db5.jpg) | 3100408353_1790065088239_4d0c2db5.jpg | 5.0 | **5000.0** | 5000×1 |
| [63](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408353/202609/3100408353_1790065154665_2dde3577.jpg) | 3100408353_1790065154665_2dde3577.jpg | 5.0 | **5000.0** | 5000×1 |
| [76](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409162/202610/3100409162_1791199324791_2c9fba32.jpg) | 3100409162_1791199324791_2c9fba32.jpg | 1.0 | **3400.0** | 100×4 + 500×2 + 1000×2 |
| [92](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409922/202610/3100409922_1791189334741_ce6ab246.jpg) | 3100409922_1791189334741_ce6ab246.jpg | 1.0 | **12000.0** | 1000×2 + 5000×2 |
| [99](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410251/202608/3100410251_1786369087034_cb4ea7b5.jpg) | 3100410251_1786369087034_cb4ea7b5.jpg | 5.0 | **5000.0** | 500×2 + 1000×4 |
| [100](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410251/202608/3100410251_1786369346860_7a3736de.jpg) | 3100410251_1786369346860_7a3736de.jpg | 5.0 | **5000.0** | 500×2 + 1000×4 |
| [101](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410102/202609/3100410102_1788230470268_91c5416d.jpg) | 3100410102_1788230470268_91c5416d.jpg | 0.3 | **7000.0** | 1000×2 + 5000×1 |
| [102](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410102/202609/3100410102_1788230452610_cd138df7.jpg) | 3100410102_1788230452610_cd138df7.jpg | 0.3 | **7000.0** | 1000×2 + 5000×1 |
| [103](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410251/202608/3100410251_1786372716539_ea20490f.jpg) | 3100410251_1786372716539_ea20490f.jpg | 5.0 | **5000.0** | 500×2 + 1000×4 |
| [104](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410251/202608/3100410251_1786374931735_97514422.jpg) | 3100410251_1786374931735_97514422.jpg | 5.0 | **5000.0** | 500×2 + 1000×4 |
| [110](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410661/202608/3100410661_1786340213119_bf22d5bb.jpg) | 3100410661_1786340213119_bf22d5bb.jpg | 5.0 | **5000.0** | 5000×1 |
| [112](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410660/202609/3100410660_1789211872550_08cb40e3.jpg) | 3100410660_1789211872550_08cb40e3.jpg | 1.0 | **11400.0** | 100×4 + 500×4 + 1000×4 + 5000×1 |
| [113](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410660/202609/3100410660_1789265643322_ed9fcca9.jpg) | 3100410660_1789265643322_ed9fcca9.jpg | 1.0 | **11400.0** | 100×4 + 500×4 + 1000×4 + 5000×1 |
| [114](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410661/202608/3100410661_1786340241859_b5f210c8.jpg) | 3100410661_1786340241859_b5f210c8.jpg | 5.0 | **5000.0** | 5000×1 |
| [119](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411228/202608/3100411228_1786690461715_7cb6a1d6.jpg) | 3100411228_1786690461715_7cb6a1d6.jpg | 1.0 | **6900.0** | 100×4 + 500×1 + 1000×1 + 5000×1 |
| [120](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411441/202608/3100411441_1786446423046_40d70100.jpg) | 3100411441_1786446423046_40d70100.jpg | 5.0 | **5000.0** | 5000×1 |
| [121](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411441/202608/3100411441_1786446461004_34d8b722.jpg) | 3100411441_1786446461004_34d8b722.jpg | 5.0 | **5000.0** | 5000×1 |
| [123](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411561/202608/3100411561_1786607746316_2b6bcf6c.jpg) | 3100411561_1786607746316_2b6bcf6c.jpg | 1.0 | **3000.0** | 500×2 + 1000×2 |
| [125](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411677/202608/3100411677_1787116295555_9b3e58db.jpg) | 3100411677_1787116295555_9b3e58db.jpg | 6.6 | **5600.0** | 100×1 + 500×1 + 5000×1 |
| [131](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411885/202608/3100411885_1787795380871_47cc5797.jpg) | 3100411885_1787795380871_47cc5797.jpg | 19.0 | **5150.0** | 5000×1 + 100×1 + 50×1 |
| [136](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411966/202608/3100411966_1787299158746_4650349e.jpg) | 3100411966_1787299158746_4650349e.jpg | 5.0 | **3000.0** | 500×4 + 1000×1 |
| [154](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412887/202609/3100412887_1790054460366_a454365f.jpg) | 3100412887_1790054460366_a454365f.jpg | 5.0 | **5000.0** | 5000×1 |
| [155](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412887/202609/3100412887_1790054438570_acfecc79.jpg) | 3100412887_1790054438570_acfecc79.jpg | 5.0 | **5000.0** | 5000×1 |
| [166](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100413118/202608/3100413118_1787410380567_0809af9e.jpg) | 3100413118_1787410380567_0809af9e.jpg | 3.0 | **13000.0** | 500×2 + 1000×2 + 10000×1 |
| [170](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100413707/202608/3100413707_1787235585392_a529bd6d.jpg) | 3100413707_1787235585392_a529bd6d.jpg | 5.0 | **5000.0** | 1000×5 |
| [171](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100413707/202608/3100413707_1787235602171_f6864480.jpg) | 3100413707_1787235602171_f6864480.jpg | 5.0 | **5000.0** | 1000×5 |
| [172](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100413707/202608/3100413707_1787238461647_4a1e0d02.jpg) | 3100413707_1787238461647_4a1e0d02.jpg | 5.0 | **5000.0** | 1000×5 |
| [173](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100413707/202608/3100413707_1787238660156_ba3b0718.jpg) | 3100413707_1787238660156_ba3b0718.jpg | 5.0 | **5000.0** | 1000×5 |
| [174](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100413707/202608/3100413707_1787267273672_d8c4ee9f.jpg) | 3100413707_1787267273672_d8c4ee9f.jpg | 5.0 | **5000.0** | 1000×5 |
| [175](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100413707/202608/3100413707_1787284006244_bf67e340.jpg) | 3100413707_1787284006244_bf67e340.jpg | 5.0 | **5000.0** | 1000×5 |
| [176](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100413707/202608/3100413707_1787833755525_6651faee.jpg) | 3100413707_1787833755525_6651faee.jpg | 6.0 | **5650.0** | 100×1 + 500×1 + 50×1 + 5000×1 |
| [177](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100413707/202608/3100413707_1787833779138_ca6858bc.jpg) | 3100413707_1787833779138_ca6858bc.jpg | 6.6 | **600.0** | 100×1 + 500×1 |
| [182](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100414611/202608/3100414611_1786773564272_535eaaef.jpg) | 3100414611_1786773564272_535eaaef.jpg | 11.0 | **5050.0** | 50×1 + 5000×1 |
| [183](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100415559/202608/3100415559_1787558146913_6087027a.jpg) | 3100415559_1787558146913_6087027a.jpg | 1.0 | **6900.0** | 100×4 + 500×5 + 1000×4 |
| [184](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100415559/202608/3100415559_1787558174671_89e99c6a.jpg) | 3100415559_1787558174671_89e99c6a.jpg | 1.0 | **6900.0** | 100×4 + 500×5 + 1000×4 |
| [189](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100415683/202608/3100415683_1786861190805_00c37590.jpg) | 3100415683_1786861190805_00c37590.jpg | 5.0 | **5000.0** | 5000×1 |
| [190](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100415683/202608/3100415683_1786861397875_fb235666.jpg) | 3100415683_1786861397875_fb235666.jpg | 5.0 | **5000.0** | 5000×1 |
| [191](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100415683/202608/3100415683_1786863506784_f7ac3c3d.jpg) | 3100415683_1786863506784_f7ac3c3d.jpg | 5.0 | **5000.0** | 5000×1 |
| [192](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100415742/202608/3100415742_1786962997374_401a96c1.jpg) | 3100415742_1786962997374_401a96c1.jpg | 1.0 | **5050.0** | 50×1 + 5000×1 |
| [193](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100415742/202608/3100415742_1786963039850_01c9fd99.jpg) | 3100415742_1786963039850_01c9fd99.jpg | 1.0 | **5050.0** | 50×1 + 5000×1 |
| [194](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100415841/202608/3100415841_1787135656499_44357877.jpg) | 3100415841_1787135656499_44357877.jpg | 5.0 | **5000.0** | 5000×1 |
| [197](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416308/202609/3100416308_1790335167805_f1c0b736.jpg) | 3100416308_1790335167805_f1c0b736.jpg | 5.0 | **5000.0** | 5000×1 |
| [200](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416472/202609/3100416472_1788660621404_5a374b69.jpg) | 3100416472_1788660621404_5a374b69.jpg | 1.0 | **1000.0** | 1000×1 |
| [201](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416472/202609/3100416472_1788660473112_a4ac69d7.jpg) | 3100416472_1788660473112_a4ac69d7.jpg | 1.0 | **1000.0** | 1000×1 |
| [203](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416472/202609/3100416472_1788664631188_e64d4d15.jpg) | 3100416472_1788664631188_e64d4d15.jpg | 1.0 | **1000.0** | 1000×1 |
| [204](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416472/202609/3100416472_1788664631885_02a6a7a6.jpg) | 3100416472_1788664631885_02a6a7a6.jpg | 1.0 | **1000.0** | 1000×1 |
| [215](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417425/202608/3100417425_1787817479802_bbd8b1ec.jpg) | 3100417425_1787817479802_bbd8b1ec.jpg | 4.0 | **13300.0** | 100×3 + 1000×3 + 5000×2 |
| [216](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417425/202608/3100417425_1787819860427_a185cd2d.jpg) | 3100417425_1787819860427_a185cd2d.jpg | 4.0 | **13300.0** | 100×3 + 1000×3 + 5000×2 |
| [217](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417425/202608/3100417425_1787819940258_0c952b87.jpg) | 3100417425_1787819940258_0c952b87.jpg | 4.0 | **13300.0** | 100×3 + 1000×3 + 5000×2 |
| [218](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417425/202608/3100417425_1787820656527_35a1570c.jpg) | 3100417425_1787820656527_35a1570c.jpg | 4.0 | **13300.0** | 100×3 + 1000×3 + 5000×2 |
| [219](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417425/202608/3100417425_1787825170841_3c9a9e9a.jpg) | 3100417425_1787825170841_3c9a9e9a.jpg | 4.0 | **13300.0** | 100×3 + 1000×3 + 5000×2 |
| [220](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417425/202608/3100417425_1787825178539_e01ad9d5.jpg) | 3100417425_1787825178539_e01ad9d5.jpg | 4.0 | **13300.0** | 100×3 + 1000×3 + 5000×2 |
| [221](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417425/202608/3100417425_1787825191447_e8736917.jpg) | 3100417425_1787825191447_e8736917.jpg | 4.0 | **13300.0** | 100×3 + 1000×3 + 5000×2 |
| [222](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417425/202608/3100417425_1787837115822_7664a457.jpg) | 3100417425_1787837115822_7664a457.jpg | 4.0 | **13300.0** | 100×3 + 1000×3 + 5000×2 |
| [223](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417425/202608/3100417425_1787888608351_983752b6.jpg) | 3100417425_1787888608351_983752b6.jpg | 4.0 | **13300.0** | 100×3 + 1000×3 + 5000×2 |
| [227](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417804/202608/3100417804_1787827744997_4471676d.jpg) | 3100417804_1787827744997_4471676d.jpg | 2.2 | **2100.0** | 100×1 + 1000×2 |
| [231](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418264/202608/3100418264_1787388254812_8656aafa.jpg) | 3100418264_1787388254812_8656aafa.jpg | 5.0 | **5000.0** | 5000×1 |
| [232](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418264/202608/3100418264_1787389302226_cfe6dae0.jpg) | 3100418264_1787389302226_cfe6dae0.jpg | 5.0 | **5000.0** | 5000×1 |
| [233](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418264/202608/3100418264_1787392317467_5001c25b.jpg) | 3100418264_1787392317467_5001c25b.jpg | 5.0 | **5000.0** | 5000×1 |
| [246](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100419852/202608/3100419852_1788000062850_024403eb.jpg) | 3100419852_1788000062850_024403eb.jpg | 2.0 | **2000.0** | 1000×2 |
| [250](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100419952/202610/3100419952_1791430522166_9604a211.jpg) | 3100419952_1791430522166_9604a211.jpg | 21.6 | **21600.0** | 100×1 + 500×1 + 1000×1 + 5000×4 |
| [251](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100419993/202610/3100419993_1791549184091_92b7b5c5.jpg) | 3100419993_1791549184091_92b7b5c5.jpg | 6.2 | **6200.0** | 100×2 + 1000×1 + 5000×1 |
| [252](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100419993/202610/3100419993_1791549269453_f9ce08bf.jpg) | 3100419993_1791549269453_f9ce08bf.jpg | 6.2 | **6200.0** | 100×2 + 1000×1 + 5000×1 |
| [253](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100419993/202610/3100419993_1791550016072_40e74cc1.jpg) | 3100419993_1791550016072_40e74cc1.jpg | 6.2 | **6200.0** | 100×2 + 1000×1 + 5000×1 |
| [254](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100420513/202608/3100420513_1787915211062_fe93df0f.jpg) | 3100420513_1787915211062_fe93df0f.jpg | 3.0 | **5300.0** | 1000×3 + 100×3 + 2000×1 |
| [255](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100420513/202608/3100420513_1787915273803_4fb3df3c.jpg) | 3100420513_1787915273803_4fb3df3c.jpg | 3.0 | **5300.0** | 1000×3 + 100×3 + 2000×1 |
| [270](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421173/202610/3100421173_1791166806391_5d793724.jpg) | 3100421173_1791166806391_5d793724.jpg | 1.0 | **5000.0** | 5000×1 |
| [271](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421323/202609/3100421323_1789362366314_9f47cb3a.jpg) | 3100421323_1789362366314_9f47cb3a.jpg | 5.0 | **11000.0** | 100×10 + 1000×4 + 500×2 + 5000×1 |
| [272](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421173/202610/3100421173_1791167634386_ea871a92.jpg) | 3100421173_1791167634386_ea871a92.jpg | 1.0 | **5000.0** | 5000×1 |
| [273](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421323/202609/3100421323_1789363687945_71651c48.jpg) | 3100421323_1789363687945_71651c48.jpg | 5.0 | **11000.0** | 100×10 + 1000×4 + 500×2 + 5000×1 |
| [279](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100422825/202609/3100422825_1789282641404_698b7881.jpg) | 3100422825_1789282641404_698b7881.jpg | 5.0 | **5000.0** | 5000×1 |
| [281](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423292/202609/3100423292_1789709079303_f1d5deaa.jpg) | 3100423292_1789709079303_f1d5deaa.jpg | 7.1 | **5100.0** | 100×1 + 5000×1 |
| [283](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423292/202609/3100423292_1789726827881_49f8ff6d.jpg) | 3100423292_1789726827881_49f8ff6d.jpg | 7.1 | **5100.0** | 100×1 + 5000×1 |
| [284](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423292/202609/3100423292_1789726875210_8396a4d5.jpg) | 3100423292_1789726875210_8396a4d5.jpg | 7.1 | **5100.0** | 100×1 + 5000×1 |
| [285](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423292/202609/3100423292_1789726929428_75f002db.jpg) | 3100423292_1789726929428_75f002db.jpg | 7.1 | **5100.0** | 100×1 + 5000×1 |
| [286](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423292/202609/3100423292_1789726951752_1f2234f2.jpg) | 3100423292_1789726951752_1f2234f2.jpg | 7.1 | **5100.0** | 100×1 + 5000×1 |
| [287](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423292/202609/3100423292_1789746599516_4bfc7fd3.jpg) | 3100423292_1789746599516_4bfc7fd3.jpg | 7.1 | **5100.0** | 100×1 + 5000×1 |
| [288](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423292/202609/3100423292_1789726958550_5cccb35d.jpg) | 3100423292_1789726958550_5cccb35d.jpg | 7.1 | **5100.0** | 100×1 + 5000×1 |
| [289](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423292/202609/3100423292_1789746574268_e6189b8d.jpg) | 3100423292_1789746574268_e6189b8d.jpg | 7.1 | **5100.0** | 100×1 + 5000×1 |
| [290](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423292/202610/3100423292_1790923490250_7fb991b6.jpg) | 3100423292_1790923490250_7fb991b6.jpg | 10.0 | **10000.0** | 5000×2 |
| [291](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423292/202609/3100423292_1790172677646_e95b094b.jpg) | 3100423292_1790172677646_e95b094b.jpg | 6.9 | **6900.0** | 100×4 + 500×13 |
| [292](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423848/202609/3100423848_1788253746904_f57c82ae.jpg) | 3100423848_1788253746904_f57c82ae.jpg | 1.0 | **5000.0** | 500×2 + 1000×4 |
| [295](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100424523/202609/3100424523_1789183388940_2266d27c.jpg) | 3100424523_1789183388940_2266d27c.jpg | 6.3 | **8100.0** | 1000×3 + 100×1 + 5000×1 |
| [304](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100425192/202609/3100425192_1789543672287_f78ea011.jpg) | 3100425192_1789543672287_f78ea011.jpg | 5.0 | **6100.0** | 100×1 + 1000×1 + 5000×1 |
| [305](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100425192/202609/3100425192_1789545137744_a28d9513.jpg) | 3100425192_1789545137744_a28d9513.jpg | 5.0 | **6100.0** | 100×1 + 1000×1 + 5000×1 |
| [307](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100425817/202609/3100425817_1790332105638_84f5bc43.jpg) | 3100425817_1790332105638_84f5bc43.jpg | 9.7 | **8750.0** | 100×2 + 500×5 + 1000×1 + 50×1 + 5000×1 |
| [314](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100426883/202609/3100426883_1788777961579_b65a43c1.jpg) | 3100426883_1788777961579_b65a43c1.jpg | 5.3 | **2000.0** | 500×4 |
| [315](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100427845/202609/3100427845_1789206071507_4239f96c.jpg) | 3100427845_1789206071507_4239f96c.jpg | 5.0 | **5000.0** | 5000×1 |
| [324](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100428069/202609/3100428069_1789721966385_28f6dab7.jpg) | 3100428069_1789721966385_28f6dab7.jpg | 1.0 | **6500.0** | 500×1 + 1000×1 + 5000×1 |
| [325](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100428113/202610/3100428113_1791614905851_75709363.jpg) | 3100428113_1791614905851_75709363.jpg | 3.0 | **3000.0** | 500×2 + 1000×2 |
| [326](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100428113/202610/3100428113_1791614934461_e1698f04.jpg) | 3100428113_1791614934461_e1698f04.jpg | 3.0 | **3000.0** | 500×2 + 1000×2 |
| [327](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100428466/202609/3100428466_1789283825084_6e686da3.jpg) | 3100428466_1789283825084_6e686da3.jpg | 5.0 | **5000.0** | 5000×1 |
| [328](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100428113/202610/3100428113_1791618109122_2f692050.jpg) | 3100428113_1791618109122_2f692050.jpg | 3.0 | **3000.0** | 500×2 + 1000×2 |
| [331](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100429523/202609/3100429523_1789479997321_935414cc.jpg) | 3100429523_1789479997321_935414cc.jpg | 1.0 | **5000.0** | 5000×1 |
| [333](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100429578/202609/3100429578_1789385513022_ccfea597.jpg) | 3100429578_1789385513022_ccfea597.jpg | 1.0 | **5000.0** | 5000×1 |
| [339](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100431373/202609/3100431373_1789817296255_c8eada7d.jpg) | 3100431373_1789817296255_c8eada7d.jpg | 5.0 | **5000.0** | 5000×1 |
| [344](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100432018/202610/3100432018_1791189643841_5c195aa2.jpg) | 3100432018_1791189643841_5c195aa2.jpg | 5.8 | **30500.0** | 10000×3 + 500×1 |
| [357](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433400/202609/3100433400_1790607331822_359eee0a.jpg) | 3100433400_1790607331822_359eee0a.jpg | 1.0 | **2000.0** | 500×2 + 1000×1 |
| [358](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433400/202609/3100433400_1790607429926_a6210ef3.jpg) | 3100433400_1790607429926_a6210ef3.jpg | 1.0 | **2000.0** | 500×2 + 1000×1 |
| [359](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433400/202609/3100433400_1790607388208_467d96ec.jpg) | 3100433400_1790607388208_467d96ec.jpg | 1.0 | **2000.0** | 500×2 + 1000×1 |
| [360](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433400/202609/3100433400_1790607859116_9c23fc60.jpg) | 3100433400_1790607859116_9c23fc60.jpg | 1.0 | **2000.0** | 500×2 + 1000×1 |
| [361](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433400/202609/3100433400_1790608645430_8cf49c57.jpg) | 3100433400_1790608645430_8cf49c57.jpg | 1.0 | **2000.0** | 500×2 + 1000×1 |
| [362](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433400/202609/3100433400_1790610900961_a4a4f458.jpg) | 3100433400_1790610900961_a4a4f458.jpg | 1.0 | **2000.0** | 500×2 + 1000×1 |
| [363](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433400/202609/3100433400_1790610908007_011c91fa.jpg) | 3100433400_1790610908007_011c91fa.jpg | 1.0 | **2000.0** | 500×2 + 1000×1 |
| [364](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433400/202609/3100433400_1790611877765_6be76657.jpg) | 3100433400_1790611877765_6be76657.jpg | 1.0 | **2000.0** | 500×2 + 1000×1 |
| [365](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433400/202609/3100433400_1790612510745_b0cdaed2.jpg) | 3100433400_1790612510745_b0cdaed2.jpg | 1.0 | **2000.0** | 500×2 + 1000×1 |
| [366](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433400/202609/3100433400_1790615025171_01763722.jpg) | 3100433400_1790615025171_01763722.jpg | 1.0 | **2000.0** | 500×2 + 1000×1 |
| [367](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433400/202609/3100433400_1790647209887_953a785f.jpg) | 3100433400_1790647209887_953a785f.jpg | 1.0 | **2000.0** | 500×2 + 1000×1 |
| [377](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434000/202609/3100434000_1790167621973_3d017fe2.jpg) | 3100434000_1790167621973_3d017fe2.jpg | 0.0 | **5000.0** | 5000×1 |
| [378](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434000/202609/3100434000_1790167664204_2238f7eb.jpg) | 3100434000_1790167664204_2238f7eb.jpg | 0.0 | **5000.0** | 5000×1 |
| [380](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434102/202609/3100434102_1790077714062_8ae95ad7.jpg) | 3100434102_1790077714062_8ae95ad7.jpg | 4.0 | **4000.0** | 500×2 + 1000×3 |
| [382](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434102/202609/3100434102_1790077822183_7e48f74c.jpg) | 3100434102_1790077822183_7e48f74c.jpg | 4.0 | **4000.0** | 500×2 + 1000×3 |
| [383](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434102/202609/3100434102_1790078427502_5b9db9ef.jpg) | 3100434102_1790078427502_5b9db9ef.jpg | 4.0 | **4000.0** | 500×2 + 1000×3 |
| [389](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434733/202610/3100434733_1791801681564_2407a416.jpg) | 3100434733_1791801681564_2407a416.jpg | 3.0 | **2000.0** | 2000×1 |
| [390](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434733/202610/3100434733_1791802192872_16dc2dcb.jpg) | 3100434733_1791802192872_16dc2dcb.jpg | 3.0 | **2000.0** | 2000×1 |
| [393](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434960/202609/3100434960_1790334890156_c1fb41f4.jpg) | 3100434960_1790334890156_c1fb41f4.jpg | 11.0 | **5050.0** | 50×1 + 5000×1 |
| [394](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435072/202609/3100435072_1790309165669_4f129985.jpg) | 3100435072_1790309165669_4f129985.jpg | 1.0 | **5500.0** | 500×1 + 5000×1 |
| [395](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435072/202609/3100435072_1790309134769_06d91af6.jpg) | 3100435072_1790309134769_06d91af6.jpg | 1.0 | **5500.0** | 500×1 + 5000×1 |
| [396](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435072/202609/3100435072_1790309317970_7181437e.jpg) | 3100435072_1790309317970_7181437e.jpg | 1.0 | **5500.0** | 500×1 + 5000×1 |
| [397](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435072/202609/3100435072_1790309623488_6ad41ad9.jpg) | 3100435072_1790309623488_6ad41ad9.jpg | 1.0 | **5500.0** | 500×1 + 5000×1 |
| [398](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435101/202609/3100435101_1790402597759_e105fcbf.jpg) | 3100435101_1790402597759_e105fcbf.jpg | 13.0 | **5100.0** | 100×1 + 5000×1 |
| [415](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1791380566779_cb32dc2f.jpg) | 3100435365_1791380566779_cb32dc2f.jpg | 8.0 | **30500.0** | 10000×3 + 500×1 |
| [416](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1791385252613_1495927a.jpg) | 3100435365_1791385252613_1495927a.jpg | 8.0 | **30500.0** | 10000×3 + 500×1 |
| [417](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1791428122784_a206cde5.jpg) | 3100435365_1791428122784_a206cde5.jpg | 8.0 | **30500.0** | 10000×3 + 500×1 |
| [418](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1791430876267_f8005641.jpg) | 3100435365_1791430876267_f8005641.jpg | 8.0 | **30500.0** | 10000×3 + 500×1 |
| [424](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435681/202609/3100435681_1790588897206_3e26866f.jpg) | 3100435681_1790588897206_3e26866f.jpg | 4.0 | **5300.0** | 100×3 + 1000×5 |
| [425](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435681/202609/3100435681_1790589200515_9d9c3da3.jpg) | 3100435681_1790589200515_9d9c3da3.jpg | 4.0 | **5300.0** | 100×3 + 1000×5 |
| [426](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435681/202609/3100435681_1790589811497_427d17f0.jpg) | 3100435681_1790589811497_427d17f0.jpg | 4.0 | **5300.0** | 100×3 + 1000×5 |
| [429](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100436196/202609/3100436196_1790662769806_9d64ab01.jpg) | 3100436196_1790662769806_9d64ab01.jpg | 11.0 | **5100.0** | 100×1 + 5000×1 |
| [430](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100436196/202609/3100436196_1790662801480_641ed8f2.jpg) | 3100436196_1790662801480_641ed8f2.jpg | 11.0 | **5100.0** | 100×1 + 5000×1 |
| [431](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100436196/202609/3100436196_1790663110751_17fc3942.jpg) | 3100436196_1790663110751_17fc3942.jpg | 11.0 | **5100.0** | 100×1 + 5000×1 |
| [432](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100436365/202609/3100436365_1790323296890_155aa8ba.jpg) | 3100436365_1790323296890_155aa8ba.jpg | 5.0 | **5000.0** | 5000×1 |
| [433](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100436365/202609/3100436365_1790323661472_c111942f.jpg) | 3100436365_1790323661472_c111942f.jpg | 5.0 | **5000.0** | 5000×1 |
| [436](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100436754/202609/3100436754_1790598081938_8875e5d1.jpg) | 3100436754_1790598081938_8875e5d1.jpg | 5.0 | **5500.0** | 500×1 + 5000×1 |
| [437](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100436754/202609/3100436754_1790598885555_c3bcf16c.jpg) | 3100436754_1790598885555_c3bcf16c.jpg | 5.0 | **5500.0** | 500×1 + 5000×1 |
| [449](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437392/202610/3100437392_1791787934595_f816fd44.jpg) | 3100437392_1791787934595_f816fd44.jpg | 8.3 | **8300.0** | 100×3 + 1000×3 + 5000×1 |
| [450](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437392/202610/3100437392_1791787967889_cceee368.jpg) | 3100437392_1791787967889_cceee368.jpg | 8.3 | **8300.0** | 100×3 + 1000×3 + 5000×1 |
| [458](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100438861/202610/3100438861_1790923112739_23d43da1.jpg) | 3100438861_1790923112739_23d43da1.jpg | 1.0 | **5500.0** | 500×1 + 5000×1 |
| [459](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100438924/202610/3100438924_1790923028436_1650f497.jpg) | 3100438924_1790923028436_1650f497.jpg | 2.0 | **2000.0** | 500×2 + 1000×1 |
| [464](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100439579/202610/3100439579_1790837287339_23f68844.jpg) | 3100439579_1790837287339_23f68844.jpg | 5.0 | **5000.0** | 5000×1 |
| [466](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100440412/202610/3100440412_1791189058919_bd0b4411.jpg) | 3100440412_1791189058919_bd0b4411.jpg | 5.1 | **5600.0** | 100×1 + 500×1 + 5000×1 |
| [475](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100441789/202610/3100441789_1791188502641_dead9d6e.jpg) | 3100441789_1791188502641_dead9d6e.jpg | 5.0 | **5000.0** | 500×2 + 1000×4 |
| [477](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100442163/202610/3100442163_1791189458402_e2a0a5ab.jpg) | 3100442163_1791189458402_e2a0a5ab.jpg | 11.0 | **5050.0** | 50×1 + 5000×1 |
| [478](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100442681/202610/3100442681_1791188260567_6e9ea31c.jpg) | 3100442681_1791188260567_6e9ea31c.jpg | 5.0 | **5000.0** | 5000×1 |
| [488](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100444298/202610/3100444298_1791703193387_bcb3b0ea.jpg) | 3100444298_1791703193387_bcb3b0ea.jpg | 8.0 | **5000.0** | 5000×1 |
| [489](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100444474/202610/3100444474_1791645072922_f20e7195.jpg) | 3100444474_1791645072922_f20e7195.jpg | 1.0 | **5000.0** | 5000×1 |
| [490](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100444848/202610/3100444848_1791805270316_65103362.jpg) | 3100444848_1791805270316_65103362.jpg | 1.0 | **5000.0** | 5000×1 |
| [491](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100444848/202610/3100444848_1791805642884_0e723d7e.jpg) | 3100444848_1791805642884_0e723d7e.jpg | 1.0 | **5000.0** | 5000×1 |
| [492](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100444848/202610/3100444848_1791805642901_291fb514.jpg) | 3100444848_1791805642901_291fb514.jpg | 1.0 | **5000.0** | 5000×1 |
| [493](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100444848/202610/3100444848_1791805642916_1551edb5.jpg) | 3100444848_1791805642916_1551edb5.jpg | 1.0 | **5000.0** | 5000×1 |
| [494](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100444848/202610/3100444848_1791805642933_f290f67e.jpg) | 3100444848_1791805642933_f290f67e.jpg | 1.0 | **5000.0** | 5000×1 |
| [495](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100444848/202610/3100444848_1791805642934_17d31d72.jpg) | 3100444848_1791805642934_17d31d72.jpg | 1.0 | **5000.0** | 5000×1 |
| [499](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100445414/202610/3100445414_1791868066511_1adec2ad.jpg) | 3100445414_1791868066511_1adec2ad.jpg | 1.0 | **5000.0** | 5000×1 |
| [500](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100445414/202610/3100445414_1791868921766_835586cb.jpg) | 3100445414_1791868921766_835586cb.jpg | 1.0 | **5000.0** | 5000×1 |
| [501](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100445414/202610/3100445414_1791869323940_571c524c.jpg) | 3100445414_1791869323940_571c524c.jpg | 1.0 | **5000.0** | 5000×1 |
| [502](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100446125/202610/3100446125_1791803370240_58a5d4c9.jpg) | 3100446125_1791803370240_58a5d4c9.jpg | 1.0 | **5000.0** | 1000×5 |

## 二、日期错误 (5条)

**问题**: 日期年份被错误解析（如 2613、1971、2611、1112）。

**原因**: 日期格式 DD/MM/YY 解析时年日颠倒，或从其他位置误取数字。


| idx | 图片 | OCR datetime | 正确日期(推测) | 说明 |
|-----|------|-------------|---------------|------|
| [96](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410218/202608/3100410218_1786608092352_5e6f4120.jpg) | 3100410218_1786608092352_5e6f4120.jpg | 2613-08-13T00:00:00 | 需验证 | 年份异常 |
| [97](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410218/202608/3100410218_1786609287305_03776bce.jpg) | 3100410218_1786609287305_03776bce.jpg | 2613-08-13T00:00:00 | 需验证 | 年份异常 |
| [452](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100438127/202610/3100438127_1791357920842_fbf52878.jpg) | 3100438127_1791357920842_fbf52878.jpg | 1971-10-26T02:39:00 | 需验证 | 年份异常 |
| [460](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100439015/202610/3100439015_1790923576656_f2c0ff14.jpg) | 3100439015_1790923576656_f2c0ff14.jpg | 2611-10-02T00:00:00 | 需验证 | 年份异常 |
| [496](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100444878/202610/3100444878_1791700448062_ea12656f.jpg) | 3100444878_1791700448062_ea12656f.jpg | 1112-10-26T00:00:00 | 需验证 | 年份异常 |

## 三、明细加总 ≠ 金额 且 金额≥100 (286条)

**经验判断** (基于抽样验证): 此类中 **amount 通常是正确的**，错误在明细：

- 幻影行（多识别了不存在的面额行）

- 数量错误（如 500×1 读成 500×4）

- 面额误读（如 5000 读成 10000）


**但也有例外**（如 idx 30，amount 和明细都错），建议逐条验证。


### 3.1 明细加总 > 金额 (150条)

明细偏大，通常是幻影行或数量偏大。金额大概率正确。


| idx | 图片 | amount | 明细加总 | 差异 | 明细 |
|-----|------|--------|---------|------|------|
| [0](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406356/202608/3100406356_1788165283908_a9d429e8.jpg) | 3100406356_1788165283908_a9d429e8.jpg | 6600.0 | 36600.0 | +30000.0 | 100×1 + 500×1 + 1000×1 + 5000×7 |
| [1](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406369/202607/3100406369_1784275986552_be8e9e0c.jpg) | 3100406369_1784275986552_be8e9e0c.jpg | 5000.0 | 5050.0 | +50.0 | 50×1 + 5000×1 |
| [2](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406369/202607/3100406369_1784275401219_53def1cb.jpg) | 3100406369_1784275401219_53def1cb.jpg | 5000.0 | 5050.0 | +50.0 | 50×1 + 5000×1 |
| [3](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406369/202607/3100406369_1784860038396_010d62dd.jpg) | 3100406369_1784860038396_010d62dd.jpg | 5000.0 | 5050.0 | +50.0 | 50×1 + 5000×1 |
| [4](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406369/202607/3100406369_1784860038404_c2e2efae.jpg) | 3100406369_1784860038404_c2e2efae.jpg | 5000.0 | 5050.0 | +50.0 | 50×1 + 5000×1 |
| [20](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406846/202609/3100406846_1789971330587_b0bd14a7.jpg) | 3100406846_1789971330587_b0bd14a7.jpg | 6900.0 | 8400.0 | +1500.0 | 100×4 + 500×4 + 1000×1 + 5000×1 |
| [24](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406846/202609/3100406846_1789452753448_b97aa6ff.jpg) | 3100406846_1789452753448_b97aa6ff.jpg | 5000.0 | 5100.0 | +100.0 | 50×2 + 500×2 + 1000×4 |
| [25](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406846/202609/3100406846_1789455962531_f69ee1f3.jpg) | 3100406846_1789455962531_f69ee1f3.jpg | 5000.0 | 5100.0 | +100.0 | 50×2 + 500×2 + 1000×4 |
| [26](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406871/202607/3100406871_1784901444010_cdaaf5d2.jpg) | 3100406871_1784901444010_cdaaf5d2.jpg | 5000.0 | 5050.0 | +50.0 | 50×1 + 5000×1 |
| [30](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407388/202607/3100407388_1785482886907_b375698f.jpg) | 3100407388_1785482886907_b375698f.jpg | 1000.0 | 13300.0 | +12300.0 | 100×3 + 1000×3 + 10000×1 |
| [36](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407538/202608/3100407538_1785667320393_4a1ede02.jpg) | 3100407538_1785667320393_4a1ede02.jpg | 700.0 | 12800.0 | +12100.0 | 100×3 + 500×3 + 5000×2 + 1000×1 |
| [37](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407581/202608/3100407581_1788197759081_719144a8.jpg) | 3100407581_1788197759081_719144a8.jpg | 13700.0 | 33700.0 | +20000.0 | 100×7 + 500×2 + 1000×22 + 5000×2 |
| [38](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407581/202608/3100407581_1788197815788_6a1107df.jpg) | 3100407581_1788197815788_6a1107df.jpg | 13700.0 | 33700.0 | +20000.0 | 100×7 + 500×2 + 1000×22 + 5000×2 |
| [43](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407731/202608/3100407731_1786501871856_72f2b83b.jpg) | 3100407731_1786501871856_72f2b83b.jpg | 10000.0 | 20000.0 | +10000.0 | 500×8 + 1000×1 + 10000×1 + 5000×1 |
| [44](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407731/202608/3100407731_1786501916511_80fc36b7.jpg) | 3100407731_1786501916511_80fc36b7.jpg | 10000.0 | 20000.0 | +10000.0 | 500×8 + 1000×1 + 10000×1 + 5000×1 |
| [45](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407731/202608/3100407731_1786501995031_0ae86cf9.jpg) | 3100407731_1786501995031_0ae86cf9.jpg | 10000.0 | 20000.0 | +10000.0 | 500×8 + 1000×1 + 10000×1 + 5000×1 |
| [46](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407731/202608/3100407731_1786507587587_c92744ed.jpg) | 3100407731_1786507587587_c92744ed.jpg | 10000.0 | 20000.0 | +10000.0 | 500×8 + 1000×1 + 10000×1 + 5000×1 |
| [51](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407769/202607/3100407769_1785420891975_5b1631dd.jpg) | 3100407769_1785420891975_5b1631dd.jpg | 5000.0 | 5050.0 | +50.0 | 5000×1 + 50×1 |
| [52](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407769/202607/3100407769_1785420909889_2b313991.jpg) | 3100407769_1785420909889_2b313991.jpg | 5000.0 | 5050.0 | +50.0 | 5000×1 + 50×1 |
| [59](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408300/202608/3100408300_1785851659503_806df019.jpg) | 3100408300_1785851659503_806df019.jpg | 5000.0 | 5050.0 | +50.0 | 50×1 + 5000×1 |
| [60](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408300/202608/3100408300_1785893654097_0e2ee5e7.jpg) | 3100408300_1785893654097_0e2ee5e7.jpg | 5000.0 | 5050.0 | +50.0 | 50×1 + 5000×1 |
| [67](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408680/202608/3100408680_1787197539865_ae150a99.jpg) | 3100408680_1787197539865_ae150a99.jpg | 9900.0 | 11400.0 | +1500.0 | 100×4 + 500×4 + 1000×4 + 5000×1 |
| [69](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408680/202608/3100408680_1787197550663_3e308843.jpg) | 3100408680_1787197550663_3e308843.jpg | 9900.0 | 11400.0 | +1500.0 | 100×4 + 500×4 + 1000×4 + 5000×1 |
| [106](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410287/202608/3100410287_1786266214584_3a1c6bfd.jpg) | 3100410287_1786266214584_3a1c6bfd.jpg | 5000.0 | 5500.0 | +500.0 | 500×1 + 5000×1 |
| [109](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410660/202608/3100410660_1788172265053_d8ecf364.jpg) | 3100410660_1788172265053_d8ecf364.jpg | 8700.0 | 17200.0 | +8500.0 | 100×2 + 500×2 + 1000×1 + 5000×3 |
| [115](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410687/202610/3100410687_1791174406152_d265afa0.jpg) | 3100410687_1791174406152_d265afa0.jpg | 9200.0 | 22200.0 | +13000.0 | 100×2 + 1000×2 + 5000×4 |
| [116](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410876/202608/3100410876_1786516927225_26ed6153.jpg) | 3100410876_1786516927225_26ed6153.jpg | 5000.0 | 35000.0 | +30000.0 | 5000×7 |
| [117](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410876/202608/3100410876_1786517019634_261cd0c4.jpg) | 3100410876_1786517019634_261cd0c4.jpg | 5000.0 | 35000.0 | +30000.0 | 5000×7 |
| [118](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410993/202608/3100410993_1787344211299_bcf7e5cf.jpg) | 3100410993_1787344211299_bcf7e5cf.jpg | 700.0 | 6700.0 | +6000.0 | 100×2 + 1000×1 + 500×1 + 5000×1 |
| [137](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412015/202609/3100412015_1790134034565_be0af20e.jpg) | 3100412015_1790134034565_be0af20e.jpg | 5000.0 | 11000.0 | +6000.0 | 5000×2 + 500×2 |
| [138](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412015/202609/3100412015_1790134068357_20f7b4ce.jpg) | 3100412015_1790134068357_20f7b4ce.jpg | 5000.0 | 11000.0 | +6000.0 | 5000×2 + 500×2 |
| [139](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412015/202609/3100412015_1790134904866_21a3e980.jpg) | 3100412015_1790134904866_21a3e980.jpg | 5000.0 | 11000.0 | +6000.0 | 5000×2 + 500×2 |
| [140](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412015/202609/3100412015_1790135349799_4979c311.jpg) | 3100412015_1790135349799_4979c311.jpg | 5000.0 | 11000.0 | +6000.0 | 5000×2 + 500×2 |
| [144](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412197/202608/3100412197_1787823210166_0905a430.jpg) | 3100412197_1787823210166_0905a430.jpg | 8300.0 | 18300.0 | +10000.0 | 100×3 + 1000×3 + 5000×3 |
| [145](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412197/202608/3100412197_1787826020994_ea6277ba.jpg) | 3100412197_1787826020994_ea6277ba.jpg | 8300.0 | 18300.0 | +10000.0 | 100×3 + 1000×3 + 5000×3 |
| [152](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412887/202609/3100412887_1790743117217_379a75d1.jpg) | 3100412887_1790743117217_379a75d1.jpg | 5300.0 | 6300.0 | +1000.0 | 100×3 + 500×4 + 1000×4 |
| [153](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412887/202609/3100412887_1790743073884_7121447e.jpg) | 3100412887_1790743073884_7121447e.jpg | 5300.0 | 6300.0 | +1000.0 | 100×3 + 500×4 + 1000×4 |
| [156](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412887/202609/3100412887_1790743232935_a71a2940.jpg) | 3100412887_1790743232935_a71a2940.jpg | 5300.0 | 6300.0 | +1000.0 | 100×3 + 500×4 + 1000×4 |
| [157](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412887/202609/3100412887_1790744053101_2c75d9eb.jpg) | 3100412887_1790744053101_2c75d9eb.jpg | 5300.0 | 6300.0 | +1000.0 | 100×3 + 500×4 + 1000×4 |
| [159](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412887/202609/3100412887_1790744047774_0afebd00.jpg) | 3100412887_1790744047774_0afebd00.jpg | 5300.0 | 6300.0 | +1000.0 | 100×3 + 500×4 + 1000×4 |
| [167](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100413380/202609/3100413380_1788605110746_d922663b.jpg) | 3100413380_1788605110746_d922663b.jpg | 8600.0 | 9600.0 | +1000.0 | 100×1 + 500×3 + 1000×3 + 5000×1 |
| [168](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100413380/202608/3100413380_1787997200868_4b6dee9e.jpg) | 3100413380_1787997200868_4b6dee9e.jpg | 7200.0 | 12200.0 | +5000.0 | 100×2 + 1000×2 + 5000×2 |
| [169](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100413380/202608/3100413380_1787998935717_8596aefe.jpg) | 3100413380_1787998935717_8596aefe.jpg | 7200.0 | 12200.0 | +5000.0 | 100×2 + 1000×2 + 5000×2 |
| [195](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416115/202608/3100416115_1787119099503_a192ad71.jpg) | 3100416115_1787119099503_a192ad71.jpg | 5000.0 | 5050.0 | +50.0 | 50×1 + 5000×1 |
| [198](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416446/202608/3100416446_1787058081732_93ead997.jpg) | 3100416446_1787058081732_93ead997.jpg | 5000.0 | 5050.0 | +50.0 | 50×1 + 5000×1 |
| [199](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416446/202608/3100416446_1787058891836_105578b5.jpg) | 3100416446_1787058891836_105578b5.jpg | 5000.0 | 5050.0 | +50.0 | 50×1 + 5000×1 |
| [209](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416976/202609/3100416976_1788489756804_b57dfff7.jpg) | 3100416976_1788489756804_b57dfff7.jpg | 151.0 | 5250.0 | +5099.0 | 100×1 + 50×3 + 5000×1 |
| [211](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416976/202609/3100416976_1788485996121_7dac0237.jpg) | 3100416976_1788485996121_7dac0237.jpg | 100.0 | 5100.0 | +5000.0 | 100×1 + 5000×1 |
| [212](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416976/202609/3100416976_1788486345697_38e58f55.jpg) | 3100416976_1788486345697_38e58f55.jpg | 100.0 | 5100.0 | +5000.0 | 100×1 + 5000×1 |
| [213](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416976/202609/3100416976_1788488542730_d6547097.jpg) | 3100416976_1788488542730_d6547097.jpg | 100.0 | 5100.0 | +5000.0 | 100×1 + 5000×1 |
| [214](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417414/202609/3100417414_1788487122965_b037e862.jpg) | 3100417414_1788487122965_b037e862.jpg | 7000.0 | 8000.0 | +1000.0 | 1000×2 + 500×2 + 5000×1 |
| [224](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417414/202609/3100417414_1789963408249_f821c578.jpg) | 3100417414_1789963408249_f821c578.jpg | 13300.0 | 18300.0 | +5000.0 | 100×3 + 1000×3 + 5000×3 |
| [225](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417414/202609/3100417414_1789963426189_85aaccda.jpg) | 3100417414_1789963426189_85aaccda.jpg | 13300.0 | 18300.0 | +5000.0 | 100×3 + 1000×3 + 5000×3 |
| [226](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100417414/202609/3100417414_1789968306866_ba528394.jpg) | 3100417414_1789968306866_ba528394.jpg | 13300.0 | 18300.0 | +5000.0 | 100×3 + 1000×3 + 5000×3 |
| [228](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418015/202609/3100418015_1788594920739_a2252240.jpg) | 3100418015_1788594920739_a2252240.jpg | 6000.0 | 6100.0 | +100.0 | 1000×1 + 100×1 + 5000×1 |
| [229](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418015/202609/3100418015_1788594957488_ef65f792.jpg) | 3100418015_1788594957488_ef65f792.jpg | 6000.0 | 6100.0 | +100.0 | 1000×1 + 100×1 + 5000×1 |
| [230](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418015/202609/3100418015_1788608561861_f2a68f97.jpg) | 3100418015_1788608561861_f2a68f97.jpg | 6000.0 | 6100.0 | +100.0 | 1000×1 + 100×1 + 5000×1 |
| [244](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100419687/202608/3100419687_1788010350967_034a231e.jpg) | 3100419687_1788010350967_034a231e.jpg | 5200.0 | 10200.0 | +5000.0 | 100×2 + 5000×2 |
| [245](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100419687/202608/3100419687_1788008381621_a18fc868.jpg) | 3100419687_1788008381621_a18fc868.jpg | 5200.0 | 10200.0 | +5000.0 | 100×2 + 5000×2 |
| [247](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100419813/202609/3100419813_1788272381435_6e231ad0.jpg) | 3100419813_1788272381435_6e231ad0.jpg | 6300.0 | 8300.0 | +2000.0 | 100×3 + 1000×3 + 5000×1 |
| [248](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100419952/202609/3100419952_1788745793610_aee8883a.jpg) | 3100419952_1788745793610_aee8883a.jpg | 8700.0 | 9200.0 | +500.0 | 100×2 + 500×2 + 1000×3 + 5000×1 |
| [249](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100419952/202609/3100419952_1788745931739_52f5614a.jpg) | 3100419952_1788745931739_52f5614a.jpg | 8700.0 | 9200.0 | +500.0 | 100×2 + 500×2 + 1000×3 + 5000×1 |
| [256](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421138/202608/3100421138_1787817010295_6a674352.jpg) | 3100421138_1787817010295_6a674352.jpg | 5000.0 | 6000.0 | +1000.0 | 500×4 + 1000×4 |
| [257](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421140/202609/3100421140_1788887111321_8c8af4bf.jpg) | 3100421140_1788887111321_8c8af4bf.jpg | 1000.0 | 16700.0 | +15700.0 | 100×2 + 500×1 + 1000×1 + 5000×3 |
| [258](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421140/202609/3100421140_1788887142561_3c969722.jpg) | 3100421140_1788887142561_3c969722.jpg | 1000.0 | 16700.0 | +15700.0 | 100×2 + 500×1 + 1000×1 + 5000×3 |
| [259](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421140/202609/3100421140_1788914893274_809262a6.jpg) | 3100421140_1788914893274_809262a6.jpg | 1000.0 | 16700.0 | +15700.0 | 100×2 + 500×1 + 1000×1 + 5000×3 |
| [260](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421140/202609/3100421140_1788920053307_a8571ba0.jpg) | 3100421140_1788920053307_a8571ba0.jpg | 1000.0 | 16700.0 | +15700.0 | 100×2 + 500×1 + 1000×1 + 5000×3 |
| [261](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421138/202609/3100421138_1788334130255_2d6a94f7.jpg) | 3100421138_1788334130255_2d6a94f7.jpg | 6600.0 | 15600.0 | +9000.0 | 100×1 + 500×1 + 5000×3 |
| [269](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421323/202609/3100421323_1788429044062_454b203b.jpg) | 3100421323_1788429044062_454b203b.jpg | 5200.0 | 25200.0 | +20000.0 | 100×2 + 500×2 + 1000×24 |
| [274](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421830/202609/3100421830_1788429683155_90cbad16.jpg) | 3100421830_1788429683155_90cbad16.jpg | 2000.0 | 3000.0 | +1000.0 | 500×2 + 1000×2 |
| [275](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100422035/202608/3100422035_1788177160793_fbdcf78b.jpg) | 3100422035_1788177160793_fbdcf78b.jpg | 6300.0 | 8300.0 | +2000.0 | 100×3 + 1000×3 + 5000×1 |
| [276](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100422035/202608/3100422035_1788177163270_1b71b55e.jpg) | 3100422035_1788177163270_1b71b55e.jpg | 6300.0 | 8300.0 | +2000.0 | 100×3 + 1000×3 + 5000×1 |
| [277](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100422035/202608/3100422035_1788181527580_39c86266.jpg) | 3100422035_1788181527580_39c86266.jpg | 6300.0 | 8300.0 | +2000.0 | 100×3 + 1000×3 + 5000×1 |
| [278](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100422035/202609/3100422035_1788232646007_bbc48035.jpg) | 3100422035_1788232646007_bbc48035.jpg | 6300.0 | 8300.0 | +2000.0 | 100×3 + 1000×3 + 5000×1 |
| [280](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423079/202609/3100423079_1789207367832_d1b4cb5d.jpg) | 3100423079_1789207367832_d1b4cb5d.jpg | 5000.0 | 5050.0 | +50.0 | 50×1 + 5000×1 |
| [298](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100425033/202609/3100425033_1788597183405_5069e023.jpg) | 3100425033_1788597183405_5069e023.jpg | 5000.0 | 5050.0 | +50.0 | 5000×1 + 50×1 |
| [299](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100425033/202609/3100425033_1788597843077_c328e61c.jpg) | 3100425033_1788597843077_c328e61c.jpg | 5000.0 | 5050.0 | +50.0 | 5000×1 + 50×1 |
| [301](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100425192/202609/3100425192_1789058111328_c5db91ce.jpg) | 3100425192_1789058111328_c5db91ce.jpg | 6000.0 | 9000.0 | +3000.0 | 500×6 + 1000×6 |
| [302](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100425192/202609/3100425192_1789092481852_b176d5f0.jpg) | 3100425192_1789092481852_b176d5f0.jpg | 6000.0 | 9000.0 | +3000.0 | 500×6 + 1000×6 |
| [303](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100425192/202609/3100425192_1789095043479_a96cbeb6.jpg) | 3100425192_1789095043479_a96cbeb6.jpg | 6000.0 | 9000.0 | +3000.0 | 500×6 + 1000×6 |
| [308](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100426160/202609/3100426160_1790576148349_f692a750.jpg) | 3100426160_1790576148349_f692a750.jpg | 8700.0 | 16700.0 | +8000.0 | 100×2 + 500×1 + 1000×1 + 5000×3 |
| [309](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100426160/202609/3100426160_1790575165027_806c4240.jpg) | 3100426160_1790575165027_806c4240.jpg | 8700.0 | 18700.0 | +10000.0 | 100×2 + 500×1 + 1000×3 + 5000×3 |
| [310](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100426160/202609/3100426160_1790576485229_7e9610f8.jpg) | 3100426160_1790576485229_7e9610f8.jpg | 8700.0 | 16700.0 | +8000.0 | 100×2 + 500×1 + 1000×1 + 5000×3 |
| [311](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100426160/202609/3100426160_1790575832174_9573b3c7.jpg) | 3100426160_1790575832174_9573b3c7.jpg | 8700.0 | 18700.0 | +10000.0 | 100×2 + 500×1 + 1000×3 + 5000×3 |
| [312](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100426160/202609/3100426160_1790579216080_00ba6d58.jpg) | 3100426160_1790579216080_00ba6d58.jpg | 8700.0 | 16700.0 | +8000.0 | 100×2 + 500×1 + 1000×1 + 5000×3 |
| [316](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100427332/202609/3100427332_1788862307164_e248f6a5.jpg) | 3100427332_1788862307164_e248f6a5.jpg | 10000.0 | 18000.0 | +8000.0 | 100×5 + 500×5 + 1000×5 + 5000×2 |
| [318](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100427810/202610/3100427810_1791812220724_0b9a59d6.jpg) | 3100427810_1791812220724_0b9a59d6.jpg | 5000.0 | 9000.0 | +4000.0 | 500×6 + 1000×6 |
| [319](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100427810/202610/3100427810_1791812245482_621b9570.jpg) | 3100427810_1791812245482_621b9570.jpg | 5000.0 | 9000.0 | +4000.0 | 500×6 + 1000×6 |
| [323](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100428040/202610/3100428040_1791546840090_e4d4a497.jpg) | 3100428040_1791546840090_e4d4a497.jpg | 15200.0 | 127200.0 | +112000.0 | 100×2 + 1000×2 + 5000×25 |
| [336](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100430269/202610/3100430269_1791883068332_257dc0e1.jpg) | 3100430269_1791883068332_257dc0e1.jpg | 8600.0 | 17600.0 | +9000.0 | 100×1 + 10000×1 + 500×3 + 1000×1 + 5000×1 |
| [337](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100430395/202609/3100430395_1789940652574_a0da53d6.jpg) | 3100430395_1789940652574_a0da53d6.jpg | 5200.0 | 10200.0 | +5000.0 | 100×2 + 5000×2 |
| [338](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100431019/202610/3100431019_1791859642107_7d756317.jpg) | 3100431019_1791859642107_7d756317.jpg | 10000.0 | 30000.0 | +20000.0 | 1000×5 + 5000×5 |
| [340](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100431305/202609/3100431305_1790406531014_2a6e95ea.jpg) | 3100431305_1790406531014_2a6e95ea.jpg | 5300.0 | 5800.0 | +500.0 | 100×3 + 500×1 + 5000×1 |
| [341](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100431866/202610/3100431866_1791010324177_a4b45ff5.jpg) | 3100431866_1791010324177_a4b45ff5.jpg | 9100.0 | 24100.0 | +15000.0 | 100×1 + 1000×4 + 5000×4 |
| [343](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100431866/202610/3100431866_1791618330413_44f3f000.jpg) | 3100431866_1791618330413_44f3f000.jpg | 13100.0 | 1113100.0 | +1100000.0 | 100×1 + 500×2 + 1000×2 + 5000×222 |
| [347](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100432164/202610/3100432164_1791192080740_9a0bd466.jpg) | 3100432164_1791192080740_9a0bd466.jpg | 6200.0 | 7200.0 | +1000.0 | 100×2 + 1000×2 + 5000×1 |
| [348](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100432950/202609/3100432950_1790662552895_38e38dd3.jpg) | 3100432950_1790662552895_38e38dd3.jpg | 5000.0 | 6000.0 | +1000.0 | 100×5 + 500×5 + 1000×3 |
| [349](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100432789/202610/3100432789_1791020511696_e17d9558.jpg) | 3100432789_1791020511696_e17d9558.jpg | 7000.0 | 8000.0 | +1000.0 | 500×2 + 1000×2 + 5000×1 |
| [350](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433289/202610/3100433289_1790832705958_2328dcc3.jpg) | 3100433289_1790832705958_2328dcc3.jpg | 8000.0 | 18000.0 | +10000.0 | 1000×3 + 5000×3 |
| [354](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433317/202609/3100433317_1790479064644_230b5557.jpg) | 3100433317_1790479064644_230b5557.jpg | 7300.0 | 13300.0 | +6000.0 | 100×3 + 1000×3 + 5000×2 |
| [355](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433317/202609/3100433317_1790481561016_5c920532.jpg) | 3100433317_1790481561016_5c920532.jpg | 7300.0 | 13300.0 | +6000.0 | 100×3 + 1000×3 + 5000×2 |
| [368](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433519/202610/3100433519_1791693788700_1e49315a.jpg) | 3100433519_1791693788700_1e49315a.jpg | 1000.0 | 7500.0 | +6500.0 | 500×1 + 1000×7 |
| [369](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433578/202609/3100433578_1790306901654_bcaebcb1.jpg) | 3100433578_1790306901654_bcaebcb1.jpg | 5200.0 | 10200.0 | +5000.0 | 100×2 + 5000×2 |
| [370](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433578/202609/3100433578_1790307030446_f524397b.jpg) | 3100433578_1790307030446_f524397b.jpg | 5200.0 | 10200.0 | +5000.0 | 100×2 + 5000×2 |
| [371](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433578/202609/3100433578_1790308715012_8f7dfb6d.jpg) | 3100433578_1790308715012_8f7dfb6d.jpg | 5200.0 | 10200.0 | +5000.0 | 100×2 + 5000×2 |
| [372](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433908/202609/3100433908_1790398421433_52126f1d.jpg) | 3100433908_1790398421433_52126f1d.jpg | 5200.0 | 5700.0 | +500.0 | 100×2 + 500×1 + 5000×1 |
| [373](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433908/202609/3100433908_1790399377445_da32a310.jpg) | 3100433908_1790399377445_da32a310.jpg | 5200.0 | 5700.0 | +500.0 | 100×2 + 500×1 + 5000×1 |
| [374](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433908/202609/3100433908_1790399460490_6fb253c7.jpg) | 3100433908_1790399460490_6fb253c7.jpg | 5200.0 | 5700.0 | +500.0 | 100×2 + 500×1 + 5000×1 |
| [375](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433908/202609/3100433908_1790401525692_e0db88d1.jpg) | 3100433908_1790401525692_e0db88d1.jpg | 5200.0 | 5700.0 | +500.0 | 100×2 + 500×1 + 5000×1 |
| [376](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433908/202609/3100433908_1790404224596_f2ae3162.jpg) | 3100433908_1790404224596_f2ae3162.jpg | 5200.0 | 5700.0 | +500.0 | 100×2 + 500×1 + 5000×1 |
| [381](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434000/202610/3100434000_1791538119107_b66d1d9e.jpg) | 3100434000_1791538119107_b66d1d9e.jpg | 8100.0 | 12600.0 | +4500.0 | 100×1 + 500×1 + 1000×2 + 5000×2 |
| [387](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434545/202610/3100434545_1791884250304_5aad2025.jpg) | 3100434545_1791884250304_5aad2025.jpg | 6000.0 | 11000.0 | +5000.0 | 500×2 + 5000×2 |
| [388](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434390/202609/3100434390_1790673488783_4ed1fb1e.jpg) | 3100434390_1790673488783_4ed1fb1e.jpg | 6000.0 | 12000.0 | +6000.0 | 1000×7 + 5000×1 |
| [391](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434924/202610/3100434924_1791011500420_79567a11.jpg) | 3100434924_1791011500420_79567a11.jpg | 6200.0 | 7200.0 | +1000.0 | 100×2 + 1000×2 + 5000×1 |
| [392](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434924/202610/3100434924_1791012011638_baa93c34.jpg) | 3100434924_1791012011638_baa93c34.jpg | 6200.0 | 7200.0 | +1000.0 | 100×2 + 1000×2 + 5000×1 |
| [399](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435101/202610/3100435101_1790837330890_7acb8ba6.jpg) | 3100435101_1790837330890_7acb8ba6.jpg | 5400.0 | 20400.0 | +15000.0 | 100×4 + 5000×4 |
| [400](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435101/202610/3100435101_1790841074586_6341b6f0.jpg) | 3100435101_1790841074586_6341b6f0.jpg | 5400.0 | 20400.0 | +15000.0 | 100×4 + 5000×4 |
| [419](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435395/202610/3100435395_1791443919527_a75f6ccc.jpg) | 3100435395_1791443919527_a75f6ccc.jpg | 5200.0 | 10200.0 | +5000.0 | 100×2 + 5000×2 |
| [420](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435653/202610/3100435653_1790849537059_c163732e.jpg) | 3100435653_1790849537059_c163732e.jpg | 5300.0 | 6300.0 | +1000.0 | 100×3 + 1000×4 + 500×4 |
| [421](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435653/202610/3100435653_1790848757575_6d392f12.jpg) | 3100435653_1790848757575_6d392f12.jpg | 5300.0 | 6300.0 | +1000.0 | 100×3 + 1000×4 + 500×4 |
| [422](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435653/202610/3100435653_1791264562541_8add0c78.jpg) | 3100435653_1791264562541_8add0c78.jpg | 6400.0 | 9400.0 | +3000.0 | 100×4 + 500×6 + 1000×6 |
| [423](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435653/202610/3100435653_1791265244953_e8e2164c.jpg) | 3100435653_1791265244953_e8e2164c.jpg | 6400.0 | 9400.0 | +3000.0 | 100×4 + 500×6 + 1000×6 |
| [427](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435681/202609/3100435681_1790326088878_06b22acb.jpg) | 3100435681_1790326088878_06b22acb.jpg | 1117.0 | 5000.0 | +3883.0 | 5000×1 |
| [428](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435974/202609/3100435974_1790317732251_00f92401.jpg) | 3100435974_1790317732251_00f92401.jpg | 5000.0 | 9000.0 | +4000.0 | 1000×9 |
| [440](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437078/202609/3100437078_1790500978904_1c5e3f5e.jpg) | 3100437078_1790500978904_1c5e3f5e.jpg | 5000.0 | 5050.0 | +50.0 | 5000×1 + 50×1 |
| [441](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437207/202609/3100437207_1790511764448_6057b03d.jpg) | 3100437207_1790511764448_6057b03d.jpg | 5000.0 | 35000.0 | +30000.0 | 5000×7 |
| [442](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437078/202609/3100437078_1790501793168_3ab08747.jpg) | 3100437078_1790501793168_3ab08747.jpg | 5000.0 | 5050.0 | +50.0 | 5000×1 + 50×1 |
| [443](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437207/202609/3100437207_1790511749111_88cde683.jpg) | 3100437207_1790511749111_88cde683.jpg | 5000.0 | 35000.0 | +30000.0 | 5000×7 |
| [446](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437253/202610/3100437253_1791902324699_dd48a9fb.jpg) | 3100437253_1791902324699_dd48a9fb.jpg | 5300.0 | 15300.0 | +10000.0 | 100×3 + 5000×3 |
| [447](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437253/202610/3100437253_1791950279437_cd24ca47.jpg) | 3100437253_1791950279437_cd24ca47.jpg | 5300.0 | 15300.0 | +10000.0 | 100×3 + 5000×3 |
| [451](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437900/202610/3100437900_1791200785922_b193b814.jpg) | 3100437900_1791200785922_b193b814.jpg | 5300.0 | 30100.0 | +24800.0 | 10000×3 + 100×1 |
| [453](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100438127/202610/3100438127_1791357936415_0c6c8412.jpg) | 3100438127_1791357936415_0c6c8412.jpg | 33600.0 | 34600.0 | +1000.0 | 100×1 + 500×3 + 1000×3 + 5000×6 |
| [461](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100438926/202610/3100438926_1791881238620_b0d7d2d5.jpg) | 3100438926_1791881238620_b0d7d2d5.jpg | 5300.0 | 15300.0 | +10000.0 | 100×3 + 5000×3 |
| [462](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100439015/202610/3100439015_1791699989593_02c61fac.jpg) | 3100439015_1791699989593_02c61fac.jpg | 5400.0 | 20400.0 | +15000.0 | 100×4 + 5000×4 |
| [463](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100439015/202610/3100439015_1791700052816_00c6b41c.jpg) | 3100439015_1791700052816_00c6b41c.jpg | 5400.0 | 20400.0 | +15000.0 | 100×4 + 5000×4 |
| [465](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100439622/202610/3100439622_1791787654678_b8b32244.jpg) | 3100439622_1791787654678_b8b32244.jpg | 7300.0 | 10200.0 | +2900.0 | 100×32 + 500×2 + 1000×6 |
| [468](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100440463/202610/3100440463_1791628074137_a9526600.jpg) | 3100440463_1791628074137_a9526600.jpg | 5300.0 | 15300.0 | +10000.0 | 100×3 + 5000×3 |
| [469](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100440463/202610/3100440463_1791628309534_e261cadc.jpg) | 3100440463_1791628309534_e261cadc.jpg | 5300.0 | 15300.0 | +10000.0 | 100×3 + 5000×3 |
| [470](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100440610/202610/3100440610_1791091472236_665d510f.jpg) | 3100440610_1791091472236_665d510f.jpg | 5000.0 | 6000.0 | +1000.0 | 100×5 + 500×5 + 1000×3 |
| [471](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100440610/202610/3100440610_1791092771018_4d493c56.jpg) | 3100440610_1791092771018_4d493c56.jpg | 5000.0 | 6000.0 | +1000.0 | 100×5 + 500×5 + 1000×3 |
| [472](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100441581/202610/3100441581_1791516708906_447466c5.jpg) | 3100441581_1791516708906_447466c5.jpg | 5300.0 | 15300.0 | +10000.0 | 100×3 + 5000×3 |
| [473](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100441581/202610/3100441581_1791516674990_33d12909.jpg) | 3100441581_1791516674990_33d12909.jpg | 5300.0 | 15300.0 | +10000.0 | 100×3 + 5000×3 |
| [474](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100441581/202610/3100441581_1791518939159_ab1603de.jpg) | 3100441581_1791518939159_ab1603de.jpg | 5300.0 | 15300.0 | +10000.0 | 100×3 + 5000×3 |
| [476](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100442074/202610/3100442074_1791267179625_1af27505.jpg) | 3100442074_1791267179625_1af27505.jpg | 5000.0 | 5050.0 | +50.0 | 50×1 + 5000×1 |
| [479](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100442297/202610/3100442297_1791279335305_3173f4cd.jpg) | 3100442297_1791279335305_3173f4cd.jpg | 5000.0 | 6000.0 | +1000.0 | 500×4 + 1000×4 |
| [486](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100444076/202610/3100444076_1791564845805_761a05cf.jpg) | 3100444076_1791564845805_761a05cf.jpg | 5000.0 | 5500.0 | +500.0 | 5000×1 + 500×1 |
| [487](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100444076/202610/3100444076_1791602967810_1372cd27.jpg) | 3100444076_1791602967810_1372cd27.jpg | 5000.0 | 5500.0 | +500.0 | 5000×1 + 500×1 |
| [498](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100445451/202610/3100445451_1791793944224_2fc69395.jpg) | 3100445451_1791793944224_2fc69395.jpg | 5300.0 | 15300.0 | +10000.0 | 100×3 + 5000×3 |
| [503](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100446125/202610/3100446125_1791803497526_7f4f37d9.jpg) | 3100446125_1791803497526_7f4f37d9.jpg | 5000.0 | 9000.0 | +4000.0 | 1000×9 |
| [504](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100446125/202610/3100446125_1791803979200_6f11da04.jpg) | 3100446125_1791803979200_6f11da04.jpg | 5000.0 | 9000.0 | +4000.0 | 1000×9 |

### 3.2 金额 > 明细加总 (136条)

明细偏小，通常是行丢失或数量偏小。金额大概率正确。


| idx | 图片 | amount | 明细加总 | 差异 | 明细 |
|-----|------|--------|---------|------|------|
| [5](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406528/202607/3100406528_1785141121454_5d8f4474.jpg) | 3100406528_1785141121454_5d8f4474.jpg | 6000.0 | 3000.0 | -3000.0 | 500×2 + 1000×2 |
| [6](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406640/202607/3100406640_1784296855686_18b43b7d.jpg) | 3100406640_1784296855686_18b43b7d.jpg | 5000.0 | 4300.0 | -700.0 | 2000×1 + 1000×1 + 500×2 + 100×1 + 200×1 |
| [7](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406640/202607/3100406640_1784296872176_8e867377.jpg) | 3100406640_1784296872176_8e867377.jpg | 5000.0 | 4300.0 | -700.0 | 2000×1 + 1000×1 + 500×2 + 100×1 + 200×1 |
| [8](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406640/202607/3100406640_1784296921958_797b08a5.jpg) | 3100406640_1784296921958_797b08a5.jpg | 5000.0 | 4300.0 | -700.0 | 2000×1 + 1000×1 + 500×2 + 100×1 + 200×1 |
| [9](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406640/202607/3100406640_1784298723771_d90da93a.jpg) | 3100406640_1784298723771_d90da93a.jpg | 5000.0 | 4300.0 | -700.0 | 2000×1 + 1000×1 + 500×2 + 100×1 + 200×1 |
| [10](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406640/202607/3100406640_1784311800774_379d03c0.jpg) | 3100406640_1784311800774_379d03c0.jpg | 5000.0 | 4300.0 | -700.0 | 2000×1 + 1000×1 + 500×2 + 100×1 + 200×1 |
| [11](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406640/202607/3100406640_1784326226387_40bd047e.jpg) | 3100406640_1784326226387_40bd047e.jpg | 5000.0 | 4300.0 | -700.0 | 2000×1 + 1000×1 + 500×2 + 100×1 + 200×1 |
| [12](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406640/202607/3100406640_1784860038567_447f6fba.jpg) | 3100406640_1784860038567_447f6fba.jpg | 5000.0 | 4300.0 | -700.0 | 2000×1 + 1000×1 + 500×2 + 100×1 + 200×1 |
| [13](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406640/202607/3100406640_1784860038583_f88a9cb4.jpg) | 3100406640_1784860038583_f88a9cb4.jpg | 5000.0 | 4300.0 | -700.0 | 2000×1 + 1000×1 + 500×2 + 100×1 + 200×1 |
| [14](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406640/202607/3100406640_1784860038702_78cbbc17.jpg) | 3100406640_1784860038702_78cbbc17.jpg | 5000.0 | 4300.0 | -700.0 | 2000×1 + 1000×1 + 500×2 + 100×1 + 200×1 |
| [15](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406640/202607/3100406640_1784860039919_27777010.jpg) | 3100406640_1784860039919_27777010.jpg | 5000.0 | 4300.0 | -700.0 | 2000×1 + 1000×1 + 500×2 + 100×1 + 200×1 |
| [16](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406640/202607/3100406640_1784860040092_f3ff2de0.jpg) | 3100406640_1784860040092_f3ff2de0.jpg | 5000.0 | 4300.0 | -700.0 | 2000×1 + 1000×1 + 500×2 + 100×1 + 200×1 |
| [17](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406640/202607/3100406640_1784860040885_abf3ae2d.jpg) | 3100406640_1784860040885_abf3ae2d.jpg | 5000.0 | 4300.0 | -700.0 | 2000×1 + 1000×1 + 500×2 + 100×1 + 200×1 |
| [31](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407515/202609/3100407515_1788770632309_8e0b75d7.jpg) | 3100407515_1788770632309_8e0b75d7.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [32](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407515/202609/3100407515_1788770591512_c9e8980f.jpg) | 3100407515_1788770591512_c9e8980f.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [33](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407515/202609/3100407515_1788770926981_f239b1fa.jpg) | 3100407515_1788770926981_f239b1fa.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [34](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407515/202609/3100407515_1788772312544_eef08e5e.jpg) | 3100407515_1788772312544_eef08e5e.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [35](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407515/202609/3100407515_1788773922547_0e98fb3f.jpg) | 3100407515_1788773922547_0e98fb3f.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [41](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407731/202608/3100407731_1786096358196_5b28cd01.jpg) | 3100407731_1786096358196_5b28cd01.jpg | 7900.0 | 1900.0 | -6000.0 | 100×4 + 500×1 + 1000×1 |
| [42](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407731/202608/3100407731_1786096939430_bc7b1fa4.jpg) | 3100407731_1786096939430_bc7b1fa4.jpg | 7900.0 | 1900.0 | -6000.0 | 100×4 + 500×1 + 1000×1 |
| [48](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407731/202608/3100407731_1787929905847_f93a02f1.jpg) | 3100407731_1787929905847_f93a02f1.jpg | 1690000.0 | 10600.0 | -1679400.0 | 10000×1 + 100×1 + 500×1 |
| [49](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407731/202608/3100407731_1787929915364_a3243725.jpg) | 3100407731_1787929915364_a3243725.jpg | 1690000.0 | 10600.0 | -1679400.0 | 10000×1 + 100×1 + 500×1 |
| [50](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407731/202608/3100407731_1787932675599_dea2b995.jpg) | 3100407731_1787932675599_dea2b995.jpg | 1690000.0 | 10600.0 | -1679400.0 | 10000×1 + 100×1 + 500×1 |
| [53](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100407799/202608/3100407799_1785817460442_27e5337b.jpg) | 3100407799_1785817460442_27e5337b.jpg | 6300.0 | 3800.0 | -2500.0 | 100×3 + 500×3 + 1000×2 |
| [64](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408680/202608/3100408680_1785825003509_a873f146.jpg) | 3100408680_1785825003509_a873f146.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [65](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408680/202608/3100408680_1785838794598_d0f62904.jpg) | 3100408680_1785838794598_d0f62904.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [66](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408680/202608/3100408680_1786275382557_9093fe0b.jpg) | 3100408680_1786275382557_9093fe0b.jpg | 6900.0 | 6100.0 | -800.0 | 100×1 + 500×4 + 1000×4 |
| [68](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408680/202608/3100408680_1786275411193_d22b944e.jpg) | 3100408680_1786275411193_d22b944e.jpg | 6900.0 | 6100.0 | -800.0 | 100×1 + 500×4 + 1000×4 |
| [70](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408680/202608/3100408680_1786280579500_8c8c6ce2.jpg) | 3100408680_1786280579500_8c8c6ce2.jpg | 6900.0 | 6100.0 | -800.0 | 100×1 + 500×4 + 1000×4 |
| [71](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100408767/202608/3100408767_1785999802378_1027cabe.jpg) | 3100408767_1785999802378_1027cabe.jpg | 4500.0 | 4000.0 | -500.0 | 1000×4 |
| [72](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409092/202608/3100409092_1787994950229_6971e0b0.jpg) | 3100409092_1787994950229_6971e0b0.jpg | 9600.0 | 8100.0 | -1500.0 | 100×1 + 500×4 + 1000×1 + 5000×1 |
| [73](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409092/202608/3100409092_1787994957114_ab58641b.jpg) | 3100409092_1787994957114_ab58641b.jpg | 9600.0 | 8100.0 | -1500.0 | 100×1 + 500×4 + 1000×1 + 5000×1 |
| [74](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409092/202608/3100409092_1787995226913_5147dd1c.jpg) | 3100409092_1787995226913_5147dd1c.jpg | 9600.0 | 8100.0 | -1500.0 | 100×1 + 500×4 + 1000×1 + 5000×1 |
| [75](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409092/202608/3100409092_1787996815443_c3c81aa3.jpg) | 3100409092_1787996815443_c3c81aa3.jpg | 9600.0 | 8100.0 | -1500.0 | 100×1 + 500×4 + 1000×1 + 5000×1 |
| [77](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409162/202610/3100409162_1791700167599_28c6f663.jpg) | 3100409162_1791700167599_28c6f663.jpg | 5800.0 | 2800.0 | -3000.0 | 100×3 + 500×3 + 1000×1 |
| [78](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409879/202608/3100409879_1786263147405_b0bbae6e.jpg) | 3100409879_1786263147405_b0bbae6e.jpg | 5000.0 | 1000.0 | -4000.0 | 500×2 |
| [79](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409879/202608/3100409879_1786263163828_d87e2b54.jpg) | 3100409879_1786263163828_d87e2b54.jpg | 5000.0 | 1000.0 | -4000.0 | 500×2 |
| [80](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409879/202608/3100409879_1786263178440_33295261.jpg) | 3100409879_1786263178440_33295261.jpg | 5000.0 | 1000.0 | -4000.0 | 500×2 |
| [81](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409879/202608/3100409879_1786270140390_4a14cc1a.jpg) | 3100409879_1786270140390_4a14cc1a.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [82](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409879/202608/3100409879_1786270154652_0d9c85b8.jpg) | 3100409879_1786270154652_0d9c85b8.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [83](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409879/202608/3100409879_1786876901084_e59c725c.jpg) | 3100409879_1786876901084_e59c725c.jpg | 5000.0 | 1000.0 | -4000.0 | 500×2 |
| [84](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409922/202609/3100409922_1790142606810_d9c5d2a2.jpg) | 3100409922_1790142606810_d9c5d2a2.jpg | 500000.0 | 5000.0 | -495000.0 | 5000×1 |
| [85](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409922/202609/3100409922_1790142631810_10423676.jpg) | 3100409922_1790142631810_10423676.jpg | 500000.0 | 5000.0 | -495000.0 | 5000×1 |
| [86](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409922/202609/3100409922_1790144098977_95058e7f.jpg) | 3100409922_1790144098977_95058e7f.jpg | 500000.0 | 5000.0 | -495000.0 | 5000×1 |
| [87](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409922/202609/3100409922_1790144099109_46f85fbb.jpg) | 3100409922_1790144099109_46f85fbb.jpg | 500000.0 | 5000.0 | -495000.0 | 5000×1 |
| [88](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409922/202609/3100409922_1790144485952_64976654.jpg) | 3100409922_1790144485952_64976654.jpg | 500000.0 | 5000.0 | -495000.0 | 5000×1 |
| [89](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409922/202609/3100409922_1790144510159_49f85934.jpg) | 3100409922_1790144510159_49f85934.jpg | 500000.0 | 5000.0 | -495000.0 | 5000×1 |
| [90](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409922/202610/3100409922_1791177867981_75a39f8c.jpg) | 3100409922_1791177867981_75a39f8c.jpg | 7000.0 | 6200.0 | -800.0 | 100×2 + 1000×1 + 5000×1 |
| [91](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409922/202610/3100409922_1791181616158_ee2ad833.jpg) | 3100409922_1791181616158_ee2ad833.jpg | 7000.0 | 6200.0 | -800.0 | 100×2 + 1000×1 + 5000×1 |
| [93](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409922/202610/3100409922_1791182827495_3816b046.jpg) | 3100409922_1791182827495_3816b046.jpg | 7000.0 | 6200.0 | -800.0 | 100×2 + 1000×1 + 5000×1 |
| [94](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409922/202610/3100409922_1791185140405_508810d8.jpg) | 3100409922_1791185140405_508810d8.jpg | 7000.0 | 6200.0 | -800.0 | 100×2 + 1000×1 + 5000×1 |
| [95](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100409922/202610/3100409922_1791185832610_129121b2.jpg) | 3100409922_1791185832610_129121b2.jpg | 7000.0 | 6200.0 | -800.0 | 100×2 + 1000×1 + 5000×1 |
| [98](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410251/202608/3100410251_1786369008438_890b7c71.jpg) | 3100410251_1786369008438_890b7c71.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [111](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410660/202610/3100410660_1791531236092_26a4f446.jpg) | 3100410660_1791531236092_26a4f446.jpg | 23700.0 | 17200.0 | -6500.0 | 100×2 + 500×2 + 1000×1 + 5000×3 |
| [122](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411561/202608/3100411561_1786607727283_cf580e54.jpg) | 3100411561_1786607727283_cf580e54.jpg | 4000.0 | 3000.0 | -1000.0 | 500×2 + 1000×2 |
| [124](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411561/202608/3100411561_1786608655596_c74a5a12.jpg) | 3100411561_1786608655596_c74a5a12.jpg | 4000.0 | 3000.0 | -1000.0 | 500×2 + 1000×2 |
| [141](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412197/202608/3100412197_1787229685133_c47eef01.jpg) | 3100412197_1787229685133_c47eef01.jpg | 6600.0 | 5600.0 | -1000.0 | 100×1 + 500×1 + 5000×1 |
| [142](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412197/202608/3100412197_1787229694994_b782495a.jpg) | 3100412197_1787229694994_b782495a.jpg | 6600.0 | 5600.0 | -1000.0 | 100×1 + 500×1 + 5000×1 |
| [143](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412197/202608/3100412197_1787229724341_5132818d.jpg) | 3100412197_1787229724341_5132818d.jpg | 6600.0 | 5600.0 | -1000.0 | 100×1 + 500×1 + 5000×1 |
| [146](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412197/202609/3100412197_1788491585471_2481e191.jpg) | 3100412197_1788491585471_2481e191.jpg | 10600.0 | 5600.0 | -5000.0 | 100×1 + 500×1 + 5000×1 |
| [147](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412197/202609/3100412197_1788491740360_02d44140.jpg) | 3100412197_1788491740360_02d44140.jpg | 10600.0 | 5600.0 | -5000.0 | 100×1 + 500×1 + 5000×1 |
| [148](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412197/202609/3100412197_1788499966868_bcb09db7.jpg) | 3100412197_1788499966868_bcb09db7.jpg | 10600.0 | 5600.0 | -5000.0 | 100×1 + 500×1 + 5000×1 |
| [149](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412197/202609/3100412197_1788499971558_3d9dd35a.jpg) | 3100412197_1788499971558_3d9dd35a.jpg | 10600.0 | 5600.0 | -5000.0 | 100×1 + 500×1 + 5000×1 |
| [150](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412796/202609/3100412796_1789549853335_05a0450e.jpg) | 3100412796_1789549853335_05a0450e.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [151](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412796/202609/3100412796_1789550351064_63ef29f6.jpg) | 3100412796_1789550351064_63ef29f6.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [158](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412887/202610/3100412887_1791854393107_cae6c350.jpg) | 3100412887_1791854393107_cae6c350.jpg | 4500.0 | 1900.0 | -2600.0 | 500×1 + 100×4 + 1000×1 |
| [160](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412931/202608/3100412931_1787051435507_c6f292da.jpg) | 3100412931_1787051435507_c6f292da.jpg | 5100.0 | 2600.0 | -2500.0 | 100×1 + 500×1 + 1000×2 |
| [161](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412931/202608/3100412931_1787051441232_e31f2140.jpg) | 3100412931_1787051441232_e31f2140.jpg | 5100.0 | 2600.0 | -2500.0 | 100×1 + 500×1 + 1000×2 |
| [162](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412931/202608/3100412931_1787051445753_69a162dc.jpg) | 3100412931_1787051445753_69a162dc.jpg | 5100.0 | 2600.0 | -2500.0 | 100×1 + 500×1 + 1000×2 |
| [163](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412887/202610/3100412887_1791861596625_fff6b822.jpg) | 3100412887_1791861596625_fff6b822.jpg | 4500.0 | 1900.0 | -2600.0 | 500×1 + 100×4 + 1000×1 |
| [164](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412931/202608/3100412931_1787051514128_9490104c.jpg) | 3100412931_1787051514128_9490104c.jpg | 5100.0 | 2600.0 | -2500.0 | 100×1 + 500×1 + 1000×2 |
| [165](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100412887/202610/3100412887_1791861608613_3cedefba.jpg) | 3100412887_1791861608613_3cedefba.jpg | 4500.0 | 1900.0 | -2600.0 | 500×1 + 100×4 + 1000×1 |
| [180](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100414330/202609/3100414330_1788269284035_834fdc2b.jpg) | 3100414330_1788269284035_834fdc2b.jpg | 6600.0 | 1600.0 | -5000.0 | 100×1 + 500×1 + 1000×1 |
| [202](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416273/202609/3100416273_1790312111492_64919b05.jpg) | 3100416273_1790312111492_64919b05.jpg | 5000.0 | 4000.0 | -1000.0 | 100×5 + 500×5 + 1000×1 |
| [205](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416976/202608/3100416976_1788154572266_f453776c.jpg) | 3100416976_1788154572266_f453776c.jpg | 11500.0 | 6500.0 | -5000.0 | 500×1 + 1000×1 + 5000×1 |
| [206](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416976/202608/3100416976_1788154696276_87c572ac.jpg) | 3100416976_1788154696276_87c572ac.jpg | 11500.0 | 6500.0 | -5000.0 | 500×1 + 1000×1 + 5000×1 |
| [207](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416976/202608/3100416976_1788158608375_dfb4b137.jpg) | 3100416976_1788158608375_dfb4b137.jpg | 11500.0 | 6500.0 | -5000.0 | 500×1 + 1000×1 + 5000×1 |
| [208](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416976/202608/3100416976_1788160878242_43c01c47.jpg) | 3100416976_1788160878242_43c01c47.jpg | 11500.0 | 6500.0 | -5000.0 | 500×1 + 1000×1 + 5000×1 |
| [210](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416976/202608/3100416976_1788164139940_2c268444.jpg) | 3100416976_1788164139940_2c268444.jpg | 11500.0 | 6500.0 | -5000.0 | 500×1 + 1000×1 + 5000×1 |
| [234](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418797/202609/3100418797_1790180058534_d801c559.jpg) | 3100418797_1790180058534_d801c559.jpg | 7300.0 | 2300.0 | -5000.0 | 100×3 + 2000×1 |
| [235](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418797/202609/3100418797_1790180059478_490e4d00.jpg) | 3100418797_1790180059478_490e4d00.jpg | 7300.0 | 2300.0 | -5000.0 | 100×3 + 2000×1 |
| [236](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418797/202609/3100418797_1790190465670_f1782a29.jpg) | 3100418797_1790190465670_f1782a29.jpg | 7300.0 | 2300.0 | -5000.0 | 100×3 + 2000×1 |
| [237](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418797/202609/3100418797_1790211662689_b23f1577.jpg) | 3100418797_1790211662689_b23f1577.jpg | 7300.0 | 2300.0 | -5000.0 | 100×3 + 2000×1 |
| [238](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418797/202609/3100418797_1790211740971_c85c4d9c.jpg) | 3100418797_1790211740971_c85c4d9c.jpg | 7300.0 | 2300.0 | -5000.0 | 100×3 + 2000×1 |
| [239](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418797/202609/3100418797_1790211809773_e750069d.jpg) | 3100418797_1790211809773_e750069d.jpg | 7300.0 | 2300.0 | -5000.0 | 100×3 + 2000×1 |
| [240](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418797/202609/3100418797_1790211810031_04211813.jpg) | 3100418797_1790211810031_04211813.jpg | 7300.0 | 2300.0 | -5000.0 | 100×3 + 2000×1 |
| [241](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418797/202609/3100418797_1790212274745_8e1cb6d7.jpg) | 3100418797_1790212274745_8e1cb6d7.jpg | 7300.0 | 2300.0 | -5000.0 | 100×3 + 2000×1 |
| [242](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418797/202609/3100418797_1790212326439_6db5f34e.jpg) | 3100418797_1790212326439_6db5f34e.jpg | 7300.0 | 2300.0 | -5000.0 | 100×3 + 2000×1 |
| [243](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100418797/202609/3100418797_1790217461262_535bb137.jpg) | 3100418797_1790217461262_535bb137.jpg | 7300.0 | 2300.0 | -5000.0 | 100×3 + 2000×1 |
| [262](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421140/202609/3100421140_1789397286040_40384716.jpg) | 3100421140_1789397286040_40384716.jpg | 11500.0 | 6500.0 | -5000.0 | 500×1 + 1000×1 + 5000×1 |
| [263](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421140/202609/3100421140_1789449929213_91225587.jpg) | 3100421140_1789449929213_91225587.jpg | 11500.0 | 6500.0 | -5000.0 | 500×1 + 1000×1 + 5000×1 |
| [264](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421140/202609/3100421140_1789444993067_3da4f92e.jpg) | 3100421140_1789444993067_3da4f92e.jpg | 11500.0 | 6500.0 | -5000.0 | 500×1 + 1000×1 + 5000×1 |
| [265](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421140/202609/3100421140_1789443808884_c89fe630.jpg) | 3100421140_1789443808884_c89fe630.jpg | 11500.0 | 6500.0 | -5000.0 | 500×1 + 1000×1 + 5000×1 |
| [266](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421229/202609/3100421229_1788424090603_82662c94.jpg) | 3100421229_1788424090603_82662c94.jpg | 600000.0 | 6900.0 | -593100.0 | 100×4 + 500×1 + 1000×6 |
| [267](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421229/202609/3100421229_1788424107964_8fc6776e.jpg) | 3100421229_1788424107964_8fc6776e.jpg | 600000.0 | 6900.0 | -593100.0 | 100×4 + 500×1 + 1000×6 |
| [268](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100421229/202609/3100421229_1788427871043_0da16a88.jpg) | 3100421229_1788427871043_0da16a88.jpg | 600000.0 | 6900.0 | -593100.0 | 100×4 + 500×1 + 1000×6 |
| [282](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423250/202609/3100423250_1788546096695_66da1322.jpg) | 3100423250_1788546096695_66da1322.jpg | 5100.0 | 4600.0 | -500.0 | 100×1 + 500×1 + 1000×4 |
| [293](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100423900/202610/3100423900_1790917679082_3224549a.jpg) | 3100423900_1790917679082_3224549a.jpg | 5000.0 | 1500.0 | -3500.0 | 100×5 + 1000×1 |
| [306](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100425499/202609/3100425499_1788609739551_8a65ad9b.jpg) | 3100425499_1788609739551_8a65ad9b.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [313](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100426711/202609/3100426711_1788978134834_6094a8e9.jpg) | 3100426711_1788978134834_6094a8e9.jpg | 2500.0 | 1500.0 | -1000.0 | 500×1 + 1000×1 |
| [317](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100427855/202610/3100427855_1791545659165_8c361070.jpg) | 3100427855_1791545659165_8c361070.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [320](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100427855/202610/3100427855_1791545707474_3b32c03e.jpg) | 3100427855_1791545707474_3b32c03e.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [321](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100427855/202610/3100427855_1791546817126_fc5abad5.jpg) | 3100427855_1791546817126_fc5abad5.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [322](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100427855/202610/3100427855_1791548089178_e8a8d8b6.jpg) | 3100427855_1791548089178_e8a8d8b6.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [329](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100429059/202609/3100429059_1790772465841_f757cd23.jpg) | 3100429059_1790772465841_f757cd23.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [330](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100429059/202609/3100429059_1790772479524_17732126.jpg) | 3100429059_1790772479524_17732126.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [334](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100430079/202609/3100430079_1790233539051_8e4abbdd.jpg) | 3100430079_1790233539051_8e4abbdd.jpg | 7300.0 | 4400.0 | -2900.0 | 100×3 + 1000×3 + 50×2 + 500×2 |
| [335](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100430079/202609/3100430079_1790236323618_38fb35dd.jpg) | 3100430079_1790236323618_38fb35dd.jpg | 7300.0 | 4400.0 | -2900.0 | 100×3 + 1000×3 + 50×2 + 500×2 |
| [342](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100431866/202610/3100431866_1791023198880_4576b1c0.jpg) | 3100431866_1791023198880_4576b1c0.jpg | 9100.0 | 6300.0 | -2800.0 | 100×3 + 1000×1 + 5000×1 |
| [345](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100432055/202609/3100432055_1789984181894_5959547d.jpg) | 3100432055_1789984181894_5959547d.jpg | 100.09 | 100.0 | -0.09000000000000341 | 100×1 |
| [346](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100432055/202609/3100432055_1789984231665_8aaad4d8.jpg) | 3100432055_1789984231665_8aaad4d8.jpg | 100.09 | 100.0 | -0.09000000000000341 | 100×1 |
| [351](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433289/202610/3100433289_1791283174089_a1040788.jpg) | 3100433289_1791283174089_a1040788.jpg | 11500.0 | 6500.0 | -5000.0 | 500×1 + 1000×1 + 5000×1 |
| [352](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433289/202610/3100433289_1791283193267_136ec695.jpg) | 3100433289_1791283193267_136ec695.jpg | 11500.0 | 6500.0 | -5000.0 | 500×1 + 1000×1 + 5000×1 |
| [353](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433289/202609/3100433289_1790313028193_a0625767.jpg) | 3100433289_1790313028193_a0625767.jpg | 6900.0 | 6600.0 | -300.0 | 100×1 + 500×1 + 1000×1 + 5000×1 |
| [356](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100433385/202609/3100433385_1790591786049_944139ff.jpg) | 3100433385_1790591786049_944139ff.jpg | 5500.0 | 1500.0 | -4000.0 | 500×1 + 1000×1 |
| [379](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434000/202609/3100434000_1790682503891_19eb0137.jpg) | 3100434000_1790682503891_19eb0137.jpg | 5300.0 | 3300.0 | -2000.0 | 100×3 + 500×2 + 1000×2 |
| [384](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434000/202610/3100434000_1791183610385_75fb2c62.jpg) | 3100434000_1791183610385_75fb2c62.jpg | 6100.0 | 1100.0 | -5000.0 | 100×1 + 1000×1 |
| [385](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434000/202610/3100434000_1791189621094_05e40a39.jpg) | 3100434000_1791189621094_05e40a39.jpg | 6100.0 | 1100.0 | -5000.0 | 100×1 + 1000×1 |
| [386](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100434000/202610/3100434000_1791185960597_ea00e9b2.jpg) | 3100434000_1791185960597_ea00e9b2.jpg | 6100.0 | 1100.0 | -5000.0 | 100×1 + 1000×1 |
| [434](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100436424/202609/3100436424_1790737778764_bce47625.jpg) | 3100436424_1790737778764_bce47625.jpg | 5300.0 | 3800.0 | -1500.0 | 100×3 + 500×3 + 1000×2 |
| [435](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100436539/202609/3100436539_1790320781447_f09b14fa.jpg) | 3100436539_1790320781447_f09b14fa.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [438](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437078/202610/3100437078_1791613592281_6834a6aa.jpg) | 3100437078_1791613592281_6834a6aa.jpg | 5000.0 | 3300.0 | -1700.0 | 100×3 + 1000×3 |
| [439](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437078/202610/3100437078_1791613599863_d0ca6796.jpg) | 3100437078_1791613599863_d0ca6796.jpg | 5000.0 | 3300.0 | -1700.0 | 100×3 + 1000×3 |
| [444](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437298/202610/3100437298_1791185341281_ba3b2c78.jpg) | 3100437298_1791185341281_ba3b2c78.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [445](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437298/202610/3100437298_1791186028777_7b1228e9.jpg) | 3100437298_1791186028777_7b1228e9.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [448](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100437298/202610/3100437298_1791188196134_6476514a.jpg) | 3100437298_1791188196134_6476514a.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [454](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100438127/202610/3100438127_1791900411073_2de8c3f8.jpg) | 3100438127_1791900411073_2de8c3f8.jpg | 6400.0 | 4400.0 | -2000.0 | 100×4 + 500×4 + 1000×2 |
| [455](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100438127/202610/3100438127_1791895635846_7b351c76.jpg) | 3100438127_1791895635846_7b351c76.jpg | 6400.0 | 4400.0 | -2000.0 | 100×4 + 500×4 + 1000×2 |
| [456](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100438127/202610/3100438127_1791900506872_4a180ea0.jpg) | 3100438127_1791900506872_4a180ea0.jpg | 6400.0 | 4400.0 | -2000.0 | 100×4 + 500×4 + 1000×2 |
| [457](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100438127/202610/3100438127_1791900450330_159b5af5.jpg) | 3100438127_1791900450330_159b5af5.jpg | 6400.0 | 4400.0 | -2000.0 | 100×4 + 500×4 + 1000×2 |
| [467](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100440144/202610/3100440144_1790956035943_6b3f0a45.jpg) | 3100440144_1790956035943_6b3f0a45.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [480](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100443103/202610/3100443103_1791288071791_0bc3930a.jpg) | 3100443103_1791288071791_0bc3930a.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [481](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100443103/202610/3100443103_1791288072338_bd38d609.jpg) | 3100443103_1791288072338_bd38d609.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [482](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100443103/202610/3100443103_1791288167750_329f5d0a.jpg) | 3100443103_1791288167750_329f5d0a.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [485](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100443644/202610/3100443644_1791620393780_3f8c7cbd.jpg) | 3100443644_1791620393780_3f8c7cbd.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |
| [497](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100445042/202610/3100445042_1791784265568_1e7e6839.jpg) | 3100445042_1791784265568_1e7e6839.jpg | 5000.0 | 3000.0 | -2000.0 | 500×2 + 1000×2 |

## 四、其他警告 (45条)


| idx | 图片 | amount | 明细加总 | 警告 |
|-----|------|--------|---------|------|
| [19](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406840/202607/3100406840_1785219254578_28723052.jpg) | 3100406840_1785219254578_28723052.jpg | 5.0 | 0 | 未可靠识别手写纸币明细，未默认补填张数 |
| [21](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406846/202609/3100406846_1790320787568_ceb8293d.jpg) | 3100406846_1790320787568_ceb8293d.jpg | 7600.0 | 0 | 金额校验不一致: amount(7600.0) + fee(25.0) != total(7600.0) |
| [22](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406846/202609/3100406846_1790320841386_818eb503.jpg) | 3100406846_1790320841386_818eb503.jpg | 7600.0 | 0 | 金额校验不一致: amount(7600.0) + fee(25.0) != total(7600.0) |
| [23](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100406846/202609/3100406846_1790322488268_399b0f70.jpg) | 3100406846_1790322488268_399b0f70.jpg | 7600.0 | 0 | 金额校验不一致: amount(7600.0) + fee(25.0) != total(7600.0) |
| [105](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410261/202608/3100410261_1786447819348_b8f9a614.jpg) | 3100410261_1786447819348_b8f9a614.jpg | 5000.0 | 0 | 未可靠识别手写纸币明细，未默认补填张数 |
| [107](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410309/202610/3100410309_1790832281033_21a27390.jpg) | 3100410309_1790832281033_21a27390.jpg | None | 0 | 未可靠识别存款金额，请检查 OCR 原文; 未可靠识别账户持有人姓名; 未可靠识别手写纸币明细，未默认补填张数 |
| [108](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100410309/202610/3100410309_1790837141516_d7d39f05.jpg) | 3100410309_1790837141516_d7d39f05.jpg | None | 0 | 未可靠识别存款金额，请检查 OCR 原文; 未可靠识别账户持有人姓名; 未可靠识别手写纸币明细，未默认补填张数 |
| [126](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411677/202608/3100411677_1788150649780_72c1cc79.jpg) | 3100411677_1788150649780_72c1cc79.jpg | None | 0 | 未可靠识别存款金额，请检查 OCR 原文; 未可靠识别账户持有人姓名; 未可靠识别手写纸币明细，未默认补填张数 |
| [127](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411797/202608/3100411797_1786173107117_ff0661e5.jpg) | 3100411797_1786173107117_ff0661e5.jpg | 5000.0 | 0 | 金额校验不一致: amount(5000.0) + fee(40.0) != total(5000.0) |
| [128](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411797/202608/3100411797_1786173122973_393d1bfa.jpg) | 3100411797_1786173122973_393d1bfa.jpg | 5000.0 | 0 | 金额校验不一致: amount(5000.0) + fee(40.0) != total(5000.0) |
| [129](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411797/202608/3100411797_1786177587263_3afc2fee.jpg) | 3100411797_1786177587263_3afc2fee.jpg | 5000.0 | 0 | 金额校验不一致: amount(5000.0) + fee(40.0) != total(5000.0) |
| [130](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411797/202608/3100411797_1786179571244_d668f657.jpg) | 3100411797_1786179571244_d668f657.jpg | 5000.0 | 0 | 金额校验不一致: amount(5000.0) + fee(40.0) != total(5000.0) |
| [132](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411966/202608/3100411966_1786934166902_37f662d2.jpg) | 3100411966_1786934166902_37f662d2.jpg | 5.0 | 50.0 | 纸币明细加总(50.0) != 存款总额(5.0) |
| [133](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411966/202608/3100411966_1786934193631_08167628.jpg) | 3100411966_1786934193631_08167628.jpg | 5.0 | 50.0 | 纸币明细加总(50.0) != 存款总额(5.0) |
| [134](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411966/202608/3100411966_1786934262099_7204dbd1.jpg) | 3100411966_1786934262099_7204dbd1.jpg | 5.0 | 50.0 | 纸币明细加总(50.0) != 存款总额(5.0) |
| [135](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100411966/202608/3100411966_1786937945884_929c17c7.jpg) | 3100411966_1786937945884_929c17c7.jpg | 5.0 | 50.0 | 纸币明细加总(50.0) != 存款总额(5.0) |
| [178](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100414113/202610/3100414113_1791957631579_0e17f93a.jpg) | 3100414113_1791957631579_0e17f93a.jpg | 21100.0 | 0 | 未可靠识别手写纸币明细，未默认补填张数 |
| [179](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100414441/202608/3100414441_1786950649230_fe359716.jpg) | 3100414441_1786950649230_fe359716.jpg | None | 0 | 未可靠识别存款金额，请检查 OCR 原文; 未可靠识别账户持有人姓名; 未可靠识别手写纸币明细，未默认补填张数 |
| [181](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100414441/202608/3100414441_1786950667979_9412eb06.jpg) | 3100414441_1786950667979_9412eb06.jpg | None | 0 | 未可靠识别存款金额，请检查 OCR 原文; 未可靠识别账户持有人姓名; 未可靠识别手写纸币明细，未默认补填张数 |
| [185](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100415645/202608/3100415645_1787037963373_b84915b5.jpg) | 3100415645_1787037963373_b84915b5.jpg | None | 0 | 未可靠识别存款金额，请检查 OCR 原文; 未可靠识别手写纸币明细，未默认补填张数 |
| [186](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100415645/202608/3100415645_1787039486402_e40faa96.jpg) | 3100415645_1787039486402_e40faa96.jpg | None | 0 | 未可靠识别存款金额，请检查 OCR 原文; 未可靠识别手写纸币明细，未默认补填张数 |
| [187](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100415645/202608/3100415645_1787054491774_44555d9f.jpg) | 3100415645_1787054491774_44555d9f.jpg | None | 0 | 未可靠识别存款金额，请检查 OCR 原文; 未可靠识别手写纸币明细，未默认补填张数 |
| [188](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100415645/202608/3100415645_1787054563921_98e237d1.jpg) | 3100415645_1787054563921_98e237d1.jpg | None | 0 | 未可靠识别存款金额，请检查 OCR 原文; 未可靠识别手写纸币明细，未默认补填张数 |
| [196](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100416270/202608/3100416270_1787031730113_2a89074e.jpg) | 3100416270_1787031730113_2a89074e.jpg | 5000.0 | 0 | 未可靠识别手写纸币明细，未默认补填张数 |
| [294](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100424676/202609/3100424676_1788848603500_712041d6.jpg) | 3100424676_1788848603500_712041d6.jpg | 10000.0 | 0 | 金额校验不一致: amount(10000.0) + fee(40.0) != total(10000.0) |
| [296](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100424676/202609/3100424676_1788849308871_3f3d534c.jpg) | 3100424676_1788849308871_3f3d534c.jpg | 10000.0 | 0 | 金额校验不一致: amount(10000.0) + fee(40.0) != total(10000.0) |
| [297](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100424489/202609/3100424489_1788506289698_f7bd5a2d.jpg) | 3100424489_1788506289698_f7bd5a2d.jpg | None | 0 | 未可靠识别存款金额，请检查 OCR 原文; 未可靠识别账户持有人姓名; 未可靠识别手写纸币明细，未默认补填张数 |
| [300](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100424763/202609/3100424763_1788590415508_df4bbdad.jpg) | 3100424763_1788590415508_df4bbdad.jpg | 5000.0 | 0 | 未可靠识别手写纸币明细，未默认补填张数 |
| [332](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100429630/202609/3100429630_1790432604969_f1b1f256.jpg) | 3100429630_1790432604969_f1b1f256.jpg | 1450.0 | 0 | 金额校验不一致: amount(1450.0) + fee(7500.0) != total(1475.0) |
| [401](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202609/3100435365_1790268875642_4743c44f.jpg) | 3100435365_1790268875642_4743c44f.jpg | 5000.0 | 0 | 金额校验不一致: amount(5000.0) + fee(40.0) != total(5000.0) |
| [402](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202609/3100435365_1790268883396_2694e726.jpg) | 3100435365_1790268883396_2694e726.jpg | 5000.0 | 0 | 金额校验不一致: amount(5000.0) + fee(40.0) != total(5000.0) |
| [403](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202609/3100435365_1790268900064_5403dcec.jpg) | 3100435365_1790268900064_5403dcec.jpg | 5000.0 | 0 | 金额校验不一致: amount(5000.0) + fee(40.0) != total(5000.0) |
| [404](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1790793746166_5d27218e.jpg) | 3100435365_1790793746166_5d27218e.jpg | 6000.0 | 0 | 金额校验不一致: amount(6000.0) + fee(40.0) != total(6000.0) |
| [405](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1790793746342_532b75f0.jpg) | 3100435365_1790793746342_532b75f0.jpg | 6000.0 | 0 | 金额校验不一致: amount(6000.0) + fee(40.0) != total(6000.0) |
| [406](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1790793746344_1ddc5231.jpg) | 3100435365_1790793746344_1ddc5231.jpg | 6000.0 | 0 | 金额校验不一致: amount(6000.0) + fee(40.0) != total(6000.0) |
| [407](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1790822913442_922b20ab.jpg) | 3100435365_1790822913442_922b20ab.jpg | 6000.0 | 0 | 金额校验不一致: amount(6000.0) + fee(40.0) != total(6000.0) |
| [408](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1790822918151_7ef9814d.jpg) | 3100435365_1790822918151_7ef9814d.jpg | 6000.0 | 0 | 金额校验不一致: amount(6000.0) + fee(40.0) != total(6000.0) |
| [409](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1790830596726_58e19d8e.jpg) | 3100435365_1790830596726_58e19d8e.jpg | 6000.0 | 0 | 金额校验不一致: amount(6000.0) + fee(40.0) != total(6000.0) |
| [410](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1790837349530_832f1a55.jpg) | 3100435365_1790837349530_832f1a55.jpg | 6000.0 | 0 | 金额校验不一致: amount(6000.0) + fee(40.0) != total(6000.0) |
| [411](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1790837349600_6556c0d4.jpg) | 3100435365_1790837349600_6556c0d4.jpg | 6000.0 | 0 | 金额校验不一致: amount(6000.0) + fee(40.0) != total(6000.0) |
| [412](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1790837349665_0353cd04.jpg) | 3100435365_1790837349665_0353cd04.jpg | 6000.0 | 0 | 金额校验不一致: amount(6000.0) + fee(40.0) != total(6000.0) |
| [413](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1790837349773_4aac96b8.jpg) | 3100435365_1790837349773_4aac96b8.jpg | 6000.0 | 0 | 金额校验不一致: amount(6000.0) + fee(40.0) != total(6000.0) |
| [414](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100435365/202610/3100435365_1790837350070_90d74001.jpg) | 3100435365_1790837350070_90d74001.jpg | 6000.0 | 0 | 金额校验不一致: amount(6000.0) + fee(40.0) != total(6000.0) |
| [483](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100443246/202610/3100443246_1791374592083_daad7ae3.jpg) | 3100443246_1791374592083_daad7ae3.jpg | 5000.0 | 0 | 金额校验不一致: amount(5000.0) + fee(40.0) != total(5000.0) |
| [484](https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/3100443246/202610/3100443246_1791394314997_24ade888.jpg) | 3100443246_1791394314997_24ade888.jpg | 5000.0 | 0 | 金额校验不一致: amount(5000.0) + fee(40.0) != total(5000.0) |

## 五、抽样验证结论

我下载了 ~25 张图片人工核对，发现以下规律：

1. **amount < 100** 的情况：100% 是 amount 错误，正确值 = 明细加总。最新代码已修复。

2. **amount ≥ 100 且加总不一致**：约 80% 是 amount 正确、明细错误（幻影行/数量错/面额误读）。

3. **旋转/颠倒图片**：amount 和明细都容易错，需要图像方向校正。

4. **日期错误**：5 条，需要修复日期解析逻辑。
