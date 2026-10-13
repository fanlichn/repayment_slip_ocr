# 斯里兰卡 OCR 识别服务

面向生产环境的斯里兰卡（Sri Lanka）OCR 识别服务，包含两个相互独立的子服务：

| 服务 | 模块 | 默认端口 | 说明 |
| --- | --- | --- | --- |
| **NIC OCR** | `app/` | `8000` | 国民身份证（NIC）识别，抽取姓名、身份证号、出生日期、性别、地址等 |
| **Repayment Slip OCR** | `repayment_slip_ocr/` | `8001` | 银行还款/转账凭证识别，抽取付款方、收款方、金额、日期、参考号、纸币明细等 |

两个服务共用同一套 OCR 引擎、图像预处理与远程图片下载（含 SSRF 防护），可单独部署、互不影响。

识别字段：

| 字段 | 说明 |
| --- | --- |
| `nic_number` | 身份证号码（旧版 9 位数字 + V/X，或新版 12 位数字） |
| `name` | 英文姓名（支持跨行合并，自动拼接 `Name:` 标签下方 1-2 行续行） |
| `name_sinhala` | 僧伽罗语姓名（占位字段，当前为 `null`，见「多语言姓名」） |
| `name_tamil` | 泰米尔语姓名（占位字段，当前为 `null`，见「多语言姓名」） |
| `date_of_birth` | 出生日期（优先取卡片印刷值，缺失时由号码解码） |
| `gender` | 性别（卡片印刷值优先，缺失时由号码解码） |
| `address` | 地址 |
| `date_of_issue` | 签发日期 |
| `nic.*` | 号码解码结果（类型、出生年份、性别、是否选民 V/X、序列号等） |

