"""
中东局势情报追踪器 - 后端 API
"""
import asyncio
import json
import os
import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件

import httpx
import feedparser
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── 大模型配置 ───────────────────────────────────────────────────────
LLM_API_KEY = os.environ.get("LLM_API_KEY")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen-plus")

# 根据模型名称自动判断默认的 API 端点
if "qwen" in LLM_MODEL.lower():
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
elif "gpt" in LLM_MODEL.lower():
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
else:
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL)

# 导入 OpenAI 客户端
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None
    print("警告: openai 库未安装，请运行: pip install openai")

app = FastAPI(title="局势情报追踪器 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 数据库配置 ───────────────────────────────────────────────────────
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "news.db"))
MAX_NEWS = 100

# 确保数据目录存在
data_dir = os.path.dirname(DB_PATH)
if data_dir and not os.path.exists(data_dir):
    os.makedirs(data_dir, exist_ok=True)
    print(f"[数据库] 创建数据目录: {data_dir}")


@contextmanager
def get_db():
    """数据库连接上下文管理器"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_db():
    """初始化数据库表"""
    with get_db() as conn:
        # 新闻表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                lang TEXT,
                title TEXT NOT NULL,
                title_zh TEXT,
                summary TEXT,
                summary_zh TEXT,
                url TEXT NOT NULL,
                published TEXT,
                fetched_at TEXT NOT NULL,
                intensity INTEGER DEFAULT 5,
                intensity_reason TEXT,
                category TEXT DEFAULT '战事进展',
                impact TEXT DEFAULT '中',
                tags TEXT,  -- JSON array
                analyzed BOOLEAN DEFAULT 0
            )
        """)

        # 烈度历史表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS intensity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                score REAL NOT NULL,
                time TEXT NOT NULL
            )
        """)

        # 创建索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_fetched ON news(fetched_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_category ON news(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_intensity ON news(intensity)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_intensity_time ON intensity_history(time)")

        print("[数据库] 初始化完成")


# 初始化数据库
init_db()


# ── 数据库操作函数 ───────────────────────────────────────────────────
def save_news(news_items: list[dict], skip_existing: bool = True):
    """保存新闻到数据库，可选跳过已存在的新闻"""
    with get_db() as conn:
        for item in news_items:
            try:
                # 如果设置跳过已存在，先检查
                if skip_existing:
                    cursor = conn.execute("SELECT id FROM news WHERE id = ?", (item["id"],))
                    if cursor.fetchone():
                        continue  # 已存在，跳过

                conn.execute("""
                    INSERT INTO news (
                        id, source, lang, title, title_zh, summary, summary_zh,
                        url, published, fetched_at, intensity, intensity_reason,
                        category, impact, tags, analyzed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item["id"],
                    item.get("source", ""),
                    item.get("lang", "en"),
                    item.get("title", ""),
                    item.get("title_zh", ""),
                    item.get("summary", ""),
                    item.get("summary_zh", ""),
                    item.get("url", ""),
                    item.get("published", ""),
                    item.get("fetched_at", datetime.now(timezone.utc).isoformat()),
                    item.get("intensity", 5),
                    item.get("intensity_reason", ""),
                    item.get("category", "战事进展"),
                    item.get("impact", "中"),
                    json.dumps(item.get("tags", [])),
                    item.get("analyzed", False)
                ))
            except Exception as e:
                print(f"保存新闻失败 {item.get('id')}: {e}")


def update_news_analysis(item: dict):
    """更新新闻的AI分析结果"""
    with get_db() as conn:
        conn.execute("""
            UPDATE news SET
                title_zh = ?,
                summary_zh = ?,
                intensity = ?,
                intensity_reason = ?,
                category = ?,
                impact = ?,
                tags = ?,
                analyzed = ?
            WHERE id = ?
        """, (
            item.get("title_zh", ""),
            item.get("summary_zh", ""),
            item.get("intensity", 5),
            item.get("intensity_reason", ""),
            item.get("category", "战事进展"),
            item.get("impact", "中"),
            json.dumps(item.get("tags", [])),
            item.get("analyzed", False),
            item["id"]
        ))


