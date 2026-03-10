import { useState, useEffect, useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

// ── 工具函数 ──────────────────────────────────────────────────────
const intensityColor = (score) => {
  if (score >= 9) return "#ff1a1a";
  if (score >= 7) return "#ff6b00";
  if (score >= 5) return "#ffd600";
  if (score >= 3) return "#00e5ff";
  return "#4cff91";
};

const intensityBg = (score) => {
  if (score >= 9) return "rgba(255,26,26,0.12)";
  if (score >= 7) return "rgba(255,107,0,0.12)";
  if (score >= 5) return "rgba(255,214,0,0.10)";
  if (score >= 3) return "rgba(0,229,255,0.08)";
  return "rgba(76,255,145,0.08)";
};

const categoryIcon = (cat) => ({
  "战事进展": "⚔️",
  "外交动态": "🤝",
  "市场反应": "📈",
  "人道主义": "🕊️",
  "军事部署": "🎯",
  "舆论动态": "📡",
}[cat] || "📌");

const impactBadge = (impact) => ({
  "高": { color: "#ff4444", bg: "rgba(255,68,68,0.15)", label: "高影响" },
  "中": { color: "#ff9900", bg: "rgba(255,153,0,0.15)", label: "中影响" },
  "低": { color: "#00bcd4", bg: "rgba(0,188,212,0.15)", label: "低影响" },
  "无": { color: "#666", bg: "rgba(102,102,102,0.15)", label: "无影响" },
}[impact] || { color: "#666", bg: "rgba(102,102,102,0.15)", label: impact });

function timeAgo(dateStr) {
  try {
    const d = new Date(dateStr);
    const diff = (Date.now() - d) / 1000;
    if (diff < 60) return "刚刚";
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
    return `${Math.floor(diff / 86400)}天前`;
  } catch { return ""; }
}

// ── 组件 ─────────────────────────────────────────────────────────

function IntensityGauge({ score, level, trend }) {
  const color = intensityColor(score);
  const pct = (score / 10) * 100;

  return (
    <div style={{
      background: "linear-gradient(135deg, #0d0d0d 0%, #111418 100%)",
      border: `1px solid ${color}33`,
      borderRadius: 16,
      padding: "28px 32px",
      boxShadow: `0 0 40px ${color}22, inset 0 1px 0 rgba(255,255,255,0.04)`,
      position: "relative",
      overflow: "hidden",
    }}>
      {/* 背景光晕 */}
      <div style={{
        position: "absolute", top: -40, right: -40,
        width: 160, height: 160,
        borderRadius: "50%",
        background: `radial-gradient(circle, ${color}20 0%, transparent 70%)`,
        pointerEvents: "none",
      }} />

      <div style={{ color: "#888", fontSize: 11, letterSpacing: 3, textTransform: "uppercase", marginBottom: 12 }}>
        综合烈度指数
      </div>

      <div style={{ display: "flex", alignItems: "flex-end", gap: 12, marginBottom: 16 }}>
        <div style={{
          fontSize: 72, fontWeight: 900, lineHeight: 1,
          color, fontFamily: "'Courier New', monospace",
          textShadow: `0 0 30px ${color}88`,
          letterSpacing: -2,
        }}>
          {score.toFixed(1)}
        </div>
        <div style={{ paddingBottom: 12 }}>
          <div style={{ fontSize: 28, lineHeight: 1 }}>{trend}</div>
        </div>
      </div>

      {/* 进度条 */}
      <div style={{ height: 4, background: "#1a1a1a", borderRadius: 2, marginBottom: 12, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${pct}%`,
          background: `linear-gradient(90deg, ${color}88, ${color})`,
          borderRadius: 2,
          transition: "width 1s ease",
          boxShadow: `0 0 8px ${color}`,
        }} />
      </div>

      <div style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: "4px 12px", borderRadius: 20,
        background: intensityBg(score),
        border: `1px solid ${color}44`,
        color, fontSize: 13, fontWeight: 600,
      }}>
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, boxShadow: `0 0 6px ${color}` }} />
        {level}
      </div>
    </div>
  );
}

function StatsBar({ stats }) {
  const cats = stats?.categories || {};
  const total = stats?.total || 0;

  return (
    <div style={{
      display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12,
    }}>
      {[
        { label: "总情报数", value: total, icon: "📊", color: "#00e5ff" },
        { label: "高影响事件", value: stats?.impacts?.["高"] || 0, icon: "⚡", color: "#ff4444" },
        { label: "战事进展", value: cats["战事进展"] || 0, icon: "⚔️", color: "#ff9900" },
      ].map(({ label, value, icon, color }) => (
        <div key={label} style={{
          background: "#0d0d0d",
          border: "1px solid #1e1e1e",
          borderRadius: 12, padding: "16px 20px",
          borderTop: `2px solid ${color}44`,
        }}>
          <div style={{ fontSize: 20, marginBottom: 4 }}>{icon}</div>
          <div style={{ fontSize: 28, fontWeight: 800, color, fontFamily: "'Courier New', monospace" }}>{value}</div>
          <div style={{ fontSize: 11, color: "#555", letterSpacing: 1 }}>{label}</div>
        </div>
      ))}
    </div>
  );
}

function CategoryFilter({ selected, onChange, counts }) {
  const cats = ["全部", "战事进展", "外交动态", "军事部署", "市场反应", "人道主义", "舆论动态"];
  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
      {cats.map(cat => {
        const active = selected === cat || (cat === "全部" && !selected);
        const count = cat === "全部" ? Object.values(counts).reduce((a, b) => a + b, 0) : (counts[cat] || 0);
        return (
          <button key={cat}
            onClick={() => onChange(cat === "全部" ? null : cat)}
            style={{
              padding: "6px 14px", borderRadius: 20, border: "1px solid",
              borderColor: active ? "#00e5ff" : "#222",
              background: active ? "rgba(0,229,255,0.12)" : "transparent",
              color: active ? "#00e5ff" : "#555",
              fontSize: 12, cursor: "pointer",
              fontFamily: "inherit",
              transition: "all 0.2s",
            }}
          >
            {categoryIcon(cat)} {cat} {count > 0 && <span style={{ opacity: 0.6 }}>({count})</span>}
          </button>
        );
      })}
    </div>
  );
}

function NewsCard({ item, index }) {
  const color = intensityColor(item.intensity);
  const badge = impactBadge(item.impact);
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      onClick={() => setExpanded(!expanded)}
      style={{
        background: expanded ? "#0f1115" : "#0a0a0a",
        border: "1px solid",
        borderColor: expanded ? `${color}33` : "#161616",
        borderLeft: `3px solid ${color}`,
        borderRadius: 10,
        padding: "16px 20px",
        cursor: "pointer",
        transition: "all 0.2s",
        animation: `fadeSlideIn 0.4s ease ${Math.min(index * 0.05, 0.5)}s both`,
      }}
    >
      {/* 顶部行 */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{
          fontSize: 11, color: "#444", letterSpacing: 1, flexShrink: 0
        }}>{item.source}</span>
        <span style={{ color: "#222", fontSize: 10 }}>·</span>
        <span style={{
          fontSize: 11, padding: "2px 8px", borderRadius: 10,
          background: badge.bg, color: badge.color,
        }}>{badge.label}</span>
        <span style={{
          fontSize: 11, padding: "2px 8px", borderRadius: 10,
          background: "#111", color: "#555",
        }}>{categoryIcon(item.category)} {item.category}</span>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "#888", display: "flex", alignItems: "center", gap: 4 }}>
          <span>🕐</span>
          <span>{(item.published || item.fetched_at) ? new Date(item.published || item.fetched_at).toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            timeZone: 'Asia/Shanghai'
          }) : '--'}</span>
        </span>
        {/* 烈度徽章 */}
        <span style={{
          fontSize: 13, fontWeight: 800, color,
          background: intensityBg(item.intensity),
          padding: "2px 10px", borderRadius: 10,
          fontFamily: "'Courier New', monospace",
          border: `1px solid ${color}33`,
          flexShrink: 0,
        }}>{item.intensity}</span>
      </div>

      {/* 标题 */}
      <div style={{ fontSize: 15, fontWeight: 600, color: "#e8e8e8", lineHeight: 1.4, marginBottom: 6 }}>
        {item.title_zh || item.title}
      </div>

      {/* 摘要 */}
      <div style={{ fontSize: 13, color: "#555", lineHeight: 1.6 }}>
        {item.summary_zh || item.summary}
      </div>

      {/* 展开详情 */}
      {expanded && (
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid #1a1a1a" }}>
          {item.intensity_reason && (
            <div style={{ fontSize: 12, color: "#666", marginBottom: 10 }}>
              <span style={{ color: color, marginRight: 4 }}>▶</span>
              烈度评估：{item.intensity_reason}
            </div>
          )}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
            {item.tags?.map(tag => (
              <span key={tag} style={{
                fontSize: 11, padding: "2px 8px", borderRadius: 10,
                background: "#111", color: "#555", border: "1px solid #1e1e1e",
              }}>#{tag}</span>
            ))}
          </div>
          <a href={item.url} target="_blank" rel="noreferrer"
            onClick={e => e.stopPropagation()}
            style={{
              fontSize: 12, color: "#00e5ff", textDecoration: "none",
              display: "inline-flex", alignItems: "center", gap: 4,
            }}>
            🔗 查看原文 →
          </a>
        </div>
      )}
    </div>
  );
}

function LoadingState() {
  return (
    <div style={{ textAlign: "center", padding: "60px 0", color: "#333" }}>
      <div style={{
        fontSize: 32, marginBottom: 16,
        animation: "pulse 1.5s infinite",
      }}>📡</div>
      <div style={{ fontSize: 14, letterSpacing: 2 }}>正在获取情报...</div>
    </div>
  );
}

// ── 主应用 ────────────────────────────────────────────────────────
export default function App() {
  const [news, setNews] = useState([]);
  const [intensity, setIntensity] = useState({ current: { score: 0, level: "加载中", trend: "→" } });
  const [stats, setStats] = useState({});
  const [category, setCategory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);

  const ITEMS_PER_PAGE = 10;
  const MAX_PAGES = 5;

  const fetchAll = useCallback(async () => {
    try {
      const [newsRes, intensityRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/api/news?limit=50${category ? `&category=${encodeURIComponent(category)}` : ""}`),
        fetch(`${API_BASE}/api/intensity`),
        fetch(`${API_BASE}/api/stats`),
      ]);

      if (!newsRes.ok) throw new Error("API 连接失败，请确认后端已启动");

      const [newsData, intensityData, statsData] = await Promise.all([
        newsRes.json(), intensityRes.json(), statsRes.json()
      ]);

      // 按发布时间排序（最新的在前）
      const sortedNews = (newsData.news || []).sort((a, b) => {
        const timeA = a.published ? new Date(a.published).getTime() : 0;
        const timeB = b.published ? new Date(b.published).getTime() : 0;
        return timeB - timeA;
      });

      setNews(sortedNews);
      setIntensity(intensityData);
      setStats(statsData);
      setLastUpdate(new Date());
      setError(null);
      setCurrentPage(1); // 刷新后重置到第一页
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await fetch(`${API_BASE}/api/refresh`, { method: "POST" });
      await new Promise(r => setTimeout(r, 3000));
      await fetchAll();
    } finally {
      setRefreshing(false);
    }
  };

  // 分页计算
  const totalPages = Math.min(Math.ceil(news.length / ITEMS_PER_PAGE), MAX_PAGES);
  const paginatedNews = news.slice((currentPage - 1) * ITEMS_PER_PAGE, currentPage * ITEMS_PER_PAGE);

  // 分页组件
  function Pagination() {
    if (totalPages <= 1) return null;

    const pages = [];
    for (let i = 1; i <= totalPages; i++) {
      pages.push(
        <button
          key={i}
          onClick={() => setCurrentPage(i)}
          style={{
            padding: "6px 12px",
            borderRadius: 6,
            border: "1px solid",
            borderColor: currentPage === i ? "#00e5ff" : "#222",
            background: currentPage === i ? "rgba(0,229,255,0.12)" : "transparent",
            color: currentPage === i ? "#00e5ff" : "#666",
            fontSize: 13,
            cursor: "pointer",
            fontFamily: "inherit",
            transition: "all 0.2s",
          }}
        >
          {i}
        </button>
      );
    }

    return (
      <div style={{
        display: "flex",
        justifyContent: "center",
        gap: 8,
        marginTop: 20,
        padding: "16px 0",
        borderTop: "1px solid #1a1a1a"
      }}>
        <button
          onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
          disabled={currentPage === 1}
          style={{
            padding: "6px 12px",
            borderRadius: 6,
            border: "1px solid #222",
            background: "transparent",
            color: currentPage === 1 ? "#333" : "#888",
            fontSize: 13,
            cursor: currentPage === 1 ? "not-allowed" : "pointer",
            fontFamily: "inherit",
          }}
        >
          ← 上一页
        </button>
        {pages}
        <button
          onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
          disabled={currentPage === totalPages}
          style={{
            padding: "6px 12px",
            borderRadius: 6,
            border: "1px solid #222",
            background: "transparent",
            color: currentPage === totalPages ? "#333" : "#888",
            fontSize: 13,
            cursor: currentPage === totalPages ? "not-allowed" : "pointer",
            fontFamily: "inherit",
          }}
        >
          下一页 →
        </button>
      </div>
    );
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "#080808",
      color: "#e0e0e0",
      fontFamily: "'PingFang SC', 'Microsoft YaHei', -apple-system, sans-serif",
    }}>
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse { 0%,100% { opacity: 0.4; } 50% { opacity: 1; } }
        @keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #0a0a0a; }
        ::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 2px; }
      `}</style>

      {/* 顶部导航 */}
      <header style={{
        borderBottom: "1px solid #111",
        background: "rgba(8,8,8,0.95)",
        backdropFilter: "blur(10px)",
        position: "sticky", top: 0, zIndex: 100,
        padding: "0 24px",
      }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", display: "flex", alignItems: "center", height: 56, gap: 16 }}>
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: "linear-gradient(135deg, #ff1a1a, #ff6b00)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 16, boxShadow: "0 0 16px #ff1a1a44",
            }}>🎯</div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: 1 }}>局势情报追踪器</div>
              <div style={{ fontSize: 10, color: "#444", letterSpacing: 2 }}>CONFLICT INTELLIGENCE</div>
            </div>
          </div>

          {/* 实时指示灯 */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: 16 }}>
            <span style={{
              width: 7, height: 7, borderRadius: "50%",
              background: error ? "#ff4444" : "#4cff91",
              boxShadow: error ? "0 0 6px #ff4444" : "0 0 6px #4cff91",
              animation: error ? "none" : "blink 2s infinite",
            }} />
            <span style={{ fontSize: 11, color: "#444" }}>
              {error ? "连接断开" : `实时监测中 · ${lastUpdate ? lastUpdate.toLocaleTimeString("zh-CN") : "--"}`}
            </span>
          </div>

          <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              style={{
                padding: "6px 16px", borderRadius: 8,
                border: "1px solid #1e1e1e",
                background: refreshing ? "#111" : "transparent",
                color: refreshing ? "#444" : "#888",
                fontSize: 12, cursor: refreshing ? "not-allowed" : "pointer",
                fontFamily: "inherit",
                transition: "all 0.2s",
              }}
            >
              {refreshing ? "⟳ 刷新中..." : "⟳ 手动刷新"}
            </button>
          </div>
        </div>
      </header>

      {/* 主体内容 */}
      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "24px" }}>
        {error && (
          <div style={{
            background: "rgba(255,68,68,0.1)", border: "1px solid rgba(255,68,68,0.3)",
            borderRadius: 10, padding: "14px 20px", marginBottom: 20,
            fontSize: 13, color: "#ff6666",
          }}>
            ⚠️ {error}
            <div style={{ fontSize: 12, color: "#ff4444aa", marginTop: 4 }}>
              请确认后端已启动：cd backend && uvicorn main:app --reload
            </div>
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 20, alignItems: "start" }}>

          {/* 左侧边栏 */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16, position: "sticky", top: 76 }}>
            <IntensityGauge
              score={intensity.current?.score || 0}
              level={intensity.current?.level || "加载中"}
              trend={intensity.current?.trend || "→"}
            />
            <StatsBar stats={stats} />

            {/* 分类统计 */}
            <div style={{
              background: "#0d0d0d", border: "1px solid #1a1a1a",
              borderRadius: 12, padding: "16px 20px",
            }}>
              <div style={{ fontSize: 11, color: "#555", letterSpacing: 2, marginBottom: 12 }}>情报分类分布</div>
              {Object.entries(stats.categories || {}).map(([cat, count]) => {
                const pct = stats.total ? (count / stats.total * 100) : 0;
                return (
                  <div key={cat} style={{ marginBottom: 8 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#666", marginBottom: 3 }}>
                      <span>{categoryIcon(cat)} {cat}</span>
                      <span>{count}</span>
                    </div>
                    <div style={{ height: 3, background: "#111", borderRadius: 2, overflow: "hidden" }}>
                      <div style={{
                        height: "100%", width: `${pct}%`,
                        background: "linear-gradient(90deg, #00e5ff88, #00e5ff)",
                        borderRadius: 2,
                      }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 右侧新闻流 */}
          <div>
            <div style={{ marginBottom: 16 }}>
              <CategoryFilter
                selected={category}
                onChange={setCategory}
                counts={stats.categories || {}}
              />
            </div>

            {loading ? <LoadingState /> : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {paginatedNews.length === 0 ? (
                  <div style={{ textAlign: "center", padding: "60px 0", color: "#333", fontSize: 14 }}>
                    暂无情报数据，点击"手动刷新"获取最新内容
                  </div>
                ) : (
                  paginatedNews.map((item, i) => (
                    <NewsCard key={item.id} item={item} index={i} />
                  ))
                )}
                <Pagination />
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
