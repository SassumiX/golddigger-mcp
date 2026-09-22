---
name: golddigger-report
description: "Golddigger风格B2B客户画像雷达报告生成器。当用户说'生成GD报告'、'出客户画像'、'雷达图报告'、'挖客户报告'时启用。从Golddigger.gold API或B2B Lead Engine获取数据，生成带雷达图的Word报告文档。"
---

# Golddigger 客户画像雷达报告生成器

## Overview

一键生成 Golddigger 风格的 B2B 客户画像雷达图 Word 报告。完整链路：

```
用户输入产品关键词
    ↓
Agent 调用 DIGGERKIT MCP 搜索客户
    ↓
拿到客户数据（公司名/国家/类型/采购需求/联系方式）
    ↓
Agent 执行本 skill → 生成雷达图 + Word 报告
    ↓
用户下载 {公司名}_buyer_radar_report.docx
```

**支持两种触发方式：**
1. **直接调用 API**：`POST /generate-report`（HTTP 服务模式）
2. **Agent 执行脚本**：本地运行 `gd_report_api.py --cli`

## 触发条件

以下任一关键词触发：
- "生成GD报告"
- "出客户画像"
- "雷达图报告"
- "挖客户报告"
- "Golddigger报告"
- "客户画像雷达图"

---

## Agent 调用指南（DIGGERKIT MCP 集成）

### 方式一：HTTP API 模式（推荐生产环境）

**启动服务：**
```bash
cd skills/golddigger-report/templates
pip install flask python-docx matplotlib numpy
python gd_report_api.py --port 8080
```

**Agent 调用：**
```bash
# 1. 调用 Golddigger 搜索客户
curl -X POST https://golddigger.gold/api/leads/search \
  -H "X-API-KEY: {YOUR_KEY}" \
  -d '{"keyword": "DTH drill bits Africa", "limit": 3}'

# 2. 把结果 POST 到报告 API（如果 GD 返回空，自动用示例数据）
curl -X POST http://localhost:8080/generate-report \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "cnpulk.com",
    "product_desc": "DTH drill bits, rock drilling tools",
    "buyers": [
      {"name": "Afrimat Limited", "country": "南非", "type": "上市矿业集团",
       "industry": "Mining", "has_contact": true, "scale": "1,001-5,000人"},
      {"name": "White Rock Minerals", "country": "阿联酋", "type": "私营采石场",
       "industry": "Quarry", "has_contact": true, "scale": "100-500人"},
      {"name": "Bin Harkil Group", "country": "沙特", "type": "多元化集团",
       "industry": "Construction", "has_contact": false, "scale": "444人"}
    ]
  }' \
  --output report.docx
```

**仅评分模式（不生成报告）：**
```bash
curl -X POST http://localhost:8080/score-only \
  -H "Content-Type: application/json" \
  -d '{"buyers": [{"name": "Acme Corp", "country": "南非", "industry": "Mining", "has_contact": true}]}'
```

### 方式二：Agent 本地执行脚本

```bash
# 传入客户数据，直接生成报告
python gd_report_api.py \
  --cli \
  --company "cnpulk.com" \
  --product "DTH drill bits, rock drilling tools, button bits"
```

**Agent 自动构建 buyers 数据示例：**
```python
# Agent 根据 DIGGERKIT 搜索结果，构造 buyers 数组
buyers = [
    {
        "name": "Afrimat Limited",
        "country": "南非",
        "type": "JSE上市矿业集团",
        "scale": "1,001-5,000人",
        "industry": "Mining & Quarrying",
        "buyer_role": "Contract Mining总监 Pierre D.",
        "purchase_needs": "DTH钻头76-165mm，持续消耗",
        "has_contact": True,
        "website": "www.afrimat.co.za",
        "contacts": ["pierre.dutoit@afrimat.co.za · +27 82 411 7475"],
        "outreach": "We offer 20-30% cost savings on DTH bits vs. current suppliers."
    },
    # ... 2 more buyers
]

# 调用 generate_report()
from gd_report_api import generate_report
output_path = generate_report(
    company_name="cnpulk.com",
    product_desc="DTH drill bits, rock drilling tools",
    buyers=buyers,
    output_dir="/tmp/gd_reports"
)
print(f"报告: {output_path}")
```

---

## 客户数据格式（buyers 数组）

每个 buyer 对象字段：

| 字段 | 必须 | 说明 |
|------|------|------|
| `name` | ✅ | 公司名 |
| `country` | ✅ | 国家（中文或英文） |
| `type` | ❌ | 公司类型（上市/私营/集团等） |
| `scale` | ❌ | 规模（人数/营收） |
| `industry` | ✅ | 行业（用于评分） |
| `buyer_role` | ❌ | 采购负责人职位 |
| `purchase_needs` | ❌ | 采购需求描述 |
| `has_contact` | ✅ | 是否有直接联系方式（用于评分） |
| `website` | ❌ | 公司官网 |
| `contacts` | ❌ | 联系方式列表（email/电话） |
| `outreach` | ❌ | 切入话术（英文，推荐25词以内） |
| `note` | ❌ | 备注（如"扩张期"/"NEOM项目"→影响紧迫度评分） |

---

## 六维评分模型

Agent 搜索结果自动评分，无需人工干预：

| 维度 | 基础分 | 加分规则 |
|------|--------|---------|
| 🏢 公司规模 | 50 | 上市+20，集团+15，中型+10 |
| 💰 采购能力 | 50 | 自有矿+20，持续消耗+15 |
| ⏰ 需求紧迫度 | 50 | 并购/扩张+25，NEOM/Vision2030+20 |
| 🔄 复购潜力 | 50 | 矿业/采石场+20，耗材属性+10 |
| 📍 地域匹配 | 50 | 非洲/中东/东南亚核心市场+30 |
| 📱 触达便利 | 50 | 有负责人邮箱+25，有官网+10 |

---

## 输出文件

```
/tmp/gd_reports/
├── {company}_buyer_radar_YYYYMMDD.docx   ← 主报告
└── radar_charts/
    ├── comparison_radar.png               ← 三客户对比雷达图
    ├── buyer_1_radar.png                 ← 客户1独立雷达图
    ├── buyer_2_radar.png
    └── buyer_3_radar.png
```

---

## 依赖

```bash
pip install flask python-docx matplotlib numpy
# 或一键
pip install -r skills/golddigger-report/templates/requirements.txt
```

---

## 代码文件

```
skills/golddigger-report/
├── SKILL.md                        ← 本文件
├── README.md
└── templates/
    ├── gd_report_api.py           ← 核心脚本（HTTP API + CLI）
    ├── gen_radar.py               ← 独立雷达图模板
    ├── gen_report.py              ← 独立Word报告模板
    └── requirements.txt           ← 依赖列表
```

---

## 快速验证（5分钟跑通）

```bash
# 1. 克隆仓库
git clone https://github.com/SassumiX/golddigger-mcp.git
cd golddigger-mcp

# 2. 安装依赖
pip install flask python-docx matplotlib numpy

# 3. 生成示例报告（无需Golddigger账号）
python skills/golddigger-report/templates/gd_report_api.py \
  --cli --company "YourCompany.com" --product "Your products"

# 4. 查看输出
ls /tmp/gd_reports/
```
