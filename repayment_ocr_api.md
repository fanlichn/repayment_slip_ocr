# Repayment Slip OCR 接口对接文档

> 斯里兰卡银行还款/转账/现金存款凭证识别服务。
> 复用 sri_lanka_nic_ocr 的图像预处理、OCR 引擎与远程图片下载（含 SSRF 防护），独立部署。

## 1. 基本信息

| 项 | 说明 |
| --- | --- |
| Base URL | `http://<host>:8000` |
| 协议 | HTTP |
| 请求/返回格式 | JSON（上传文件接口为 `multipart/form-data`） |
| 字符编码 | UTF-8 |

---

## 2. 健康检查

### 2.1 GET /health

**请求**

```bash
curl -X GET "http://localhost:8000/health"
```

**返回**

```json
{ "status": "ok" }
```

---

## 3. OCR 识别接口

提供三种上传方式，能力完全一致，均支持 `include_lines` 查询参数：

| 接口 | 请求方式 | 请求体 |
| --- | --- | --- |
| `/ocr` | POST | `multipart/form-data`（`file` 字段） |
| `/ocr_base64` | POST | JSON（`image_base64`） |
| `/ocr_url` | POST | JSON（`image_url`） |

### 3.1 通用查询参数

| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `include_lines` | bool | 否 | `false` | 为 `true` 时，返回原始 OCR 行（`text`/`confidence`/`box`），便于调试 |

### 3.2 POST /ocr（上传图片文件）

**请求**

```bash
curl -X POST "http://localhost:8000/ocr" \
  -F "file=@receipt.jpg"

# 需要原始 OCR 行时
curl -X POST "http://localhost:8000/ocr?include_lines=true" \
  -F "file=@receipt.jpg"
```

### 3.3 POST /ocr_base64（Base64 图片）

**请求**

```bash
curl -X POST "http://localhost:8000/ocr_base64" \
  -H "Content-Type: application/json" \
  -d '{"image_base64": "<图片 Base64 字符串，不含 data:image 前缀>"}'
```

### 3.4 POST /ocr_url（图片 URL）

支持 OSS / S3 / CDN 等公开链接，内置 SSRF 防护（默认拒绝内网/回环地址）。

**请求**

```bash
curl -X POST "http://localhost:8000/ocr_url" \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/xxx.jpg"}'
```

---

## 4. 返回格式

所有识别接口的返回结构统一为一个**扁平 JSON 对象**，但字段集合**随图片类型不同而不同**。核心规则：

1. **固定字段 `success`**：布尔值，表示是否成功识别出有效字段。
2. **有明确「字段名 : 值」结构的图片**：直接返回图片上的原始字段名作为 key，值作为 value。
3. **无明确字段名的图片**（如部分 App 转账成功回执）：返回统一的规范化字段名（见 4.2）。
4. 值为空（`null`）的字段会被自动省略，不出现在返回里。

### 4.1 有明确字段名的图片

返回的 key 是图片上的原始字段名（不同银行措辞不同），value 为图片原文。

**Sampath Vishwa 转账回执示例：**

```json
{
  "success": true,
  "Status": "Success",
  "Transaction ID": "89101292",
  "Date & Time": "2026-10-09 13:19:00",
  "Source Account Number": "*2918",
  "Amount": "LKR 5,500.00",
  "Beneficiary Name": "Lak Artha Pyt Ltd",
  "Beneficiary Account No.": "1001096962",
  "Beneficiary Remarks": "913171047v",
  "Destination Bank": "COMMERCIAL BANK OF CEYLON"
}
```

**BOC Flex 转账回执示例：**

```json
{
  "success": true,
  "Transaction Amount": "LKR 5,700.00",
  "Transaction Date & Time": "2026-10-09 13:47:00",
  "Transaction ID": "FX10858294700000",
  "Charges & Fee": "LKR 25.00",
  "Remarks": "sss",
  "Transaction Status": "SUCCESS",
  "Account Number": "**3943",
  "Sender's Name": "MR A MEVIN",
  "Sender's Bank": "Bank of Ceylon",
  "Account No": "1001096962",
  "Beneficiary Name": "Lakartha",
  "Beneficiary Bank": "Commercial Bank"
}
```

**People's Pay 回执示例**（Pay from / Pay to 两个同名分区，用 `Payer` / `Payee` 前缀区分）：