def get_news_from_db(category: Optional[str] = None, min_intensity: Optional[int] = None, limit: int = 50, analyzed_only: bool = True) -> list[dict]:
    """从数据库获取新闻"""
    with get_db() as conn:
        query = "SELECT * FROM news WHERE 1=1"
        params = []

        # 默认只返回已分析的新闻
        if analyzed_only:
            query += " AND analyzed = 1"

        if category:
            query += " AND category = ?"
            params.append(category)

        if min_intensity:
            query += " AND intensity >= ?"
            params.append(min_intensity)

        query += " ORDER BY fetched_at DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        news = []
        for row in rows:
            item = dict(row)
            # 解析 tags JSON
            try:
                item["tags"] = json.loads(item.get("tags", "[]")) if item.get("tags") else []
            except:
                item["tags"] = []
            item["analyzed"] = bool(item.get("analyzed", 0))
            news.append(item)

        return news


def get_news_count(category: Optional[str] = None, min_intensity: Optional[int] = None, analyzed_only: bool = True) -> int:
    """获取新闻数量"""
    with get_db() as conn:
        query = "SELECT COUNT(*) FROM news WHERE 1=1"
        params = []

        if analyzed_only:
            query += " AND analyzed = 1"

        if category:
            query += " AND category = ?"
            params.append(category)

        if min_intensity:
            query += " AND intensity >= ?"
            params.append(min_intensity)

        cursor = conn.execute(query, params)
        return cursor.fetchone()[0]


def get_unanalyzed_news(limit: int = 10) -> list[dict]:
    """获取未分析的新闻"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM news WHERE analyzed = 0 ORDER BY fetched_at DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        news = []
        for row in rows:
            item = dict(row)
            try:
                item["tags"] = json.loads(item.get("tags", "[]")) if item.get("tags") else []
            except:
                item["tags"] = []
            item["analyzed"] = False
            news.append(item)
        return news


def get_existing_news_ids() -> set:
    """获取所有已存在的新闻ID"""
    with get_db() as conn:
        cursor = conn.execute("SELECT id FROM news")
        return {row[0] for row in cursor.fetchall()}


def save_intensity_history(score: float):
    """保存烈度历史"""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO intensity_history (score, time) VALUES (?, ?)",
            (score, datetime.now(timezone.utc).isoformat())
        )

        # 只保留最近100条记录
        conn.execute("""
            DELETE FROM intensity_history
            WHERE id NOT IN (
                SELECT id FROM intensity_history ORDER BY time DESC LIMIT 100
            )
        """)


def get_intensity_history(limit: int = 48) -> list[dict]:
    """获取烈度历史"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM intensity_history ORDER BY time DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in reversed(rows)]


# ── 内存缓存（用于快速访问）──────────────────────────────────────────
news_store: list[dict] = []
intensity_history_cache: list[dict] = []


def load_data_from_db():
    """从数据库加载数据到内存缓存"""
    global news_store, intensity_history_cache
    news_store = get_news_from_db(limit=MAX_NEWS, analyzed_only=True)
    intensity_history_cache = get_intensity_history(48)
    print(f"[启动] 从数据库加载 {len(news_store)} 条已分析新闻")


# 启动时加载数据
load_data_from_db()

