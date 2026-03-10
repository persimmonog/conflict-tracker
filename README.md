# 🎯 局势情报追踪器 MVP

AI 驱动的地缘政治情报聚合分析工具，实时追踪全球新闻、自动翻译、AI 烈度评分。

## 📁 项目结构

```
conflict-tracker/
├── .gitignore               # Git 忽略配置
├── backend/
│   ├── .gitignore           # 后端忽略配置
│   ├── main.py              # FastAPI 后端主程序
│   ├── requirements.txt     # Python 依赖
│   └── .env.example         # 环境变量模板
├── frontend/
│   ├── .gitignore           # 前端忽略配置
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       └── App.jsx          # React 主界面
├── deploy/                  # 部署脚本
│   ├── aliyun-deploy.sh     # 阿里云一键部署
│   ├── backup.sh            # 数据备份脚本
│   └── nginx.conf           # Nginx 配置
├── data/                    # SQLite 数据库目录（持久化）
│   ├── .gitignore           # 忽略数据库文件但保留目录
│   └── .gitkeep             # 保留空目录
├── docker-compose.yml       # Docker 部署配置
├── DEPLOY.md                # Docker 部署说明
└── ALIYUN_DEPLOY.md         # 阿里云 ECS 部署指南
```

## 🚀 快速启动

### 方式一：阿里云 ECS 部署（生产推荐）

一键部署到阿里云服务器：

```bash
# SSH 登录到你的阿里云 ECS
ssh root@YOUR_IP

# 一键部署
curl -fsSL https://raw.githubusercontent.com/your-username/conflict-tracker/main/deploy/aliyun-deploy.sh | sudo bash
```

详细指南：[ALIYUN_DEPLOY.md](ALIYUN_DEPLOY.md)

---

### 方式二：Docker 部署（本地/测试）

```bash
# 1. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入你的阿里云百炼平台 API Key

# 2. 启动服务
docker-compose up -d

# 3. 访问
# 前端: http://localhost
# 后端API: http://localhost:8000
```

详细说明见 [DEPLOY.md](DEPLOY.md)

---

### 方式二：本地开发

### 第一步：配置 API Key

```bash
cd backend
cp .env.example .env
# 编辑 .env，填入你的阿里云百炼平台 API Key
# 获取地址: https://bailian.console.aliyun.com/
```

### 第二步：启动后端

```bash
cd backend

# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate      # macOS/Linux
# venv\Scripts\activate       # Windows

# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn main:app --reload --port 8000
```

后端启动后访问：http://localhost:8000/docs（API 文档）

### 第三步：启动前端

```bash
# 新开一个终端窗口
cd frontend
npm install
npm run dev
```

前端访问：http://localhost:5173

---

## 🔧 API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/news` | GET | 获取新闻列表，支持 `?category=战事进展&min_intensity=5` |
| `/api/intensity` | GET | 获取当前烈度 + 历史趋势 |
| `/api/stats` | GET | 获取统计数据 |
| `/api/refresh` | POST | 手动触发刷新 |
| `/health` | GET | 健康检查 |

## ⚙️ 配置说明

### 大模型配置 (LLM)

使用 OpenAI 兼容接口统一调用各大模型：

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `LLM_API_KEY` | API Key | - |
| `LLM_MODEL` | 模型名称 | `qwen-plus` |
| `LLM_BASE_URL` | API 端点（可选） | 根据模型自动判断 |

**自动判断 API 端点：**
- 模型名包含 `qwen` → 阿里云百炼兼容端点
- 模型名包含 `gpt` → OpenAI 官方端点

**阿里云百炼 (默认):**
```bash
LLM_API_KEY=sk-xxx
LLM_MODEL=qwen-plus
# 自动使用: https://dashscope.aliyuncs.com/compatible-mode/v1
```

**OpenAI:**
```bash
LLM_API_KEY=sk-xxx
LLM_MODEL=gpt-3.5-turbo
# 自动使用: https://api.openai.com/v1
```

**自定义端点（用于代理或第三方服务）：**
```bash
LLM_API_KEY=your-key
LLM_MODEL=any-model
LLM_BASE_URL=https://your-custom-endpoint.com/v1
```

### 其他配置

- **刷新频率**：默认每 10 分钟自动刷新（`main.py` 中 `asyncio.sleep(600)`）
- **新闻源**：在 `RSS_SOURCES` 列表中增减
- **关键词过滤**：修改 `KEYWORDS` 列表
- **每次分析数量**：MVP 限制每次 10 条，可在 `refresh_news()` 中调整

## 🗺️ 后续功能规划（Phase 2）

- [x] ~~数据持久化存储~~ ✅ SQLite 已完成
- [ ] 接入更多新闻源（半岛电视台中文、法新社等）
- [ ] 烈度历史折线图可视化
- [ ] 原油/黄金价格关联显示
- [ ] 邮件/Telegram 推送告警
