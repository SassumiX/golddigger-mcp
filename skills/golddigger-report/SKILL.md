---
name: golddigger-report
description: "Golddigger风格B2B客户画像雷达报告生成器。当用户说'生成GD报告'、'出客户画像'、'雷达图报告'、'挖客户报告'时启用。从Golddigger.gold API或B2B Lead Engine获取数据，生成带雷达图的Word报告文档。"
---

# Golddigger 客户画像雷达报告生成器

## Overview

一键生成 Golddigger 风格的 B2B 客户画像雷达图 Word 报告。自动完成：数据采集 → 客户筛选评分 → 雷达图生成 → Word 文档排版输出。

**支持两种数据源：**
1. Golddigger.gold API（免费版数据库为空时自动降级）
2. B2B Lead Engine 网络搜索（兜底方案，始终可用）

**输出：** 带 4 张雷达图（1 张综合对比 + 3 张分客户）+ 专业 Word 文档

## 触发条件

以下任一关键词触发：
- "生成GD报告"
- "出客户画像"
- "雷达图报告"
- "挖客户报告"
- "Golddigger报告"
- "客户画像雷达图"

## 输入参数

| 参数 | 必须 | 说明 |
|------|------|------|
| `company_url` | ✅ | 客户官网 URL（如 cnpulk.com） |
| `product_desc` | ✅ | 产品描述文本 |
| `target_count` | ❌ | 目标客户数量，默认 3 |
| `api_key` | ❌ | Golddigger API Key（不提供则用已存储的） |

## Workflow

### Step 1：数据采集

```
输入 → 产品分析 → Golddigger API 调用
                        ↓
               API 返回 >0 ?
               ↓ Yes         ↓ No (免费版 db_rows=0)
          使用 GD 数据    B2B Lead Engine 网络搜索兜底
                        ↓
              获取 3 个真实采购商数据
              （公司名、国家、类型、规模、采购需求、联系方式）
```

**Golddigger API 调用规范：**
- Base URL: `https://golddigger.gold`
- 注册接口: `POST /api/tenants/register` → `{email, password}` → 返回 `api_key`
- 知识库上传: `POST /api/knowledge` → `{"content": 产品描述文本, "source_type": "text"}`
- 客户搜索: `GET /api/leads/search?q={keyword}&limit={n}` → `{"count", "leads": [...]}`
- 健康检查: `GET /health` → `{"db_rows": 数字}`（db_rows=0 = 免费版空库）

**Golddigger 免费版已知限制：**
- `db_rows: 0`，搜索永远返回 0 结果
- 知识库上传可提取关键词但不填充客户库
- 3 条 demo lead 是付费 SUPER 用户专属

### Step 2：客户评分（雷达六维）

每个客户按以下维度打分（满分 100）：

| 维度 | 说明 | 评分依据 |
|------|------|---------|
| 🏢 公司规模 | 规模越大越稳定 | 上市/大型集团 > 中型 > 小型 |
| 💰 采购能力 | 支付能力和预算 | 自有矿/持续消耗 > 偶发采购 |
| ⏰ 需求紧迫度 | 近期换供应商可能性 | 并购/扩张期 > 稳定供应商 |
| 🔄 复购潜力 | 耗材属性和复购频率 | 钻头等耗材 > 一次性设备 |
| 📍 地域匹配 | 与目标市场契合度 | 核心市场 > 边缘市场 |
| 📱 触达便利 | 联系方式和沟通难度 | 有负责人邮箱 > 只能官网联系 |

**评分标准参考（可按行业调整）：**

```
高匹配（+20分）: 公司官网明确有采购负责人邮箱+电话
中匹配（+10分）: 公司官网有通用联系表单
低匹配（+5分）:  只能通过 LinkedIn 或中间人联系
无匹配（+0分）:  无法找到任何联系方式
```

### Step 3：雷达图生成

使用 `matplotlib` 生成 4 张 PNG 图片：

```
/workspace/radar_charts/
├── comparison_radar.png     # 三客户叠加对比雷达图
├── buyer_1_radar.png        # 客户1独立雷达图
├── buyer_2_radar.png        # 客户2独立雷达图
└── buyer_3_radar.png       # 客户3独立雷达图
```

**雷达图规范：**
- 尺寸: 5.5×5.5 inch，dpi=150
- 背景色: `#F9FAFB`
- 网格: 5层（20/40/60/80/100），虚线，色值 `#E5E7EB`
- 填充: 半透明 alpha=0.15
- 数据点: 圆形，白色填充，彩色边框
- 字体: DejaVu Sans（英文标签）
- 图例: 右上角，多客户叠加图显示

