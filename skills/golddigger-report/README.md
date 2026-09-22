# Golddigger Report Skill

一键生成 Golddigger 风格的 B2B 客户画像雷达图 Word 报告。

## 快速开始

### 在 Mavis Agent 中使用

```bash
# 触发 skill
/给我生成cnpulk.com的客户画像雷达报告
/golddigger-report cnpulk.com DTH钻头出口非洲
```

### 独立运行

```bash
cd skills/golddigger-report/templates

# 1. 安装依赖
pip install python-docx matplotlib numpy

# 2. 修改 buyers_data 变量填入你的客户数据
# 3. 运行
python gen_report.py
# 输出: xxx_buyer_radar_report.docx
```

## 输入参数

| 参数 | 必须 | 说明 |
|------|------|------|
| `company_url` | ✅ | 客户官网 URL |
| `product_desc` | ✅ | 产品描述文本 |
| `target_count` | ❌ | 目标客户数量，默认 3 |
| `api_key` | ❌ | Golddigger API Key |

## 输出

```
{company}_buyer_radar_report.docx
```
包含：
- 封面（元信息：产品/市场/工具/日期）
- 核心发现 + 综合对比雷达图
- 三客户横向对比表
- 3 × 客户详情页（含独立雷达图 + 档案表 + 联系方式 + 切入话术）
- 行动优先级表
- 地域分布图

## 雷达六维评分维度

| 维度 | 说明 |
|------|------|
| 🏢 公司规模 | 规模越大越稳定 |
| 💰 采购能力 | 支付能力和预算 |
| ⏰ 需求紧迫度 | 近期换供应商可能性 |
| 🔄 复购潜力 | 耗材属性和复购频率 |
| 📍 地域匹配 | 与目标市场契合度 |
| 📱 触达便利 | 联系方式和沟通难度 |

## 颜色规范

| 用途 | 色值 |
|------|------|
| 主色（金） | `#C9812A` |
| 深色 | `#1A1A2E` |
| HOT红 | `#DC2626` |
| 强调蓝 | `#2563EB` |
| 暖橙 | `#F59E0B` |
| 中灰 | `#6B7280` |

## 依赖

```txt
python-docx>=1.0.0
matplotlib>=3.7.0
numpy>=1.24.0
```
