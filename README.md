# GoldDigger MCP Server

**DiggerKit-C+ · 工厂 Agent 一击接入挖客**

[![MCP Server](https://img.shields.io/badge/MCP-Server-green)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Data Sovereignty](https://img.shields.io/badge/Data-Local%20Only-blue)](https://golddigger.gold)

> B2B Lead Intelligence API — 让任何 MCP 客户端（Claude / Cursor / Cline / 你的 SI Agent）接入 GoldDigger 挖客。

**两个版本，同一份数据主权承诺：**

| 版本 | 语言 | 依赖 | 工具 | 状态 |
|---|---|---|---|---|
| **v2.0** | Node.js ≥18 | **零依赖** | 4 个（3 只读 + 1 受控写） | ✅ **推荐** |
| v1 | Python ≥3.9 | matplotlib / python-docx 等 | 6 个（含 3 个纯本地工具） | 已归档，仍可用 |

---

## v2.1（Node.js，推荐）

零依赖、单文件、`npx` 即跑。

### 安装 —— 3 种方式，都不需要 npm 账号

**A · zip 直下（推荐 · 国内最稳）**
```bash
curl -LO https://golddigger.gold/static/diggerkit-mcp-v2.1.0.zip
unzip diggerkit-mcp-v2.1.0.zip
cd golddigger-mcp-v2.1.0
node node/index.js
```
官方站直下，不依赖 GitHub，国内速度最快。GitHub Release 快照同版本：
<https://github.com/SassumiX/golddigger-mcp/releases/download/v2.1.0/golddigger-mcp-v2.1.0.zip>

**B · npm 安装**
```bash
npm install git+https://github.com/SassumiX/golddigger-mcp.git
GOLDDIGGER_API_KEY=gd_xxxxx npx golddigger-mcp
```

> ⚠️ **npm 会把 `git+https://` 悄悄改成 SSH 去 clone**（`hosted-git-info` 的偏好），
> 你没配 SSH key 就会报 `Permission denied (publickey)` —— 看着像权限问题，其实是网络问题。
> 报错时先加这一行再试：
> ```bash
> git config --global http.version HTTP/1.1
> ```
> （HTTP/2 在部分网络/代理下会被中途切断。HTTPS 通了 npm 就不会回落 SSH。）
>
> 💡 `npx github:SassumiX/golddigger-mcp` 这种简写在部分 npm 版本上会**静默失败**
> （`npm exec` 处理 git specifier 时 exit 128，无任何报错输出）。
> 用上面的 `npm install` + `npx <bin>` 写法。
>
> 国内网络下 **A 方式（zip）更稳**，推荐优先选 A。

**C · GitHub Release zip（固定版本快照，离线可用）**
```bash
curl -LO https://github.com/SassumiX/golddigger-mcp/releases/download/v2.1.0/golddigger-mcp-v2.1.0.zip
unzip golddigger-mcp-v2.1.0.zip
cd golddigger-mcp-v2.1.0
node node/index.js
```

### 接入 MCP 客户端

```json
{
  "mcpServers": {
    "golddigger": {
      "command": "npx",
      "args": ["golddigger-mcp"],
      "env": {
        "GOLDDIGGER_API_KEY": "gd_xxxxx"
      }
    }
  }
}
```

已下载 zip 的把 `command` 换成 `node`、`args` 指向 `node/index.js` 即可。

### 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `GOLDDIGGER_API_KEY` | 是 | 你的 API Key，在 <https://golddigger.gold/ui/> 取 |
| `GOLDDIGGER_BASE_URL` | 否 | 默认 `https://golddigger.gold`，自建部署时改 |
| `GOLDDIGGER_TIMEOUT_MS` | 否 | 单次请求超时，默认 20000 |

API Key 前缀决定角色：`gds_` = 供应商（挖客），`gdb_` = 买家。越权返回 `KEY_ROLE_MISMATCH`（403）。

### v2.1 工具集

| 工具 | 说明 | 数据流 |
|---|---|---|
| `check_readiness` | 一次报出所有阻塞项：key 有效性 + 后端连通 + 配额 | 外部调用（不消耗配额） |
| `check_quota` | 剩余配额、套餐、重置时间 | 外部调用（只读，不消耗配额） |
| `check_answerable` | 覆盖度预检：这次计划挖 N 条，够不够 | 本地 + `/api/quota` |
| `search_leads` | 按产品关键词 + 国家 + 行业检索潜在买家 | 外部调用，**每次 1 配额** |

### 两个配额池（2026-11-11 起）

| 池 | 覆盖 | 单位 | 额度 |
|---|---|---|---|
| API 池 | `search_leads` | 次 | Starter 20 / Pro 100 / Premium 500 / Whitelabel 无限 |
| 挖客行动池 | DiggerKit C / C+ | Quota | 每天 1000 Quota = **10 次挖客行动** |

两池互不占用，各自 UTC 00:00 重置。Whitelabel 豁免挖客池。
`check_quota` 会直接给一句人话总结。

### 工作流

```
check_readiness  → 确认 key / 后端 / 配额都正常
      ↓
check_quota      → 看还剩多少次
      ↓
check_answerable → 这次计划挖 N 条，够不够
      ↓
search_leads     → 逐次挖（每次 1 配额，挖到就转化，不要囤着等以后）
```

**配额不对称**：搜索花 1 次配额，外联（写邮件 / WhatsApp）花 0 次。
「挖 10 条只跟 3 条」是浪费额度 —— 挖 5 条全部跟完才是正常节奏。

---

## v1（Python，已归档）

功能更全 —— 除检索外还有**三个纯本地工具**（本地评分 / 雷达图报告 / 外联草稿），数据完全不出本机。
完整文档见 [`README.v1-python.md`](README.v1-python.md)。

```bash
git clone https://github.com/SassumiX/golddigger-mcp.git
cd golddigger-mcp
pip install -r requirements.txt
export GOLDDIGGER_API_KEY="gd_your_key_here"
python3 server.py --transport stdio
```

MCP Registry manifest：[`server.v1-python.json`](server.v1-python.json)（原 `server.json`）。

---

## 数据主权

- ✅ **Token 客户自购** —— 模型开销走客户自己的账户，我们不代付
- ✅ **数据客户自抓** —— 线索返回给调用方即止，我们不留存
- ✅ **0 抽佣** —— 不抽流水
- ✅ **不代找客户** —— 只把你的关键词变成检索请求，结果来自公开 B2B 数据源
- ✅ **不保证认证** —— 检索到的只是线索，不是已验证的合规身份

---

## 为什么没发 npm registry

npm registry 需要 npm 账号 + 发布 token。没有可用凭证时，
硬把包装到别人账号下会造成「谁维护、谁收 telemetry、谁能下架」的归属混乱。

所以官方分发固定走这三条路，**三条指向同一份源码**（`node/index.js`），
不存在「npm 版和官网版不一样」的问题：

1. **npm install git+https://…**（实测可用）—— 无 npm 账号依赖，版本跟 Git tag 走
2. **GitHub Release zip** —— 固定版本快照，离线可用
3. **官方站 `/static/*.zip`** —— 国内直连，走 Caddy 显式 MIME 路由

---

## License

MIT