```json
{
  "success": true,
  "Payer Name": "MS VINDYA NADEESHANI DE SILVA",
  "Payer Bank": "People's Bank",
  "Payer Account No": "012200******84",
  "Account Currency": "LKR",
  "Payee Name": "Lak Artha (Pvt) Ltd",
  "Payee Bank": "Commercial Bank PLC",
  "Payee Account No": "1001096962",
  "Amount (LKR)": "7,900.00",
  "Fee Amount (LKR)": "25.00",
  "Total debit amount (LKR)": "7,925.00",
  "Date & Time": "2026-10-08 12:02:53",
  "Trace No": "2026100800600901",
  "Remarks": "loan"
}
```

**Commercial Bank CDM 无卡存款凭条示例：**

```json
{
  "success": true,
  "TRACE": "5107",
  "TRANSACTION": "CARDLESS DEPOSIT",
  "DEPOSIT AMOUNT": "6,100.00",
  "ACCOUNT NUMBER": "1001096962",
  "CUSTOMER NAME": "LAK ARTHA SERVICES",
  "SOURCE OF FUNDS": "UNKNOWN"
}
```

### 4.2 无明确字段名的图片（规范化字段）

当图片没有清晰的「字段名 : 值」结构时，返回以下规范化字段（仅返回识别到的非空字段）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `success` | bool | 是否成功识别 |
| `status` | string | 交易状态：`success` / `pending` / `failed` |
| `bank` | string | 银行/渠道：`peoples_bank` / `commercial_bank` / `boc` / `hnb` / `vishwa` 等 |
| `amount` | number | 交易金额（LKR） |
| `fee` | number | 手续费 |
| `total_debit` | number | 借方合计 |
| `currency` | string | 币种（默认 `LKR`） |
| `datetime` | string | 交易时间（ISO 8601） |
| `payer_name` / `payer_account` / `payer_bank` | string | 付款方姓名/账号/银行 |
| `payee_name` / `payee_account` / `payee_bank` | string | 收款方姓名/账号/银行 |
| `transaction_reference` | string | 交易参考号 |
| `remarks` | string | 备注/附言 |

**Commercial Bank App 转账成功回执示例：**

```json
{
  "success": true,
  "status": "success",
  "bank": "commercial_bank",
  "amount": 6400.0,
  "currency": "LKR",
  "datetime": "2026-10-09T13:43:00",
  "payee_name": "Lak Artha (Pvt) Ltd",
  "payee_account": "1001096962",
  "payee_bank": "Commercial Bank PLC",
  "transaction_reference": "416444/154352389"
}
```

### 4.3 include_lines=true 时的附加字段

开启 `include_lines=true` 后，返回末尾会追加 `lines` 数组，每个元素为一条原始 OCR 行：

```json
{
  "success": true,
  "...": "...",
  "lines": [
    {
      "text": "ACC0UNT NUMBER: 1001096962",
      "confidence": 0.9773436784744263,
      "box": [[218.0, 677.0], [721.0, 677.0], [721.0, 710.0], [218.0, 710.0]]
    }
  ]
}
```

`box` 为四边形四个顶点坐标 `[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]`，对应图片中的像素位置。

---

## 5. 错误码

| 状态码 | 场景 | 返回体 |
| --- | --- | --- |
| `400` | base64 格式无效 | `{"detail": "无效的 base64 图片数据"}` |
| `400` | 图片 URL 获取失败（含 SSRF 拦截） | `{"detail": "<具体原因>"}` |
| `413` | 上传文件超过大小限制（默认 15MB） | `{"detail": "文件过大"}` |
| `500` | 服务内部错误 | `{"detail": "Internal Server Error"}` |

---

## 6. 注意事项

- **字段因图而异**：本服务对接多种银行凭证，返回的字段名与数量不固定，接入方需按 key 动态解析，不要依赖固定字段集合。
- **账号脱敏**：部分账号可能带掩码（如 `012200******84`、`**3943`），属银行回执原始展示，服务原样返回。
- **金额字段**：有明确字段名的图片中金额为原文（如 `"LKR 5,500.00"`）；规范化字段中金额为数值（如 `6400.0`）。
- **日期字段**：统一为 24 小时制 `YYYY-MM-DD HH:MM:SS`，自动去掉 AM/PM（如 `"2026-10-09 13:19:00"`）。
- **OCR 精度**：部分字段（手写、低清晰度、遮挡）可能识别不到或存在 OCR 误读，接入方建议对关键字段做二次校验。