> 身份证号码的出生日期/性别解码遵循官方规则：旧版 `YY DDD SSS C V/X`，新版 `YYYY DDD SSSS C`，其中 `DDD` 为一年中的第几天，女性 +500。参考 [DRP 官方 FAQ](https://drp.gov.lk/en/faq.php)。

---

## 目录结构

```
sri_lanka_nic_ocr/
├── app/                        # NIC OCR 服务
│   ├── __init__.py
│   ├── config.py               # 配置（环境变量 .env，两个服务共用）
│   ├── nic_parser.py           # NIC 号码解析（出生日期/性别/校验）
│   ├── preprocessing.py        # OpenCV 图像预处理（缩放/去噪/纠偏/二值化）
│   ├── ocr_engine.py           # OCR 引擎封装（PaddleOCR / Tesseract）
│   ├── url_fetch.py            # 远程图片下载（含 SSRF 防护）
│   ├── extractor.py            # NIC 字段抽取
│   ├── schemas.py              # NIC 响应模型
│   ├── main.py                 # NIC FastAPI 服务（端口 8000）
│   └── cli.py                  # NIC 命令行单图测试
├── repayment_slip_ocr/         # 还款/转账凭证 OCR 服务
│   ├── __init__.py
│   ├── extractor.py            # 凭证字段抽取（多银行/多版式）
│   ├── schemas.py              # 凭证响应模型
│   ├── main.py                 # 凭证 FastAPI 服务（端口 8001）
│   └── cli.py                  # 凭证命令行单图测试
├── tests/
│   ├── test_nic_parser.py
│   └── test_repayment_extractor.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 环境要求

- Python 3.10+
- 内存建议 ≥ 2 GB（PaddleOCR 模型加载后约占 1 GB+）
- 可选：NVIDIA GPU（需 `paddlepaddle-gpu` 与 CUDA 环境）

---

## 快速开始（本地开发）

```bash
# 1. 创建并激活虚拟环境
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 2. 安装依赖（首次会下载 PaddleOCR 模型，耗时较长）
pip install -r requirements.txt

# 3. （可选）复制配置
copy .env.example .env        # Windows
cp .env.example .env          # Linux/macOS

# 4. 启动 NIC OCR 服务（端口 8000）
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 5. 启动 Repayment Slip OCR 服务（端口 8001，另开终端）
uvicorn repayment_slip_ocr.main:app --host 0.0.0.0 --port 8001

# 6. 单图命令行测试（无需启动服务）
python -m app.cli path/to/id_card.jpg                      # NIC
python -m repayment_slip_ocr.cli path/to/slip.jpg           # 凭证
```

启动成功后访问：

- NIC OCR 接口文档：<http://localhost:8000/docs>
- Repayment Slip OCR 接口文档：<http://localhost:8001/docs>
- 健康检查：<http://localhost:8000/health>（NIC）/ <http://localhost:8001/health>（凭证）

---

## API 使用示例

### 上传图片（multipart）

```bash
curl -X POST http://localhost:8000/ocr \
  -F "file=@id_card.jpg"
```

### Base64（JSON）

```bash
curl -X POST http://localhost:8000/ocr_base64 \
  -H "Content-Type: application/json" \
  -d '{"image_base64": "<BASE64编码的图片>"}'
```

### 图片 URL（OSS / S3 / CDN 等公开链接）

服务端会直接下载图片并识别，适合图片已存在对象存储（如阿里云 OSS）的场景：

```bash
curl -X POST http://localhost:8000/ocr_url \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/ID_FRONT/3100435890/202609/3100435890_1789889899894_af49363b.jpg"}'
```

```python
import requests

resp = requests.post(
    "http://localhost:8000/ocr_url",
    json={"image_url": "https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/ID_FRONT/xxx.jpg"},
    timeout=60,
)
print(resp.json())
```

URL 下载相关配置（环境变量，前缀 `NIC_OCR_`）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `NIC_OCR_URL_FETCH_TIMEOUT_SECONDS` | `10` | 下载超时（秒） |
| `NIC_OCR_URL_FETCH_ALLOW_PRIVATE_HOSTS` | `false` | 是否允许内网/私有地址，生产保持 `false`（SSRF 防护） |

下载失败、非图片内容、超过 `NIC_OCR_MAX_UPLOAD_BYTES` 等情况均返回 `400` 并带中文错误说明。

> **私有 Bucket 注意**：若 OSS Bucket 开了私有读写，需在业务服务端生成**带签名的临时 URL**（如 `oss2.Bucket.sign_url`，设置较短过期时间）再传给本接口，不要把 AccessKey 提供给 OCR 服务。

### Python 调用

```python
import requests

with open("id_card.jpg", "rb") as f:
    resp = requests.post("http://localhost:8000/ocr", files={"file": f})
print(resp.json())
```

返回示例：

```json
{
  "success": true,
  "nic_number": "198512345678",
  "nic": {
    "valid": true,
    "normalized": "198512345678",
    "nic_type": "new",
    "birth_year": 1985,
    "gender": "male",
    "birth_date": "1985-05-03",
    "is_voter": null,
    "serial": "4567",
    "check_digit": "8"
  },
  "name": "JOHN DOE",
  "date_of_birth": "1985-05-03",
  "gender": "male",
  "address": "NO. 123, MAIN ROAD, COLOMBO",
  "date_of_issue": "2016-06-01",
  "lines": [],
  "warnings": [],
  "elapsed_ms": 812.3
}
```

---

## Repayment Slip OCR（还款/转账凭证识别）

独立于 NIC OCR 的第二个服务，识别斯里兰卡各银行的还款/转账/现金存款凭证，抽取付款方、收款方、金额、日期、参考号、纸币明细等字段。

### 支持的文档类型与银行

| `doc_type` | 说明 | 已适配银行/渠道 |
| --- | --- | --- |
| `payment_confirmation` | 付款确认回执 | People's Bank、BOC、Pan Asia 等 |
| `fund_transfer_receipt` | 转账回执 | Commercial Bank、HNB、BOC 等 |
| `cash_deposit_slip` | 现金存款凭条 | Commercial Bank（含 CDM 无卡存款、纸质 Cash Credit Slip） |
| `e_receipt` | 电子收据 | Commercial Bank 等 |

### 识别字段

| 字段 | 说明 |
| --- | --- |
| `doc_type` | 文档类型（见上表） |
| `status` | 交易状态：`success` / `pending` / `failed` |
| `bank` | 银行/渠道（`peoples_bank` / `commercial_bank` / `boc` / `hnb` / ...） |
| `payer` | 付款方：`name` / `account` / `account_prefix` / `account_last4` / `bank` |
| `payee` | 收款方：同上结构 |
| `amount` | 交易金额（LKR） |
| `fee` | 手续费 |
| `total_debit` | 借方合计 |
| `currency` | 币种（默认 `LKR`） |
| `datetime` | 交易时间（ISO 8601） |
| `references` | 各类参考号：`transaction_id` / `txn_ref` / `retrieval_ref` / `bank_reference_number` / `e_receipt_reference` / `my_ref` / `receiver_ref` / `remarks` |
| `deposit_breakdown` | 现金存款纸币明细：`[{denomination, quantity, amount}]` |
| `branch` / `terminal_id` / `trace_no` | 存款凭条的网点/终端/追踪号 |
| `warnings` | 识别过程中的提示（如明细加总与总额不符、未可靠识别等） |

### 接口

三个接口与 NIC OCR 一致，均支持 `include_lines=true` 查询参数（返回原始 OCR 行，便于调试）：

```bash
# 上传图片
curl -X POST "http://localhost:8001/ocr?include_lines=true" -F "file=@slip.jpg"

# Base64
curl -X POST "http://localhost:8001/ocr_base64?include_lines=true" \
  -H "Content-Type: application/json" \
  -d '{"image_base64": "<BASE64>"}'

# 图片 URL（OSS / S3 / CDN 公开链接）
curl -X POST "http://localhost:8001/ocr_url?include_lines=true" \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://lak-pic.oss-ap-southeast-1.aliyuncs.com/attachment/REPAY_PHOTO/xxx.jpg"}'
```

### 返回示例（Commercial Bank Cash Credit Slip）

```json
{
  "success": true,
  "doc_type": "cash_deposit_slip",
  "bank": "commercial_bank",
  "payer": {},
  "payee": {
    "name": "Lak Artha (Pvt) Ltd",
    "account": "1001096962",
    "account_prefix": "1001",
    "account_last4": "6962",
    "bank": "Commercial Bank"
  },
  "amount": 5300.0,
  "total_debit": 5300.0,
  "currency": "LKR",
  "datetime": "2026-10-09T09:24:16",
  "references": {},
  "fields": {},
  "deposit_breakdown": [],
  "warnings": ["未可靠识别手写纸币明细，未默认补填张数"],
  "lines": [],
  "elapsed_ms": 6491.17
}
```

### 调试技巧

当识别结果不符合预期时，用 `include_lines=true` 获取原始 OCR 文本，检查关键字段是否被正确识别：

- **金额识别异常**：OCR 可能把千分位逗号识别成点（如 `5.300.00`），已内置兼容解析。
- **姓名/账号错位**：现金存款凭条优先取表单字段值，缺失时回退底部机打户名；账号用带校验的 `_extract_account` 提取。
- **纸币明细为空**：手写张数 OCR 识别率低，代码不会默认补填（避免误填 quantity=1），而是留空并发出警告。
- **日期错误**：优先取机打完整日期时间，表单日期作为兜底。

---

## 生产部署

两个服务共用同一镜像，通过不同的启动命令区分。

### 方案一：Docker Compose（推荐）

`docker-compose.yml` 已配置两个服务：`nic-ocr`（8000）和 `repayment-ocr`（8001）。

```bash
# 构建并后台启动两个服务（restart: unless-stopped 会自动拉起）
docker compose up -d --build

# 只启动其中一个
docker compose up -d nic-ocr
docker compose up -d repayment-ocr

# 查看日志
docker compose logs -f nic-ocr
docker compose logs -f repayment-ocr

# 查看状态
docker compose ps
```

### 方案二：Docker 单容器

```bash
docker build -t sri-lanka-nic-ocr:latest .

# NIC OCR（端口 8000）
docker run -d --name nic-ocr \
  --restart unless-stopped \
  -p 8000:8000 \
  -e NIC_OCR_OCR_ENGINE=paddle \
  -e NIC_OCR_PADDLE_USE_GPU=false \
  sri-lanka-nic-ocr:latest

# Repayment Slip OCR（端口 8001，覆盖启动命令）
docker run -d --name repayment-ocr \
  --restart unless-stopped \
  -p 8001:8000 \
  -e NIC_OCR_OCR_ENGINE=paddle \
  -e NIC_OCR_PADDLE_USE_GPU=false \
  sri-lanka-nic-ocr:latest \
  uvicorn repayment_slip_ocr.main:app --host 0.0.0.0 --port 8000 --workers 2
```

### 方案三：Linux 裸机 + systemd

1. 按「快速开始」安装依赖到某个虚拟环境，例如 `/opt/nic-ocr/.venv`。
2. 分别创建两个服务文件。

NIC OCR（`/etc/systemd/system/nic-ocr.service`）：

```ini
[Unit]
Description=Sri Lanka NIC OCR Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/nic-ocr
EnvironmentFile=/opt/nic-ocr/.env
ExecStart=/opt/nic-ocr/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5
User=nic-ocr
StandardOutput=append:/var/log/nic-ocr/out.log
StandardError=append:/var/log/nic-ocr/err.log

[Install]
WantedBy=multi-user.target
```

Repayment Slip OCR（`/etc/systemd/system/repayment-ocr.service`）：

```ini
[Unit]
Description=Sri Lanka Repayment Slip OCR Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/nic-ocr
EnvironmentFile=/opt/nic-ocr/.env
ExecStart=/opt/nic-ocr/.venv/bin/uvicorn repayment_slip_ocr.main:app --host 0.0.0.0 --port 8001 --workers 2
Restart=always
RestartSec=5
User=nic-ocr
StandardOutput=append:/var/log/repayment-ocr/out.log
StandardError=append:/var/log/repayment-ocr/err.log

[Install]
WantedBy=multi-user.target
```

3. 启动并设为开机自启：

```bash
sudo mkdir -p /var/log/nic-ocr /var/log/repayment-ocr
sudo systemctl daemon-reload
sudo systemctl enable --now nic-ocr repayment-ocr
```

### 方案四：Windows 裸机

使用 [NSSM](https://nssm.cc/) 将服务注册为 Windows 服务：

```powershell
# NIC OCR
nssm install NicOcr "C:\path\to\.venv\Scripts\uvicorn.exe"
nssm set NicOcr AppParameters "app.main:app --host 0.0.0.0 --port 8000 --workers 2"
nssm set NicOcr AppDirectory "C:\path\to\sri_lanka_nic_ocr"
nssm set NicOcr AppStdout "C:\path\to\logs\nic-out.log"
nssm set NicOcr AppStderr "C:\path\to\logs\nic-err.log"
nssm set NicOcr Start SERVICE_AUTO_START
nssm start NicOcr

# Repayment Slip OCR
nssm install RepaymentOcr "C:\path\to\.venv\Scripts\uvicorn.exe"
nssm set RepaymentOcr AppParameters "repayment_slip_ocr.main:app --host 0.0.0.0 --port 8001 --workers 2"
nssm set RepaymentOcr AppDirectory "C:\path\to\sri_lanka_nic_ocr"
nssm set RepaymentOcr AppStdout "C:\path\to\logs\repayment-out.log"
nssm set RepaymentOcr AppStderr "C:\path\to\logs\repayment-err.log"
nssm set RepaymentOcr Start SERVICE_AUTO_START
nssm start RepaymentOcr
```

也可用「任务计划程序」在开机时运行 `uvicorn app.main:app ...`（选择「无论用户是否登录都运行」）。

---

## 重启 / 更新 / 回滚

### Docker Compose

```bash
# 重启全部服务（不重建）
docker compose restart

# 只重启某一个
docker compose restart nic-ocr
docker compose restart repayment-ocr

# 更新代码后：重建并滚动更新
git pull
docker compose up -d --build

# 回滚到上一个镜像标签（示例）
docker compose down
docker run -d --name nic-ocr -p 8000:8000 sri-lanka-nic-ocr:v1.0.0
```

### Docker 单容器

```bash
docker restart nic-ocr repayment-ocr          # 重启
docker stop nic-ocr && docker rm nic-ocr && docker run -d ...   # 重建
```

### systemd（Linux）

```bash
sudo systemctl restart nic-ocr repayment-ocr   # 重启
sudo systemctl stop nic-ocr                    # 停止单个
sudo systemctl status repayment-ocr            # 查看状态与最近日志
sudo journalctl -u repayment-ocr -f            # 跟踪日志
```

### Windows 服务（NSSM）

```powershell
nssm restart NicOcr          # 重启 NIC OCR
nssm restart RepaymentOcr    # 重启 Repayment OCR
nssm stop NicOcr             # 停止
nssm start RepaymentOcr      # 启动
nssm status NicOcr           # 查看状态
```

---

## 配置项（环境变量 / `.env`）

前缀 `NIC_OCR_`，也可直接写入 `.env` 文件。**NIC OCR 与 Repayment Slip OCR 两个服务共用同一套配置。**

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `NIC_OCR_OCR_ENGINE` | `paddle` | OCR 引擎：`paddle` / `tesseract` |
| `NIC_OCR_OCR_LANG` | `en` | 语言：PaddleOCR 用 `en`；Tesseract 用 `eng` |
| `NIC_OCR_NAME_OCR_ENGINE` | `tesseract` | 多语言姓名第二引擎：`tesseract` / `none`（关闭） |
| `NIC_OCR_NAME_OCR_LANG` | `sin+tam` | 第二引擎语言包（Tesseract `+` 连接） |
| `NIC_OCR_NAME_TESSERACT_PSM` | `6` | 第二引擎 Tesseract 页面分割模式 |
| `NIC_OCR_TESSERACT_CMD` | 空 | tesseract 可执行文件路径（不在 PATH 时指定） |
| `NIC_OCR_PADDLE_USE_GPU` | `false` | 是否使用 GPU |
| `NIC_OCR_PADDLE_USE_ANGLE_CLS` | `true` | 是否启用方向分类 |
| `NIC_OCR_NIC_DAY_MODE` | `nic366` | 出生日期解码模式：`nic366`（推荐，匹配真实出生日期）/ `literal`（见下） |
| `NIC_OCR_OLD_NIC_CENTURY` | `1900` | 旧版号码两位年份的前缀 |
| `NIC_OCR_HOST` | `0.0.0.0` | 监听地址 |
| `NIC_OCR_PORT` | `8000` | 监听端口 |
| `NIC_OCR_WORKERS` | `2` | uvicorn worker 数 |
| `NIC_OCR_MAX_UPLOAD_BYTES` | `15728640` | 上传大小上限（15 MB） |

---

## NIC 号码解析规则与已知偏移

斯里兰卡身份证号自 2016 年 1 月 1 日起从「9 位数字 + 字母」升级为「12 位数字」：

- 旧版 `YY DDD SSS C V/X`：`YY` 出生年份后两位（按 1900 世纪解释），`DDD` 年内第几天，`SSS` 序列号，`C` 校验位，`V`=选民 / `X`=非选民。
- 新版 `YYYY DDD SSSS C`：`YYYY` 完整出生年份，`DDD` 年内第几天，`SSSS` 序列号，`C` 校验位。
- 性别：`DDD > 500` 表示女性（需减去 500 得到实际天数），否则为男性。

**366 天日历偏移（重要）**：政府编号方案使用「固定 366 天日历」，每年都为 2 月 29 日预留一个位置。因此在非闰年、出生日在 3 月 1 日及之后时，号码中的 `DDD` 比真实「年内第几天」大 1。

- 默认 `nic366`：补偿 366 天日历，还原真实出生日期（3 月之后非闰年生日减 1 天）；实测与卡片印刷的出生日期一致。
- `literal`：按字面天数解码（`Jan 1 + (DDD - 1)` 天），简单直观，但对非闰年 3 月之后的生日会偏大 1 天。

由于卡片本身印刷了出生日期，本服务**优先采用 OCR 识别的印刷日期**，号码解码结果作为兜底与交叉校验；两者不一致时会写入 `warnings`。如需改回字面天数解码，设置 `NIC_OCR_NIC_DAY_MODE=literal` 即可。

> 参考：[DRP 官方 FAQ](https://drp.gov.lk/en/faq.php)、[Understanding Sri Lanka's NIC System](https://thesrilanka.lk/info/national-identity-card/understanding-sri-lankan-nic-system/)、[lk-id（TypeScript 实现，含 366 天日历说明）](https://www.npmjs.com/package/lk-id)、[lka-nic-decoder（Python 实现）](https://pypi.org/project/lka-nic-decoder/)。

---

## 性能与优化

- **worker 数**：CPU 环境下建议 `workers = CPU 核数 / 2` 到 `CPU 核数` 之间；内存受限时降低 worker 数。
- **GPU**：将 `requirements.txt` 中的 `paddlepaddle` 换成 `paddlepaddle-gpu==2.6.1`，并设置 `NIC_OCR_PADDLE_USE_GPU=true`；Compose 中取消 `deploy.resources` 注释。
- **首次请求延迟**：服务启动时已预热模型（lifespan 中调用 `warmup()`），避免首个请求过慢。
- **并发**：模型在进程内共享，`uvicorn --workers N` 会启动 N 个独立进程，各自加载一份模型。

---

## 健康检查与日志

- 健康检查：`GET /health`，返回 `{"status":"ok"}`。
  - NIC OCR：`http://localhost:8000/health`
  - Repayment Slip OCR：`http://localhost:8001/health`
- Docker Compose 已为两个服务内置 healthcheck（每 30s 探测一次）。
- 日志：Docker 用 `docker compose logs -f nic-ocr` / `docker compose logs -f repayment-ocr`；systemd 用 `journalctl -u nic-ocr -f` / `journalctl -u repayment-ocr -f`。

---

## 多语言姓名

斯里兰卡身份证正面的姓名以三种文字印刷：**英语（拉丁字母）、泰米尔语、僧伽罗语**。

当前实现说明：

- `name` 字段返回**英文姓名**，且已支持跨行合并（`Name:` 标签下方的字母续行会自动拼接）。
- `name_sinhala` / `name_tamil` 由**多语言姓名第二引擎**识别，默认为 Tesseract（`sin` + `tam` 语言包），与主引擎（PaddleOCR，仅拉丁文字）相互独立、互不影响。
- 第二引擎在纠偏后的原图上运行一次，输出行级文本与坐标；抽取逻辑以**英文姓名区块为锚点**，从第二引擎结果中取垂直距离最近（其次水平重叠最大）的目标文字行——卡片顶部还有「ශ්‍රී ලංකා / இலங்கை」等标语，因此不能见文字就取。
- 结果会清洗掉混入的非目标字符；僧伽罗语的零宽连接符（ZWJ/ZWNJ）会保留，保证合体字（如 `ශ්‍රී`）完整。
- 第二引擎**永不阻断主流程**：启动时 `tesseract` 不可用或缺语言包会记录日志并降级（`name_sinhala`/`name_tamil` 返回 `null`）；若卡片上检测到对应文字但未能识别出姓名行，`warnings` 中会出现提示。

### 部署启用方式

**Docker（已内置，无需操作）**：镜像已安装 `tesseract-ocr`、`tesseract-ocr-sin`、`tesseract-ocr-tam`，默认启用。

**Linux 裸机 / systemd**：

```bash
sudo apt install tesseract-ocr tesseract-ocr-sin tesseract-ocr-tam
```

**Windows**：从 [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) 安装 Tesseract（安装时勾选 Sinhala、Tamil 语言包），并在 `.env` 中指定路径：

```ini
NIC_OCR_TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

**关闭第二引擎**：设置 `NIC_OCR_NAME_OCR_ENGINE=none`。

### 精度说明与替代方案

Tesseract 对印刷体僧伽罗语/泰米尔语的精度一般，长姓名偶有个别字符识别错误。若需更高精度：

1. **调整 PSM**：`NIC_OCR_NAME_TESSERACT_PSM` 默认 `6`（假设单一文本块），可试 `7`（单行）或 `11/12`（稀疏文本）。
2. **云端 OCR API**：Google Cloud Vision 支持僧伽罗语/泰米尔语，质量最好，但需外网与密钥管理；可按 `ocr_engine.py` 的引擎接口封装替换第二引擎。

---

## 测试

```bash
# 运行全部测试（NIC + 还款凭条）
pytest -q

# 只跑还款凭条抽取测试
pytest -q tests/test_repayment_extractor.py

# 只跑 NIC 号码解析测试
pytest -q tests/test_nic_parser.py
```

还款凭条测试覆盖多银行/多版式的字段抽取规则（People's Bank、BOC、Commercial Bank CDM、Cash Credit Slip、HNB 等），新增版式时建议同步补充测试用例。

---

## 常见问题（FAQ）

**Q：（NIC）识别不出姓名/地址？**
A：这些字段依赖卡片上「Name / Address」等标签。若识别为空，先检查图片是否清晰、方向是否端正；可在 `extractor.py` 的标签列表里补充实际卡片使用的措辞（含僧伽罗语/泰米尔语标签）。长姓名跨行时，`_find_full_name` 会自动合并 `Name:` 标签正下方（水平落在取值列内、垂直距离不超过 2 倍行高）的至多 2 行字母续行；若卡片版式特殊导致合并遗漏，可调整 `_NAME_CONT_RE` / `_NON_NAME_KEYWORDS` 过滤规则。

**Q：（NIC）NIC 号码里混入了字母（如 0 识别成 O）？**
A：`_find_nic` 已内置常见混淆纠正（O→0、I→1、S→5 等）。若仍失败，说明图片过糊，建议提高图片分辨率或改善光照。

**Q：（NIC）出生日期比真实早/晚一天？**
A：多为 366 天日历偏移所致，见上文「已知偏移」，切换 `NIC_OCR_NIC_DAY_MODE=nic366` 后重启即可。

**Q：（NIC）校验位（最后一位）为何不做校验？**
A：斯里兰卡 NIC 校验位算法未公开，无法可靠校验，故仅透传不校验。

**Q：（NIC）name_sinhala / name_tamil 一直返回 null？**
A：见上文「多语言姓名」。Linux 裸机部署需先 `apt install tesseract-ocr tesseract-ocr-sin tesseract-ocr-tam`；Windows 需安装 Tesseract 并设置 `NIC_OCR_TESSERACT_CMD`。第二引擎不可用时服务会记录启动日志（「多语言姓名第二引擎未启用」），主流程不受影响。

**Q：（凭证）金额识别不对或返回 null？**
A：先用 `include_lines=true` 查看 OCR 原始文本，确认金额行是否被识别。OCR 常把千分位逗号识别成点（如 `5.300.00`），已内置兼容解析。若金额行完全未识别，需改善图片清晰度或在 `extractor.py` 中补充该行附近的标签匹配规则。

**Q：（凭证）现金存款凭条的纸币明细（deposit_breakdown）为空？**
A：手写张数 OCR 识别率低，代码不会默认补填 quantity=1（避免误导），而是留空并发出警告。若需精确明细，建议改善图片质量或在业务侧结合 amount 总额自行拆分。

**Q：（凭证）户名/账号识别错位？**
A：现金存款凭条优先取表单字段值，缺失时回退底部机打户名；账号用带校验的 `_extract_account` 提取（排除 OCR 噪声）。若仍错位，用 `include_lines=true` 检查标签与值的对应关系。