**matplotlib 脚本模板（`/workspace/.skills/golddigger-report/templates/gen_radar.py`）：**
```python
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def draw_radar(axes_labels, values, filename, color='#2563EB', title=''):
    n = len(axes_labels)
    angles = np.linspace(0, 2*np.pi, n, endpoint=False).tolist()
    angles_full = angles + angles[:1]
    v_full = values + [values[0]]

    fig, ax = plt.subplots(figsize=(5.5, 5.5), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor('#F9FAFB')
    ax.set_facecolor('#F9FAFB')

    # 网格
    for level in [20, 40, 60, 80, 100]:
        ax.plot(angles_full, [level]*len(angles_full), color='#E5E7EB', lw=0.5, ls='--')
    ax.plot(angles_full, [100]*len(angles_full), color='#D1D5DB', lw=1)

    # 填充+折线
    ax.fill(angles_full, v_full, color=color, alpha=0.15)
    ax.plot(angles_full, v_full, color=color, lw=2.5, marker='o',
            markersize=6, markerfacecolor='white', markeredgecolor=color)

    ax.set_xticks(angles); ax.set_xticklabels(axes_labels, size=9, color='#374151')
    ax.set_yticks([20,40,60,80,100]); ax.set_yticklabels(['20','40','60','80','100'], size=7, color='#9CA3AF')
    ax.set_ylim(0, 110); ax.set_theta_offset(np.pi/2); ax.set_theta_direction(-1)
    ax.spines['polar'].set_visible(False)
    if title: ax.set_title(title, size=13, fontweight='bold', color='#1A1A2E', pad=20)
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight', facecolor='#F9FAFB')
    plt.close()
```

### Step 4：Word 文档生成

使用 `python-docx` 生成最终报告：

```
/workspace/{company}_buyer_radar_report.docx
```

**Word 文档结构：**
```
第1页：封面
  - 公司名称 + Logo色标题
  - 元信息（产品/市场/工具/日期）
  - 分隔线装饰

第2页：核心发现
  - 数据来源说明
  - 综合评分概览
  - 【综合对比雷达图】(嵌入式PNG)

第3页：三客户对比表
  - 8维度横向对比表格

第4-7页：客户详情（×3）
  每个客户：
  - 公司名称 + 国家旗帜 + 综合评分
  - 基础档案表格（公司名/类型/规模/总部/官网/行业定位/采购角色）
  - 【客户独立雷达图】(嵌入式PNG)
  - 雷达六维评分条（ASCII条形图）
  - 联系方式列表
  - 英文切入话术（斜体）

末尾：行动优先级表 + 地域分布 + 工具说明
```

**python-docx 关键规范：**
- 页面: A4，左右边距 2.5cm
- 表头行: 深色背景 `#1A1A2E`，白色字体
- 斑马条纹: 奇数行 `#F9FAFB`，偶数行 `#FFFFFF`
- 颜色系统:
  - 主色: `#C9812A`（金色，用于标题）
  - 强调红: `#DC2626`（HOT LEAD标签）
  - 强调蓝: `#2563EB`（雷达图基准色）
  - 深灰: `#1A1A2E`（正文）
  - 中灰: `#6B7280`（辅助文字）
  - 浅灰: `#333333`（表格正文）
- 雷达条: `█`（填充）+ `░`（空白）+ 分数数字，色值 `#2563EB`
- 字体: Arial（英文）+ Microsoft YaHei（中文）

**Python 脚本模板（`/workspace/.skills/golddigger-report/templates/gen_report.py`）：**
见 `/workspace/gen_final_report.py` 的完整实现。

## 输出文件

| 文件 | 说明 |
|------|------|
| `{company}_buyer_radar_report.docx` | 最终 Word 报告 |
| `/workspace/radar_charts/*.png` | 雷达图图片（中间产物） |

## 代码文件清单

```
/workspace/.skills/golddigger-report/
├── SKILL.md                          ← 本文件
├── templates/
│   ├── gen_radar.py                  ← 雷达图生成脚本模板
│   └── gen_report.py                 ← Word报告生成脚本模板（参考 /workspace/gen_final_report.py）
└── README.md                         ← 使用说明
```

## 使用示例

### 基本调用
```
用户：帮我生成cnpulk.com的客户画像雷达报告
助理：
  1. 读取产品信息 → cnpulk.com DTH钻头/凿岩工具
  2. 调用 Golddigger API → db_rows=0，免费版空库
  3. 降级到 B2B Lead Engine 搜索
  4. 找到 3 个采购商：Afrimat/White Rock/Bin Harkil
  5. 生成雷达图 × 4
  6. 生成 Word 文档
  → 交付：普兰卡钎具_客户画像雷达报告.docx
```

### 高级调用（提供 API Key）
```
用户：用Golddigger API Key xxxx生成xxx.com的报告
助理：
  1. 用提供的 Key 调用 /health 检查
  2. 若 db_rows > 0 → 用真实 GD 客户库
  3. 若 db_rows = 0 → 降级搜索
  ...
```

## 已知限制

1. **Golddigger 免费版**：`db_rows=0`，搜索永远返回 0，付费 SUPER 套餐（¥499+/月）后可用
2. **雷达图中文**：matplotlib 默认字体不支持中文，用英文标签替代（`plt.rcParams['font.family'] = 'DejaVu Sans'`）
3. **Word 中文字体**：依赖系统安装 Microsoft YaHei，无则回退到 Arial

## 依赖

```bash
pip install python-docx matplotlib numpy
# Golddigger API 调用无需额外依赖（urllib 内置）
```