# ── RSS 新闻源配置 ─────────────────────────────────────────────────────
def load_rss_config():
    """从配置文件加载 RSS 源和关键词"""
    config_path = os.path.join(os.path.dirname(__file__), "rss_sources.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("sources", []), config.get("keywords", {})
    except Exception as e:
        print(f"加载 RSS 配置失败: {e}")
        return [], {}

RSS_SOURCES, KEYWORDS = load_rss_config()


def is_relevant(title: str, summary: str) -> bool:
    """
    严格冲突相关性判断：
    新闻必须与中东武装冲突、军事行动、地缘政治危机直接相关
    """
    title_lower = title.lower()
    text_lower = (title + " " + summary).lower()

    # 获取配置
    core_keywords = KEYWORDS.get("core", [])
    conflict_keywords = KEYWORDS.get("conflict", [])
    political_strict_keywords = KEYWORDS.get("political_strict", [])
    exclude_keywords = KEYWORDS.get("exclude", [])

    # 1. 排除检查 - 包含任何排除词直接过滤
    for exclude in exclude_keywords:
        if exclude in text_lower:
            return False

    # 2. 标题必须包含核心地域词（确保是关于中东的）
    has_core = any(core in title_lower for core in core_keywords)
    if not has_core:
        return False

    # 3. 标题必须包含冲突词或严格政治词（确保是关于冲突/危机的）
    has_conflict = any(conflict in title_lower for conflict in conflict_keywords)
    has_political = any(political in title_lower for political in political_strict_keywords)

    # 必须同时满足：是关于中东的 + 是关于冲突的
    return has_core and (has_conflict or has_political)


def make_id(url: str, title: str) -> str:
    return hashlib.md5((url + title).encode()).hexdigest()[:12]


async def fetch_rss() -> list[dict]:
    """拉取 RSS 并过滤相关新闻"""
    results = []
    async with httpx.AsyncClient(timeout=15) as client:
        for source in RSS_SOURCES:
            try:
                resp = await client.get(source["url"])
                feed = feedparser.parse(resp.text)
                for entry in feed.entries[:20]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    link = entry.get("link", "")
                    published = entry.get("published", "")
                    if is_relevant(title, summary):
                        results.append({
                            "id": make_id(link, title),
                            "source": source["name"],
                            "lang": source["lang"],
                            "title": title,
                            "summary": summary[:300],
                            "url": link,
                            "published": published,
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        })
            except Exception as e:
                print(f"RSS fetch error ({source['name']}): {e}")
    return results


async def analyze_with_llm(news_items: list[dict]) -> list[dict]:
    """使用配置的大模型进行批量分析：翻译 + 评分 + 分类"""
    if not news_items:
        return []

    api_key = LLM_API_KEY
    if not api_key:
        print("LLM API Key 未配置")
        for item in news_items:
            item["title_zh"] = item["title"]
            item["summary_zh"] = item["summary"][:100]
            item["intensity"] = 5
            item["intensity_reason"] = "API Key 未配置"
            item["category"] = "战事进展"
            item["impact"] = "中"
            item["tags"] = []
            item["analyzed"] = False
        return news_items

    # 构造批量分析 prompt
    news_text = "\n\n".join([
        f"[{i+1}] 来源: {n['source']}\n标题: {n['title']}\n摘要: {n['summary']}"
        for i, n in enumerate(news_items)
    ])

    prompt = f"""你是一个地缘政治情报分析专家，专注中东局势。

请对以下 {len(news_items)} 条新闻进行分析，返回 JSON 数组，每条对应一个对象，字段如下：
- index: 原序号(1开始)
- title_zh: 中文标题翻译（若已是中文则优化）
- summary_zh: 中文摘要（50字以内，精炼）
- intensity: 冲突烈度评分 1-10（1=无关冲突，10=极端升级，核战边缘）
- intensity_reason: 评分理由（20字以内）
- category: 分类，从以下选一个：["战事进展","外交动态","市场反应","人道主义","军事部署","舆论动态"]
- impact: 对市场影响，从以下选一个：["高","中","低","无"]
- tags: 关键词标签数组，最多3个

重要规则：
1. 烈度(intensity)和影响(impact)必须一致：
   - intensity≥7 → impact必须是"高"
   - intensity 5-6 → impact应该是"中"或"高"
   - intensity≤4 → impact应该是"低"或"无"
2. 只有重大军事升级或极端事件才给高影响

评分标准：
1-2: 常规外交声明，无实质影响
3-4: 局部冲突或紧张表态
5-6: 重大军事行动或外交破裂
7-8: 大规模军事升级，多国卷入
9-10: 极端升级，可能引发区域战争

新闻内容：
{news_text}

只返回 JSON 数组，不要任何解释。格式：
[{{"index":1,"title_zh":"...","summary_zh":"...","intensity":5,"intensity_reason":"...","category":"战事进展","impact":"中","tags":["以色列","空袭","加沙"]}}]"""

    try:
        # 使用统一的 OpenAI 兼容接口
        if not AsyncOpenAI:
            raise Exception("openai 库未安装")

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=LLM_BASE_URL
        )

        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是一个地缘政治情报分析专家，专注中东局势。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        raw = response.choices[0].message.content.strip()

        # 清理可能的 markdown
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        analyses = json.loads(raw)

        # 合并到原始新闻
        analysis_map = {a["index"]: a for a in analyses}
        for i, item in enumerate(news_items):
            a = analysis_map.get(i + 1, {})
            item["title_zh"] = a.get("title_zh", item["title"])
            item["summary_zh"] = a.get("summary_zh", item["summary"][:100])
            item["intensity"] = a.get("intensity", 5)
            item["intensity_reason"] = a.get("intensity_reason", "")
            item["category"] = a.get("category", "战事进展")
            item["impact"] = a.get("impact", "中")
            item["tags"] = a.get("tags", [])
            item["analyzed"] = True

            # 修正不一致的评分：低烈度新闻不能有高影响
            if item["intensity"] <= 4 and item["impact"] == "高":
                item["impact"] = "中"
            elif item["intensity"] <= 2 and item["impact"] in ["高", "中"]:
                item["impact"] = "低"
            # 高烈度新闻必须有中高影响
            elif item["intensity"] >= 7 and item["impact"] in ["低", "无"]:
                item["impact"] = "中"

    except Exception as e:
        print(f"LLM 分析错误: {e}")
        for item in news_items:
            item["title_zh"] = item["title"]
            item["summary_zh"] = item["summary"][:100]
            item["intensity"] = 5
            item["intensity_reason"] = f"分析失败: {str(e)[:20]}"
            item["category"] = "战事进展"
            item["impact"] = "中"
            item["tags"] = []
            item["analyzed"] = False

    return news_items




def calc_overall_intensity(items: list[dict]) -> dict:
    """计算综合烈度"""
    if not items:
        return {"score": 0, "level": "平静", "trend": "→"}

    recent = [n for n in items if n.get("intensity")]
    if not recent:
        return {"score": 0, "level": "平静", "trend": "→"}

    # 最近20条加权平均
    scores = [n["intensity"] for n in recent[:20]]
    avg = sum(scores) / len(scores)
    max_score = max(scores)
    weighted = avg * 0.4 + max_score * 0.6  # 偏向峰值

    level = "极端危机" if weighted >= 9 else \
            "高度紧张" if weighted >= 7 else \
            "中度紧张" if weighted >= 5 else \
            "轻度紧张" if weighted >= 3 else "基本平静"

    # 趋势：对比历史
    trend = "→"
    history = get_intensity_history(2)
    if len(history) >= 2:
        prev = history[-2]["score"]
        if weighted > prev + 0.5:
            trend = "↑"
        elif weighted < prev - 0.5:
            trend = "↓"

    return {"score": round(weighted, 1), "level": level, "trend": trend}


# ── 定时刷新任务 ────────────────────────────────────────────────────
async def refresh_news():
    global news_store, intensity_history_cache
    print(f"[{datetime.now()}] 开始刷新新闻...")
    raw = await fetch_rss()

    # 从数据库获取已存在的ID进行去重
    existing_ids = get_existing_news_ids()
    new_items = [n for n in raw if n["id"] not in existing_ids]
    print(f"  抓取 {len(raw)} 条，新增 {len(new_items)} 条")

    if new_items:
        # 第一步：只保存新新闻的基础信息（未分析状态）
        # 这样即使AI分析失败，新闻也不会丢失
        for item in new_items:
            item["analyzed"] = False
        save_news(new_items, skip_existing=True)
        print(f"  已保存 {len(new_items)} 条新新闻")

        # 第二步：只对新增的新闻进行AI分析
        to_analyze = new_items[:10]  # MVP 每次最多分析10条
        print(f"  开始AI分析 {len(to_analyze)} 条新闻...")

        analyzed = await analyze_with_llm(to_analyze)

        # 第三步：更新分析结果到数据库
        for item in analyzed:
            update_news_analysis(item)
        print(f"  AI分析完成")

        # 更新内存缓存
        news_store = get_news_from_db(limit=MAX_NEWS, analyzed_only=True)

        # 记录烈度历史
        intensity = calc_overall_intensity(news_store)
        save_intensity_history(intensity["score"])
        intensity_history_cache = get_intensity_history(48)
    else:
        print("  没有新新闻")


async def scheduler():
    while True:
        try:
            await refresh_news()
        except Exception as e:
            print(f"Scheduler error: {e}")
        await asyncio.sleep(600)  # 每10分钟刷新


@app.on_event("startup")
async def startup():
    # 启动调度器
    asyncio.create_task(scheduler())

    # 启动后台分析任务（持续处理未分析的新闻）
    asyncio.create_task(background_analyzer())


async def background_analyzer():
    """后台持续分析未处理的新闻"""
    await asyncio.sleep(10)  # 等待系统启动完成

    while True:
        try:
            unanalyzed = get_unanalyzed_news(5)  # 每次处理5条
            if unanalyzed:
                print(f"[后台分析] 发现 {len(unanalyzed)} 条未分析新闻，开始分析...")
                analyzed = await analyze_with_llm(unanalyzed)
                for item in analyzed:
                    update_news_analysis(item)
                # 刷新内存缓存
                global news_store
                news_store = get_news_from_db(limit=MAX_NEWS, analyzed_only=True)
                print(f"[后台分析] 完成 {len(analyzed)} 条新闻分析")
            else:
                print("[后台分析] 没有待分析的新闻")
        except Exception as e:
            print(f"[后台分析] 错误: {e}")

        # 每30秒检查一次
        await asyncio.sleep(30)


# ── API 路由 ────────────────────────────────────────────────────────
@app.get("/api/news")
async def get_news(
    category: Optional[str] = None,
    min_intensity: Optional[int] = None,
    limit: int = 50,
    include_unanalyzed: bool = False  # 是否包含未分析的新闻
):
    items = get_news_from_db(category=category, min_intensity=min_intensity, limit=limit, analyzed_only=not include_unanalyzed)
    total = get_news_count(category=category, min_intensity=min_intensity, analyzed_only=not include_unanalyzed)
    unanalyzed_count = len(get_unanalyzed_news(1000)) if not include_unanalyzed else 0
    return {"news": items, "total": total, "unanalyzed_pending": unanalyzed_count}


@app.get("/api/news/unanalyzed")
async def get_unanalyzed_news_api(limit: int = 50):
    """获取未分析的新闻列表（调试用）"""
    items = get_unanalyzed_news(limit)
    return {
        "news": items,
        "total": len(items),
        "message": "这些新闻正在等待AI分析"
    }


@app.get("/api/intensity")
async def get_intensity():
    # 从内存缓存获取最新新闻计算当前烈度
    intensity = calc_overall_intensity(news_store)
    # 从历史记录获取历史数据
    history = get_intensity_history(24)
    return {
        "current": intensity,
        "history": history,
    }


@app.get("/api/stats")
async def get_stats():
    with get_db() as conn:
        # 总新闻数（已分析）
        cursor = conn.execute("SELECT COUNT(*) FROM news WHERE analyzed = 1")
        total_analyzed = cursor.fetchone()[0]

        # 未分析新闻数
        cursor = conn.execute("SELECT COUNT(*) FROM news WHERE analyzed = 0")
        total_unanalyzed = cursor.fetchone()[0]

        # 分类统计（只统计已分析的）
        cursor = conn.execute("SELECT category, COUNT(*) as count FROM news WHERE analyzed = 1 GROUP BY category")
        categories = {row["category"]: row["count"] for row in cursor.fetchall()}

        # 影响统计（只统计已分析的）
        cursor = conn.execute("SELECT impact, COUNT(*) as count FROM news WHERE analyzed = 1 GROUP BY impact")
        impacts = {row["impact"]: row["count"] for row in cursor.fetchall()}

        # 最新更新时间
        cursor = conn.execute("SELECT MAX(fetched_at) as last_updated FROM news")
        row = cursor.fetchone()
        last_updated = row["last_updated"] if row else None

    return {
        "total": total_analyzed,
        "unanalyzed": total_unanalyzed,
        "categories": categories,
        "impacts": impacts,
        "last_updated": last_updated,
    }


@app.post("/api/refresh")
async def manual_refresh(background_tasks: BackgroundTasks):
    background_tasks.add_task(refresh_news)
    return {"message": "刷新任务已启动"}


@app.post("/api/analyze-pending")
async def analyze_pending(background_tasks: BackgroundTasks):
    """手动触发分析未处理的新闻"""
    async def do_analyze():
        unanalyzed = get_unanalyzed_news(10)
        if unanalyzed:
            print(f"[手动分析] 开始分析 {len(unanalyzed)} 条新闻...")
            analyzed = await analyze_with_llm(unanalyzed)
            for item in analyzed:
                update_news_analysis(item)
            global news_store
            news_store = get_news_from_db(limit=MAX_NEWS, analyzed_only=True)
            print(f"[手动分析] 完成 {len(analyzed)} 条新闻分析")
        else:
            print("[手动分析] 没有待分析的新闻")

    background_tasks.add_task(do_analyze)
    return {"message": "分析任务已启动", "pending_count": len(get_unanalyzed_news(100))}


@app.get("/health")
async def health():
    with get_db() as conn:
        # 已分析新闻数
        cursor = conn.execute("SELECT COUNT(*) FROM news WHERE analyzed = 1")
        analyzed_count = cursor.fetchone()[0]
        # 未分析新闻数
        cursor = conn.execute("SELECT COUNT(*) FROM news WHERE analyzed = 0")
        unanalyzed_count = cursor.fetchone()[0]

    return {
        "status": "ok",
        "news_count": analyzed_count,
        "unanalyzed_count": unanalyzed_count,
        "db_path": DB_PATH,
    }
