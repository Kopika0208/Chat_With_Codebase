import { useState, useEffect, useCallback } from "react";

const API_BASE = "/api";
const NAV_ITEMS = ["Dashboard", "Query", "Call Graph", "Onboarding"];
const ONBOARDING_TABS = ["Overview", "Entry/Exit Points", "Roadmap", "File Structure", "Navigation", "Code Health", "Contributions"];

// ─── API Helpers ──────────────────────────────────────────────────────────────

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error ${res.status}`);
  }
  return res.json();
}

function useApi(path, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const isRepoValid = path && !path.includes("/repos/null") && !path.includes("/repos/undefined") && !path.includes("/repos/") ? false : true;

  const reload = useCallback(() => {
    if (!path || path.includes("/repos/null") || path.includes("/repos/undefined")) {
      setData(null);
      setLoading(false);
      setError("Please select a repository.");
      return;
    }

    setLoading(true);
    setError(null);
    apiFetch(path)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [path]);

  useEffect(() => { reload(); }, [reload, ...deps]);
  return { data, loading, error, reload };
}

// ─── Shared Components ───────────────────────────────────────────────────────

function Navbar({ page, setPage }) {
  return (
    <nav style={{
      background: "#0a0f1e", borderBottom: "1px solid rgba(255,255,255,0.07)",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "0 32px", height: 52, position: "sticky", top: 0, zIndex: 100,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#fff", fontWeight: 700, fontSize: 16, fontFamily: "'Fira Code', monospace" }}>
        <span style={{ color: "#4f8ef7", fontSize: 18 }}>&lt;/&gt;</span> RepoMind
      </div>
      <div style={{ display: "flex", gap: 28 }}>
        {NAV_ITEMS.map(item => (
          <button key={item} onClick={() => setPage(item)} style={{
            background: "none", border: "none", cursor: "pointer",
            color: page === item ? "#fff" : "rgba(255,255,255,0.5)",
            fontWeight: page === item ? 700 : 400, fontSize: 14, padding: "4px 0",
            borderBottom: page === item ? "2px solid #4f8ef7" : "2px solid transparent",
            fontFamily: "inherit", transition: "color 0.2s"
          }}>{item}</button>
        ))}
      </div>
    </nav>
  );
}

function Badge({ children, color = "#4f8ef7" }) {
  const bg = color === "green" ? "rgba(34,197,94,0.15)" : color === "yellow" ? "rgba(234,179,8,0.15)" : color === "red" ? "rgba(239,68,68,0.15)" : "rgba(79,142,247,0.15)";
  const text = color === "green" ? "#4ade80" : color === "yellow" ? "#facc15" : color === "red" ? "#f87171" : "#4f8ef7";
  return (
    <span style={{ background: bg, color: text, fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 20, border: `1px solid ${text}33` }}>
      {children}
    </span>
  );
}

function Card({ children, style = {}, onClick }) {
  return (
    <div onClick={onClick} style={{
      background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: 12, padding: 20, ...style
    }}>
      {children}
    </div>
  );
}

function StatCard({ icon, value, label }) {
  return (
    <Card style={{ flex: 1, minWidth: 140 }}>
      <div style={{ fontSize: 22, marginBottom: 8 }}>{icon}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: "#fff" }}>{value}</div>
      <div style={{ fontSize: 13, color: "rgba(255,255,255,0.45)", marginTop: 4 }}>{label}</div>
    </Card>
  );
}

function Loader({ text = "Loading..." }) {
  return (
    <div style={{ textAlign: "center", padding: 60, color: "rgba(255,255,255,0.4)" }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
      {text}
    </div>
  );
}

function ErrorBox({ message, onRetry }) {
  return (
    <div style={{ textAlign: "center", padding: 40, color: "#f87171" }}>
      <div style={{ fontSize: 28, marginBottom: 12 }}>⚠️</div>
      <div style={{ marginBottom: 16 }}>{message}</div>
      {onRetry && (
        <button onClick={onRetry} style={{
          background: "#4f8ef7", border: "none", color: "#fff", padding: "8px 20px",
          borderRadius: 8, cursor: "pointer", fontWeight: 600, fontSize: 13,
        }}>Retry</button>
      )}
    </div>
  );
}

function RepoDropdown({ repos, selected, onSelect }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <button onClick={() => setOpen(!open)} style={{
        background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.12)",
        color: "#fff", padding: "8px 16px", borderRadius: 8, cursor: "pointer",
        fontSize: 14, display: "flex", alignItems: "center", gap: 8, minWidth: 240,
      }}>
        {selected || "Select repo"} <span style={{ marginLeft: "auto" }}>▾</span>
      </button>
      {open && (
        <div style={{
          position: "absolute", top: "100%", left: 0, background: "#0f1628",
          border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8, zIndex: 50,
          minWidth: 260, marginTop: 4, overflow: "hidden",
        }}>
          {(repos || []).map(r => {
            const name = typeof r === "string" ? r : r.name;
            return (
              <div key={name} onClick={() => { onSelect(name); setOpen(false); }} style={{
                padding: "10px 16px", cursor: "pointer", fontSize: 14, color: "#fff",
                background: selected === name ? "#4f8ef7" : "transparent",
              }}
                onMouseEnter={e => { if (selected !== name) e.target.style.background = "rgba(255,255,255,0.05)"; }}
                onMouseLeave={e => { if (selected !== name) e.target.style.background = "transparent"; }}
              >{name}</div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Landing Page ─────────────────────────────────────────────────────────────

function LandingPage({ setPage }) {
  const features = [
    { icon: "🧠", title: "AI-Powered Queries", desc: "Ask questions in natural language and get intelligent answers with relevant code snippets" },
    { icon: "🔀", title: "Call Graph Visualization", desc: "Interactive visualization of function relationships and code dependencies" },
    { icon: "💚", title: "Code Health Analysis", desc: "Comprehensive health scoring with actionable refactoring recommendations" },
    { icon: "🔍", title: "Smart Navigation", desc: "Intelligent symbol search and navigation through complex codebases" },
    { icon: "⚡", title: "Instant Onboarding", desc: "Get up to speed quickly with automated project insights and learning roadmaps" },
    { icon: "</>", title: "Multi-Language Support", desc: "Supports Python, JavaScript, TypeScript, Java, C++, Go, Rust, and more" },
  ];
  const steps = [
    { n: 1, title: "Add Repository", desc: "Connect your GitHub repository or upload local code" },
    { n: 2, title: "AI Analysis", desc: "Our AI analyzes your codebase and builds knowledge graphs" },
    { n: 3, title: "Ask & Explore", desc: "Query your code in natural language and explore insights" },
  ];

  return (
    <div style={{ fontFamily: "'Inter', sans-serif", color: "#fff", background: "#060b18", minHeight: "100vh" }}>
      <nav style={{ background: "#060b18", borderBottom: "1px solid rgba(255,255,255,0.07)", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 40px", height: 52 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700, fontSize: 16, fontFamily: "'Fira Code', monospace" }}>
          <span style={{ color: "#4f8ef7" }}>&lt;/&gt;</span> RepoMind
        </div>
        <button onClick={() => setPage("Dashboard")} style={{ background: "#4f8ef7", color: "#fff", border: "none", borderRadius: 8, padding: "8px 20px", cursor: "pointer", fontWeight: 600, fontSize: 14 }}>Get Started</button>
      </nav>
      <div style={{ textAlign: "center", padding: "80px 40px 60px" }}>
        <h1 style={{ fontSize: 52, fontWeight: 800, margin: 0, lineHeight: 1.1 }}>Understand Any Codebase</h1>
        <h2 style={{ fontSize: 52, fontWeight: 800, color: "#4f8ef7", margin: "8px 0 24px" }}>In Minutes</h2>
        <p style={{ color: "rgba(255,255,255,0.5)", fontSize: 16, maxWidth: 540, margin: "0 auto 36px", lineHeight: 1.6 }}>
          AI-powered code analysis that helps you explore, understand, and navigate complex codebases with natural language queries and intelligent insights.
        </p>
        <button onClick={() => setPage("Dashboard")} style={{ background: "#4f8ef7", color: "#fff", border: "none", borderRadius: 8, padding: "14px 32px", cursor: "pointer", fontWeight: 600, fontSize: 16 }}>Start Exploring</button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, maxWidth: 960, margin: "0 auto 72px", padding: "0 32px" }}>
        {features.map(f => (<Card key={f.title}><div style={{ fontSize: 20, marginBottom: 10 }}>{f.icon}</div><div style={{ fontWeight: 600, marginBottom: 6 }}>{f.title}</div><div style={{ color: "rgba(255,255,255,0.45)", fontSize: 13, lineHeight: 1.5 }}>{f.desc}</div></Card>))}
      </div>
      <div style={{ textAlign: "center", padding: "0 32px 80px" }}>
        <h2 style={{ fontSize: 28, fontWeight: 700, margin: "0 0 8px" }}>How It Works</h2>
        <p style={{ color: "rgba(255,255,255,0.45)", margin: "0 0 48px" }}>Get started in three simple steps</p>
        <div style={{ display: "flex", justifyContent: "center", gap: 48 }}>
          {steps.map(s => (
            <div key={s.n} style={{ maxWidth: 200, textAlign: "center" }}>
              <div style={{ width: 44, height: 44, borderRadius: "50%", background: "#4f8ef7", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 18, margin: "0 auto 16px" }}>{s.n}</div>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>{s.title}</div>
              <div style={{ color: "rgba(255,255,255,0.45)", fontSize: 13 }}>{s.desc}</div>
            </div>
          ))}
        </div>
      </div>
      <div style={{ textAlign: "center", padding: 16, borderTop: "1px solid rgba(255,255,255,0.07)", color: "rgba(255,255,255,0.3)", fontSize: 13 }}>Built with ❤️ for developers • Powered by AI</div>
    </div>
  );
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

function Dashboard({ setPage, setSelectedRepo, onReposChanged }) {
  const { data, loading, error, reload } = useApi("/repos");

  if (loading) return <Loader text="Loading repositories..." />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const repos = data?.repos || [];
  const totalFunctions = repos.reduce((s, r) => s + (r.functions || 0), 0);
  const avgHealth = repos.length ? Math.round(repos.reduce((s, r) => s + (r.health || 0), 0) / repos.length) : 0;

  return (
    <div style={{ padding: "40px 48px", maxWidth: 1100, margin: "0 auto" }}>
      <h1 style={{ fontSize: 32, fontWeight: 700, margin: "0 0 4px", color: "#fff" }}>Dashboard</h1>
      <p style={{ color: "rgba(255,255,255,0.4)", margin: "0 0 32px", fontSize: 14 }}>Manage and explore your code repositories</p>

      <div style={{ display: "flex", gap: 16, marginBottom: 40 }}>
        <StatCard icon="📁" value={repos.length} label="Total Repositories" />
        <StatCard icon="⚡" value={totalFunctions.toLocaleString()} label="Total Functions" />
        <StatCard icon="💚" value={avgHealth || "–"} label="Avg Health Score" />
        <StatCard icon="📈" value={repos.filter(r => r.has_vectorstore).length} label="Indexed" />
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ fontSize: 20, fontWeight: 600, margin: 0, color: "#fff" }}>Your Repositories</h2>
        <IngestButton onComplete={() => { reload(); onReposChanged?.(); }} />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 40 }}>
        {repos.map(r => (
          <Card key={r.name} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", gap: 16, alignItems: "flex-start", flex: 1 }}>
              <div style={{ fontSize: 20, marginTop: 2 }}>📁</div>
              <div>
                <div style={{ fontWeight: 600, color: "#fff", marginBottom: 4 }}>{r.name}</div>
                <div style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", marginBottom: 12 }}>
                  {r.files} files • {r.functions} functions • {(r.languages || []).join(", ") || "Unknown"}
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  {["Query", "Call Graph", "Onboarding"].map(action => (
                    <button key={action} onClick={() => { setSelectedRepo(r.name); setPage(action); }} style={{
                      background: "#4f8ef7", border: "none", color: "#fff",
                      padding: "5px 14px", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600,
                    }}>{action}</button>
                  ))}
                  <DeleteRepoButton
                    repoName={r.name}
                    onDeleted={() => {
                      setSelectedRepo(current => current === r.name ? null : current);
                      reload();
                      onReposChanged?.();
                    }}
                  />
                </div>
              </div>
            </div>
            <div style={{ textAlign: "right", minWidth: 100 }}>
              <Badge color={r.has_vectorstore ? "green" : "yellow"}>
                {r.has_vectorstore ? "Indexed" : "Partial"}
              </Badge>
            </div>
          </Card>
        ))}
        {repos.length === 0 && (
          <div style={{ textAlign: "center", padding: 40, color: "rgba(255,255,255,0.4)" }}>
            No repositories ingested yet. Add one above to get started.
          </div>
        )}
      </div>
    </div>
  );
}

function DeleteRepoButton({ repoName, onDeleted }) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(null);

  async function handleDelete() {
    const confirmed = window.confirm(
      `Delete "${repoName}" from the dashboard?\n\nThis will permanently remove its folders from /data/${repoName} and /evaluation/${repoName}.`
    );
    if (!confirmed) return;

    setDeleting(true);
    setError(null);
    try {
      await apiFetch(`/repos/${encodeURIComponent(repoName)}`, { method: "DELETE" });
      onDeleted?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 6 }}>
      <button
        onClick={handleDelete}
        disabled={deleting}
        style={{
          background: deleting ? "rgba(239,68,68,0.5)" : "#ef4444",
          border: "none",
          color: "#fff",
          padding: "5px 14px",
          borderRadius: 6,
          cursor: deleting ? "not-allowed" : "pointer",
          fontSize: 12,
          fontWeight: 600,
          opacity: deleting ? 0.8 : 1,
        }}
      >
        {deleting ? "Deleting..." : "Delete"}
      </button>
      {error && <span style={{ color: "#f87171", fontSize: 11 }}>{error}</span>}
    </div>
  );
}

function IngestButton({ onComplete }) {
  const [showForm, setShowForm] = useState(false);
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState(null);

  async function handleIngest() {
    if (!url.trim()) return;
    setStatus("ingesting");
    try {
      await apiFetch("/repos/ingest", { method: "POST", body: JSON.stringify({ repo_url: url }) });
      setStatus("started");
      // Poll status
      const interval = setInterval(async () => {
        try {
          const s = await apiFetch(`/repos/ingest/status?repo_url=${encodeURIComponent(url)}`);
          if (s.status === "complete") {
            clearInterval(interval);
            setStatus("done");
            setUrl("");
            setTimeout(() => { setShowForm(false); setStatus(null); onComplete(); }, 1500);
          } else if (s.status === "failed") {
            clearInterval(interval);
            setStatus("error: " + s.message);
          }
        } catch { /* keep polling */ }
      }, 3000);
    } catch (e) {
      setStatus("error: " + e.message);
    }
  }

  if (!showForm) {
    return <button onClick={() => setShowForm(true)} style={{ background: "#4f8ef7", border: "none", color: "#fff", padding: "8px 18px", borderRadius: 8, cursor: "pointer", fontWeight: 600, fontSize: 13 }}>+ Add Repository</button>;
  }

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <input value={url} onChange={e => setUrl(e.target.value)} onKeyDown={e => e.key === "Enter" && handleIngest()}
        placeholder="https://github.com/owner/repo" style={{
          background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.12)",
          color: "#fff", padding: "8px 14px", borderRadius: 8, fontSize: 13, outline: "none", width: 300,
        }} />
      <button onClick={handleIngest} disabled={status === "ingesting" || status === "started"} style={{
        background: "#4f8ef7", border: "none", color: "#fff", padding: "8px 16px",
        borderRadius: 8, cursor: "pointer", fontWeight: 600, fontSize: 13, opacity: status ? 0.7 : 1,
      }}>{status === "ingesting" || status === "started" ? "⏳ Ingesting..." : status === "done" ? "✅ Done!" : "🚀 Ingest"}</button>
      <button onClick={() => { setShowForm(false); setStatus(null); }} style={{ background: "none", border: "none", color: "rgba(255,255,255,0.4)", cursor: "pointer", fontSize: 16 }}>✕</button>
      {status && status.startsWith("error") && <span style={{ color: "#f87171", fontSize: 12 }}>{status}</span>}
    </div>
  );
}

// ─── Query Page ───────────────────────────────────────────────────────────────

function QueryPage({ selectedRepo, setSelectedRepo, repos }) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const suggestions = [
    "Where is the main entry point?",
    "How does the authentication flow work?",
    "What are the core data structures?",
    "Show me the API endpoints",
  ];

  async function handleQuery(q) {
    const text = q || query;
    if (!text.trim() || !selectedRepo) return;
    setQuery(text);
    setLoading(true);
    setResult(null);
    try {
      const data = await apiFetch(`/repos/${selectedRepo}/query`, {
        method: "POST",
        body: JSON.stringify({ query: text }),
      });
      setResult(data);
    } catch (e) {
      setResult({ answer: `Error: ${e.message}`, docs: [], method: "error" });
    }
    setLoading(false);
  }

  return (
    <div style={{ padding: "40px 48px", maxWidth: 900, margin: "0 auto" }}>
      <h1 style={{ fontSize: 28, fontWeight: 700, margin: "0 0 4px", color: "#fff" }}>Query Codebase</h1>
      <p style={{ color: "rgba(255,255,255,0.4)", margin: "0 0 28px", fontSize: 14 }}>Ask questions about your code in natural language</p>

      <div style={{ marginBottom: 20 }}>
        <label style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", display: "block", marginBottom: 6 }}>Select Repository</label>
        <RepoDropdown repos={repos} selected={selectedRepo} onSelect={setSelectedRepo} />
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 32 }}>
        <input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && handleQuery()}
          placeholder="e.g., Where is judgment prediction implemented?"
          style={{ flex: 1, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.12)", color: "#fff", padding: "12px 18px", borderRadius: 8, fontSize: 15, outline: "none", fontFamily: "inherit" }} />
        <button onClick={() => handleQuery()} style={{ background: "#1e293b", border: "1px solid rgba(255,255,255,0.12)", color: "#fff", padding: "12px 24px", borderRadius: 8, cursor: "pointer", fontWeight: 600, fontSize: 14, display: "flex", alignItems: "center", gap: 6 }}>➤ Query</button>
      </div>

      {loading && <Loader text="Analyzing codebase..." />}

      {result && !loading && (
        <div>
          {/* Answer */}
          <Card style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
              <span style={{ fontWeight: 600, color: "#4f8ef7" }}>Answer</span>
              <div style={{ display: "flex", gap: 8 }}>
                <Badge>{result.method}</Badge>
                <Badge color="green">{result.latency_seconds}s</Badge>
              </div>
            </div>
            <pre style={{ whiteSpace: "pre-wrap", color: "rgba(255,255,255,0.8)", fontSize: 14, lineHeight: 1.7, margin: 0, fontFamily: "'Fira Code', monospace" }}>{result.answer}</pre>
          </Card>

          {/* Graph stats */}
          {result.graph_stats && (
            <Card style={{ marginBottom: 16 }}>
              <div style={{ fontWeight: 600, color: "#fff", marginBottom: 12 }}>📊 Graph-RAG Stats</div>
              <div style={{ display: "flex", gap: 24 }}>
                {[
                  ["Anchor Nodes", result.graph_stats.anchor_nodes],
                  ["Graph Expanded", result.graph_stats.expanded_nodes ?? result.graph_stats.total_nodes_visited],
                  ["Max Depth", result.graph_stats.max_depth_reached],
                  ["Final Docs", result.graph_stats.final_document_count],
                ].map(([label, val]) => (
                  <div key={label} style={{ textAlign: "center" }}>
                    <div style={{ fontSize: 20, fontWeight: 700, color: "#4f8ef7" }}>{val ?? "–"}</div>
                    <div style={{ fontSize: 11, color: "rgba(255,255,255,0.4)" }}>{label}</div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Source docs */}
          {result.docs && result.docs.length > 0 && (
            <div>
              <h3 style={{ fontSize: 16, fontWeight: 600, color: "#fff", marginBottom: 12 }}>📂 Source Code Matches</h3>
              {result.docs.map((doc, i) => (
                <Card key={i} style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                    <span style={{ fontSize: 13, color: "#4f8ef7", fontFamily: "'Fira Code', monospace" }}>{doc.path}</span>
                    <span style={{ fontSize: 12, color: "rgba(255,255,255,0.35)" }}>Lines {doc.start_line}–{doc.end_line}</span>
                  </div>
                  {doc.symbol_name && <Badge>{doc.symbol_name}</Badge>}
                  <pre style={{ whiteSpace: "pre-wrap", color: "rgba(255,255,255,0.7)", fontSize: 13, lineHeight: 1.5, marginTop: 8, fontFamily: "'Fira Code', monospace", maxHeight: 200, overflow: "auto" }}>{doc.content}</pre>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {!result && !loading && (
        <div style={{ textAlign: "center", padding: "60px 0" }}>
          <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>➤</div>
          <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8, color: "rgba(255,255,255,0.6)" }}>Ask a question about your codebase</div>
          <div style={{ color: "rgba(255,255,255,0.3)", marginBottom: 24, fontSize: 14 }}>Try queries like:</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "center" }}>
            {suggestions.map(s => (
              <button key={s} onClick={() => handleQuery(s)} style={{
                background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
                color: "rgba(255,255,255,0.6)", padding: "8px 20px", borderRadius: 20, cursor: "pointer", fontSize: 13,
              }}>{s}</button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Call Graph ───────────────────────────────────────────────────────────────

function CallGraphPage({ selectedRepo, setSelectedRepo, repos }) {
  const [focus, setFocus] = useState("");
  const [summary, setSummary] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState(null);

  const { data, loading, error, reload } = useApi(
    `/repos/${selectedRepo}/callgraph${focus ? `?focus=${encodeURIComponent(focus)}&max_depth=2` : ""}`,
    [selectedRepo, focus]
  );

  const typeColors = { entry: "#4f8ef7", core: "#a855f7", helper: "#22c55e" };

  useEffect(() => {
    if (!focus) {
      setSummary("");
      setSummaryError(null);
      setSummaryLoading(false);
      return;
    }

    const fetchSummary = async () => {
      setSummaryLoading(true);
      setSummaryError(null);
      try {
        const funcLabel = focus.split(":").pop();
        const q = `Explain the function '${funcLabel}' in this codebase. Include what it does, input and output behavior, key helpers it calls, and where data flows next. Mention file reference and entry relationships.`;
        const result = await apiFetch(`/repos/${selectedRepo}/query`, {
          method: "POST",
          body: JSON.stringify({ query: q, max_depth: 3, k_initial: 5, strategy: "dfs" }),
        });
        setSummary(result.answer || "No summary returned.");
      } catch (err) {
        setSummaryError(err.message || "Failed to get function summary.");
      } finally {
        setSummaryLoading(false);
      }
    };

    fetchSummary();
  }, [focus, selectedRepo]);

  // Simple force-directed-ish layout
  function layoutNodes(nodes) {
    if (!nodes || !nodes.length) return { nodes: [], width: 0, height: 0 };
    const rows = {};
    nodes.forEach(n => {
      const type = n.type || "helper";
      if (!rows[type]) rows[type] = [];
      rows[type].push(n);
    });
    const typeOrder = ["entry", "core", "helper"];
    const laid = [];
    const canvasWidth = 1180;
    const nodeWidth = 160;
    const horizontalGap = 26;
    const verticalGap = 78;
    const maxPerRow = 5;
    let y = 28;

    for (const type of typeOrder) {
      const group = rows[type] || [];
      if (!group.length) continue;

      const chunkedRows = [];
      for (let i = 0; i < group.length; i += maxPerRow) {
        chunkedRows.push(group.slice(i, i + maxPerRow));
      }

      chunkedRows.forEach((row, rowIndex) => {
        const totalWidth = row.length * nodeWidth + Math.max(0, row.length - 1) * horizontalGap;
        const startX = Math.max(20, (canvasWidth - totalWidth) / 2);
        row.forEach((n, i) => {
          laid.push({
            ...n,
            x: startX + i * (nodeWidth + horizontalGap),
            y: y + rowIndex * verticalGap,
            color: typeColors[type] || "#22c55e",
          });
        });
      });

      y += chunkedRows.length * verticalGap + 34;
    }

    return {
      nodes: laid,
      width: canvasWidth,
      height: Math.max(520, y + 48),
    };
  }

  return (
    <div style={{ padding: "30px 24px", maxWidth: 1200, margin: "0 auto" }}>
      <h1 style={{ fontSize: 30, fontWeight: 700, margin: "0 0 6px", color: "#fff" }}>Call Graph Explorer</h1>
      <p style={{ color: "rgba(255,255,255,0.65)", margin: "0 0 18px", fontSize: 15 }}>Visualize function call relationships and dependencies (select core function to focus).</p>

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 24, flexWrap: "wrap" }}>
        <RepoDropdown repos={repos} selected={selectedRepo} onSelect={name => { setSelectedRepo(name); setFocus(""); }} />
        <div style={{ flex: 1, minWidth: 280, maxWidth: 450 }}>
          <select value={focus} onChange={e => setFocus(e.target.value)} style={{ width: "100%", padding: "10px 14px", borderRadius: 10, background: "rgba(15, 23, 42, 1)", border: "1px solid rgba(255,255,255,0.18)", color: "#fff", fontSize: 14 }}>
            <option value="" style={{ background: "rgba(15, 23, 42, 1)", color: "#fff" }}>-- Focus core function --</option>
            {data && data.nodes && data.nodes.filter(n => n.type === "core").map(n => (
              <option key={n.id} value={n.id} style={{ background: "rgba(15, 23, 42, 1)", color: "#fff" }}>{n.label}</option>
            ))}
          </select>
        </div>
        <div style={{ fontSize: 13, color: "rgba(255,255,255,0.6)", marginLeft: "auto" }}>
          Core functions: {data?.nodes?.filter(n => n.type === "core").length ?? 0}
        </div>
      </div>

      {loading && <Loader text="Loading call graph..." />}
      {error && <ErrorBox message={error} onRetry={reload} />}

      {data && !loading && (
        <>
          <Card style={{ padding: 0, overflow: "hidden", marginBottom: 18, minHeight: 640 }}>
            <div style={{ position: "relative", height: 600, overflow: "auto", background: "rgba(0,0,0,0.25)" }}>
              {(() => {
                const layout = layoutNodes(data.nodes || []);
                const nodes = layout.nodes;
                const nodeMap = {};
                nodes.forEach(n => { nodeMap[n.id] = n; });
                const edges = (data.edges || []).filter(e => nodeMap[e.source] && nodeMap[e.target]);

                return (
                  <>
                    <div style={{ position: "relative", width: layout.width, minHeight: layout.height }}>
                      <svg width={layout.width} height={layout.height} style={{ position: "absolute", top: 0, left: 0 }}>
                        {edges.map((e, i) => {
                          const s = nodeMap[e.source], t = nodeMap[e.target];
                          if (!s || !t) return null;
                          return <line key={i} x1={s.x + 80} y1={s.y + 18} x2={t.x + 80} y2={t.y + 18} stroke="rgba(79,142,247,0.35)" strokeWidth={1.5} strokeDasharray="4 3" />;
                        })}
                      </svg>
                      {nodes.map(n => (
                        <div key={n.id} onClick={() => setFocus(n.id)} style={{
                          position: "absolute", left: n.x, top: n.y,
                          background: n.color, color: "#fff", borderRadius: 8,
                          padding: "8px 16px", fontSize: 12, fontWeight: 600,
                          cursor: "pointer", whiteSpace: "nowrap", width: 160, overflow: "hidden", textOverflow: "ellipsis",
                          boxShadow: `0 0 16px ${n.color}44`, fontFamily: "'Fira Code', monospace", textAlign: "center",
                        }} title={n.id}>{n.label}</div>
                      ))}
                    </div>
                  </>
                );
              })()}
            </div>
          </Card>

          <div style={{ display: "flex", gap: 10, alignItems: "center", margin: "0 0 16px" }}>
            <span style={{ width: 13, height: 13, background: "#4f8ef7", borderRadius: 3, display: "inline-block" }} />
            <span style={{ color: "#d1d5db", fontSize: 13 }}>entry</span>
            <span style={{ width: 13, height: 13, background: "#a855f7", borderRadius: 3, display: "inline-block", marginLeft: 12 }} />
            <span style={{ color: "#d1d5db", fontSize: 13 }}>core</span>
            <span style={{ width: 13, height: 13, background: "#22c55e", borderRadius: 3, display: "inline-block", marginLeft: 12 }} />
            <span style={{ color: "#d1d5db", fontSize: 13 }}>helper</span>
          </div>

          {focus && data && (
            <Card style={{ marginBottom: 20, background: "rgba(0,0,0,0.4)" }}>
              <h3 style={{ color: "#fff", margin: "10px 16px" }}>Focused function details</h3>
              {(() => {
                const functionNode = (data.nodes || []).find(n => n.id === focus);
                const inEdges = (data.edges || []).filter(e => e.target === focus);
                const outEdges = (data.edges || []).filter(e => e.source === focus);
                const parents = inEdges.map(e => e.source);
                const children = outEdges.map(e => e.target);
                return (
                  <>
                    <div style={{ display: "flex", gap: 20, padding: "0 16px 16px", flexWrap: "wrap" }}>
                      <div style={{ minWidth: 250 }}>
                        <p style={{ color: "#ccc", margin: "4px 0" }}><strong>ID:</strong> {functionNode?.id ?? focus}</p>
                        <p style={{ color: "#ccc", margin: "4px 0" }}><strong>Name:</strong> {functionNode?.label ?? focus.split(':').pop()}</p>
                        <p style={{ color: "#ccc", margin: "4px 0" }}><strong>Type:</strong> {functionNode?.type ?? "unknown"}</p>
                        <p style={{ color: "#ccc", margin: "4px 0" }}><strong>File:</strong> {functionNode?.file ?? "unknown"}</p>
                        <p style={{ color: "#ccc", margin: "4px 0" }}><strong>Incoming calls:</strong> {parents.length}</p>
                        <p style={{ color: "#ccc", margin: "4px 0" }}><strong>Outgoing calls:</strong> {children.length}</p>
                      </div>

                      <div>
                        <p style={{ color: "#fff", margin: "4px 0 8px" }}><strong>Callers (entry/core/help):</strong></p>
                        <ul style={{ margin: 0, paddingLeft: 16, color: "#ddd" }}>
                          {parents.length ? parents.map(parent => <li key={parent}>{parent.split(':').pop()}</li>) : <em>None</em>}
                        </ul>
                      </div>

                      <div>
                        <p style={{ color: "#fff", margin: "4px 0 8px" }}><strong>Callees (core/helper):</strong></p>
                        <ul style={{ margin: 0, paddingLeft: 16, color: "#ddd" }}>
                          {children.length ? children.map(child => <li key={child}>{child.split(':').pop()}</li>) : <em>None</em>}
                        </ul>
                      </div>
                    </div>

                    <div style={{ padding: "0 16px 16px" }}>
                      <h4 style={{ color: "#fff", margin: "8px 0" }}>LLM summary</h4>
                      {summaryLoading && <p style={{ color: "#9ca3af" }}>Generating summary...</p>}
                      {summaryError && <p style={{ color: "#f87171" }}>Error: {summaryError}</p>}
                      {!summaryLoading && !summaryError && summary && (
                        <p style={{ color: "#d1d5db", margin: 0, whiteSpace: "pre-line" }}>{summary}</p>
                      )}
                      {!summaryLoading && !summaryError && !summary && (
                        <p style={{ color: "#9ca3af", margin: 0 }}>Select a core function and wait for the LLM to explain it.</p>
                      )}
                    </div>
                    </>
                );
              })()}
            </Card>
          )}
        </>
      )}
    </div>
  );
}

// ─── Onboarding Page ──────────────────────────────────────────────────────────

function OnboardingPage({ selectedRepo, setSelectedRepo, repos }) {
  const [tab, setTab] = useState("Overview");

  return (
    <div style={{ padding: "40px 48px", maxWidth: 1000, margin: "0 auto" }}>
      <h1 style={{ fontSize: 28, fontWeight: 700, margin: "0 0 4px", color: "#fff" }}>Codebase Onboarding</h1>
      <p style={{ color: "rgba(255,255,255,0.4)", margin: "0 0 24px", fontSize: 14 }}>Comprehensive codebase insights</p>

      <div style={{ marginBottom: 24 }}>
        <RepoDropdown repos={repos} selected={selectedRepo} onSelect={setSelectedRepo} />
      </div>

      <div style={{ display: "flex", gap: 4, marginBottom: 28, flexWrap: "wrap" }}>
        {ONBOARDING_TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            background: tab === t ? "#4f8ef7" : "rgba(255,255,255,0.05)",
            border: `1px solid ${tab === t ? "#4f8ef7" : "rgba(255,255,255,0.1)"}`,
            color: tab === t ? "#fff" : "rgba(255,255,255,0.5)",
            padding: "7px 16px", borderRadius: 8, cursor: "pointer", fontSize: 13, fontWeight: tab === t ? 600 : 400,
          }}>{t}</button>
        ))}
      </div>

      {tab === "Overview" && <OnboardOverview repo={selectedRepo} />}
      {tab === "Entry/Exit Points" && <OnboardEntryExit repo={selectedRepo} />}
      {tab === "Roadmap" && <OnboardRoadmap repo={selectedRepo} />}
      {tab === "File Structure" && <OnboardFileStructure repo={selectedRepo} />}
      {tab === "Navigation" && <OnboardEntryExit repo={selectedRepo} />}
      {tab === "Code Health" && <OnboardCodeHealth repo={selectedRepo} />}
      {tab === "Contributions" && <OnboardContributions repo={selectedRepo} />}
    </div>
  );
}

function OnboardOverview({ repo }) {
  if (!repo || repo === "null" || repo === "undefined") {
    return (
      <Card style={{ padding: 20 }}>
        <div style={{ color: "#e2e8f0", fontSize: 16 }}>Select a repository from the dropdown first to load onboarding content.</div>
      </Card>
    );
  }

  const { data, loading, error, reload } = useApi(`/repos/${repo}/onboarding/overview`, [repo]);
  if (loading) return <Loader />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  const s = data.summary || {};
  const langs = data.language_distribution || [];

  return (
    <div>
      <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
        {[[s.files || 0, "Total Files"], [s.functions || 0, "Functions"], [s.classes || 0, "Classes"], [(s.languages || []).length, "Languages"]].map(([v, l]) => (
          <Card key={l} style={{ flex: 1, textAlign: "center" }}>
            <div style={{ fontSize: 26, fontWeight: 700, color: "#fff" }}>{v}</div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", marginTop: 4 }}>{l}</div>
          </Card>
        ))}
      </div>

      <Card style={{ marginBottom: 20 }}>
        <div style={{ fontWeight: 600, color: "#fff", marginBottom: 16 }}>Language Distribution</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {langs.map(l => (
            <div key={l.language} style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span style={{ color: "rgba(255,255,255,0.7)", fontSize: 14, minWidth: 100 }}>{l.language}</span>
              <div style={{ flex: 1, background: "rgba(255,255,255,0.08)", borderRadius: 4, height: 20, overflow: "hidden" }}>
                <div style={{ width: `${l.percentage}%`, height: "100%", background: "#4f8ef7", borderRadius: 4 }} />
              </div>
              <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 12, minWidth: 50, textAlign: "right" }}>{l.percentage}%</span>
            </div>
          ))}
        </div>
      </Card>

      <div style={{ display: "flex", gap: 12 }}>
        <Card style={{ flex: 1 }}>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", marginBottom: 4 }}>Knowledge Graph</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "#fff" }}>{data.kg_nodes} nodes / {data.kg_edges} edges</div>
        </Card>
        <Card style={{ flex: 1 }}>
          <div style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", marginBottom: 4 }}>Boot Chain</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: data.has_boot_chain ? "#4ade80" : "#f87171" }}>{data.has_boot_chain ? "Available" : "Not detected"}</div>
        </Card>
      </div>

      <Card style={{ marginTop: 20 }}>
        <div style={{ fontWeight: 600, color: "#fff", marginBottom: 12 }}>📘 Generated Codebase Documentation</div>
        <div style={{ whiteSpace: "pre-wrap", color: "#d1d5db", fontSize: 14, lineHeight: 1.6 }}>
          {data.documentation || "No pre-generated documentation available. Re-ingest the repository to generate it."}
        </div>
      </Card>
    </div>
  );
}

function OnboardEntryExit({ repo }) {
  const { data, loading, error, reload } = useApi(`/repos/${repo}/onboarding/entry-points`, [repo]);
  if (loading) return <Loader />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  return (
    <div>
      <Card style={{ marginBottom: 20 }}>
        <div style={{ fontWeight: 600, color: "#fff", marginBottom: 16 }}>📍 Entry Points ({(data.entry_points || []).length})</div>
        {(data.entry_points || []).map(e => (
          <div key={e.full_id} style={{ borderTop: "1px solid rgba(255,255,255,0.07)", padding: "14px 0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontWeight: 600, color: "#fff", fontFamily: "'Fira Code', monospace" }}>{e.name}</div>
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", marginTop: 4 }}>{e.file}</div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span style={{ fontSize: 12, color: "rgba(255,255,255,0.4)" }}>fan-out: {e.fan_out}</span>
              <Badge color={e.type === "boot_entry" ? "green" : "blue"}>{e.type}</Badge>
            </div>
          </div>
        ))}
      </Card>
      <Card>
        <div style={{ fontWeight: 600, color: "#fff", marginBottom: 16 }}>📍 Exit Points ({(data.exit_points || []).length})</div>
        {(data.exit_points || []).map(e => (
          <div key={e.full_id} style={{ borderTop: "1px solid rgba(255,255,255,0.07)", padding: "14px 0", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontWeight: 600, color: "#fff", fontFamily: "'Fira Code', monospace" }}>{e.name}</div>
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", marginTop: 4 }}>{e.file}</div>
            </div>
            <span style={{ fontSize: 12, color: "rgba(255,255,255,0.4)" }}>fan-in: {e.fan_in}</span>
          </div>
        ))}
      </Card>
    </div>
  );
}

function OnboardRoadmap({ repo }) {
  const { data, loading, error, reload } = useApi(`/repos/${repo}/onboarding/roadmap`, [repo]);
  if (loading) return <Loader />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  return (
    <Card>
      <div style={{ fontWeight: 600, color: "#fff", marginBottom: 6 }}>Learning Roadmap</div>
      <div style={{ fontSize: 13, color: "rgba(255,255,255,0.4)", marginBottom: 24 }}>{data.summary}</div>
      {(data.steps || []).map((s, i) => (
        <div key={s.step} style={{ display: "flex", gap: 20, marginBottom: i < (data.steps || []).length - 1 ? 28 : 0 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <div style={{ width: 36, height: 36, borderRadius: "50%", background: "#4f8ef7", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 16, flexShrink: 0 }}>{s.step}</div>
            {i < (data.steps || []).length - 1 && <div style={{ width: 2, flex: 1, background: "rgba(79,142,247,0.3)", marginTop: 6 }} />}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, color: "#fff", marginBottom: 6, marginTop: 6 }}>{s.file}</div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", marginBottom: 8 }}>{s.dependency_count} dependencies • {(s.functions || []).length} functions</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {(s.functions || []).slice(0, 6).map(f => (
                <span key={f} style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 6, padding: "4px 10px", fontSize: 12, color: "rgba(255,255,255,0.6)", fontFamily: "'Fira Code', monospace" }}>{f}</span>
              ))}
            </div>
          </div>
        </div>
      ))}
    </Card>
  );
}

function OnboardFileStructure({ repo }) {
  const { data, loading, error, reload } = useApi(`/repos/${repo}/onboarding/file-tree`, [repo]);
  if (loading) return <Loader />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  function renderTree(tree, depth = 0) {
    return Object.entries(tree).map(([key, val]) => {
      if (val._type === "file") {
        return (
          <div key={val._path} style={{ display: "flex", justifyContent: "space-between", padding: "7px 0", paddingLeft: depth * 20, borderTop: "1px solid rgba(255,255,255,0.04)" }}>
            <span style={{ color: "rgba(255,255,255,0.65)", fontSize: 13, fontFamily: "'Fira Code', monospace" }}>📄 {key}</span>
            <span style={{ color: "rgba(255,255,255,0.3)", fontSize: 12 }}>{val._functions}fn {val._classes}cls</span>
          </div>
        );
      }
      return (
        <div key={key}>
          <div style={{ padding: "6px 0", paddingLeft: depth * 20, color: "rgba(255,255,255,0.5)", fontSize: 14 }}>📂 {key}/</div>
          {renderTree(val, depth + 1)}
        </div>
      );
    });
  }

  return (
    <Card>
      <div style={{ fontWeight: 600, color: "#fff", marginBottom: 16 }}>File Structure ({data.total_files} files)</div>
      {renderTree(data.tree || {})}
    </Card>
  );
}

function OnboardCodeHealth({ repo }) {
  const { data, loading, error, reload } = useApi(`/repos/${repo}/health`, [repo]);
  if (loading) return <Loader text="Analyzing code health..." />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data) return null;

  const scoreColor = data.overall_score >= 80 ? "#4ade80" : data.overall_score >= 60 ? "#facc15" : data.overall_score >= 40 ? "#fb923c" : "#f87171";
  const sevColor = s => s === "critical" || s === "high" ? "red" : s === "medium" ? "yellow" : "blue";

  return (
    <div>
      <Card style={{ textAlign: "center", marginBottom: 16 }}>
        <div style={{ fontSize: 52, fontWeight: 800, color: scoreColor }}>{Math.round(data.overall_score)}</div>
        <div style={{ color: "rgba(255,255,255,0.5)", fontSize: 14 }}>Overall Health Score — Grade {data.grade} ({data.level})</div>
      </Card>

      <Card style={{ marginBottom: 16 }}>
        <div style={{ fontWeight: 600, color: "#fff", marginBottom: 16 }}>Health Dimensions</div>
        {Object.entries(data.dimension_scores || {}).map(([dim, score]) => (
          <div key={dim} style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
            <span style={{ color: "rgba(255,255,255,0.6)", fontSize: 13, minWidth: 160 }}>{dim.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</span>
            <div style={{ flex: 1, background: "rgba(255,255,255,0.08)", borderRadius: 4, height: 16, overflow: "hidden" }}>
              <div style={{ width: `${score}%`, height: "100%", background: score >= 70 ? "#4ade80" : score >= 50 ? "#facc15" : "#f87171", borderRadius: 4, transition: "width 0.5s" }} />
            </div>
            <span style={{ color: "rgba(255,255,255,0.5)", fontSize: 12, minWidth: 40, textAlign: "right" }}>{Math.round(score)}</span>
          </div>
        ))}
      </Card>

      {(data.smells || []).length > 0 && (
        <Card style={{ marginBottom: 16 }}>
          <div style={{ fontWeight: 600, color: "#fff", marginBottom: 14 }}>⚠️ Code Smells ({data.smells.length})</div>
          {data.smells.slice(0, 10).map((smell, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 0", borderTop: "1px solid rgba(255,255,255,0.07)" }}>
              <div>
                <div style={{ fontWeight: 600, color: "#fff" }}>{smell.type}</div>
                <div style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", marginTop: 3, fontFamily: "'Fira Code', monospace" }}>{smell.file}</div>
              </div>
              <Badge color={sevColor(smell.severity)}>{smell.severity}</Badge>
            </div>
          ))}
        </Card>
      )}

      {(data.suggestions || []).length > 0 && (
        <Card>
          <div style={{ fontWeight: 600, color: "#fff", marginBottom: 14 }}>💡 Refactoring Suggestions ({data.suggestions.length})</div>
          {data.suggestions.slice(0, 8).map((sug, i) => (
            <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 0", borderTop: "1px solid rgba(255,255,255,0.07)" }}>
              <span style={{ color: "#4ade80", fontSize: 16, marginTop: 1 }}>✓</span>
              <div>
                <div style={{ fontWeight: 600, color: "#fff", marginBottom: 4 }}>{sug.smell_type || sug.type}</div>
                <div style={{ fontSize: 13, color: "rgba(255,255,255,0.6)", lineHeight: 1.5 }}>{sug.description}</div>
              </div>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}

function OnboardContributions({ repo }) {
  const { data, loading, error, reload } = useApi(`/repos/${repo}/contributions`, [repo]);
  if (loading) return <Loader text="Loading contributions..." />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!data || !data.authors || data.authors.length === 0) {
    return <Card><div style={{ textAlign: "center", color: "rgba(255,255,255,0.4)", padding: 32 }}>No contribution data available. Re-ingest the repository to enable contribution analysis.</div></Card>;
  }

  const topAuthors = (data.authors || []).slice(0, 5);
  const maxCommits = Math.max(...topAuthors.map(a => a.commits || 0), 1);
  const maxFiles = Math.max(...topAuthors.map(a => a.files_changed || 0), 1);
  const totalLinesAdded = topAuthors.reduce((sum, a) => sum + (a.lines_added || 0), 0);
  const totalLinesDeleted = topAuthors.reduce((sum, a) => sum + (a.lines_deleted || 0), 0);

  return (
    <div>
      <div style={{ display: "flex", gap: 16, marginBottom: 24 }}>
        <StatCard icon="👥" value={data.total_authors} label="Authors" />
        <StatCard icon="📝" value={data.total_commits} label="Commits" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 16, marginBottom: 18 }}>
        <Card>
          <div style={{ fontWeight: 600, color: "#fff", marginBottom: 16 }}>Top Contributors By Commits</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {topAuthors.map((a, i) => (
              <div key={a.name + i}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6, gap: 12 }}>
                  <div style={{ color: "#fff", fontWeight: 600, minWidth: 0 }}>
                    #{i + 1} {a.name}
                  </div>
                  <div style={{ color: "rgba(255,255,255,0.55)", fontSize: 12, whiteSpace: "nowrap" }}>
                    {(a.commits || 0).toLocaleString()} commits
                  </div>
                </div>
                <div style={{ background: "rgba(255,255,255,0.08)", borderRadius: 999, height: 12, overflow: "hidden" }}>
                  <div style={{
                    width: `${Math.max(8, Math.round(((a.commits || 0) / maxCommits) * 100))}%`,
                    height: "100%",
                    background: "linear-gradient(90deg, #4f8ef7 0%, #22c55e 100%)",
                    borderRadius: 999,
                  }} />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, color: "rgba(255,255,255,0.4)", fontSize: 12 }}>
                  <span>{(a.files_changed || 0).toLocaleString()} files changed</span>
                  <span>{a.net_lines >= 0 ? "+" : ""}{(a.net_lines || 0).toLocaleString()} net lines</span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <div style={{ fontWeight: 600, color: "#fff", marginBottom: 16 }}>Top 5 Snapshot</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
            <div style={{ background: "rgba(255,255,255,0.04)", borderRadius: 10, padding: 14 }}>
              <div style={{ color: "rgba(255,255,255,0.45)", fontSize: 12, marginBottom: 6 }}>Shown Authors</div>
              <div style={{ color: "#fff", fontSize: 28, fontWeight: 700 }}>{topAuthors.length}</div>
            </div>
            <div style={{ background: "rgba(255,255,255,0.04)", borderRadius: 10, padding: 14 }}>
              <div style={{ color: "rgba(255,255,255,0.45)", fontSize: 12, marginBottom: 6 }}>Top Commit Share</div>
              <div style={{ color: "#fff", fontSize: 28, fontWeight: 700 }}>
                {Math.round(((topAuthors[0]?.commits || 0) / Math.max(data.total_commits || 1, 1)) * 100)}%
              </div>
            </div>
            <div style={{ background: "rgba(255,255,255,0.04)", borderRadius: 10, padding: 14 }}>
              <div style={{ color: "rgba(255,255,255,0.45)", fontSize: 12, marginBottom: 6 }}>Lines Added</div>
              <div style={{ color: "#4ade80", fontSize: 28, fontWeight: 700 }}>+{totalLinesAdded.toLocaleString()}</div>
            </div>
            <div style={{ background: "rgba(255,255,255,0.04)", borderRadius: 10, padding: 14 }}>
              <div style={{ color: "rgba(255,255,255,0.45)", fontSize: 12, marginBottom: 6 }}>Lines Deleted</div>
              <div style={{ color: "#f87171", fontSize: 28, fontWeight: 700 }}>-{totalLinesDeleted.toLocaleString()}</div>
            </div>
          </div>

          <div style={{ marginTop: 16 }}>
            <div style={{ color: "rgba(255,255,255,0.55)", fontSize: 12, marginBottom: 8 }}>Files changed comparison</div>
            {topAuthors.map((a, i) => (
              <div key={`${a.name}-${i}-files`} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <span style={{ color: "rgba(255,255,255,0.7)", fontSize: 12, minWidth: 120, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {a.name}
                </span>
                <div style={{ flex: 1, background: "rgba(255,255,255,0.06)", height: 8, borderRadius: 999, overflow: "hidden" }}>
                  <div style={{
                    width: `${Math.max(6, Math.round(((a.files_changed || 0) / maxFiles) * 100))}%`,
                    height: "100%",
                    background: "#a855f7",
                    borderRadius: 999,
                  }} />
                </div>
                <span style={{ color: "rgba(255,255,255,0.45)", fontSize: 12, minWidth: 28, textAlign: "right" }}>
                  {a.files_changed || 0}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <div style={{ fontWeight: 600, color: "#fff", marginBottom: 6 }}>🏆 Contributors</div>
        <div style={{ color: "rgba(255,255,255,0.45)", fontSize: 12, marginBottom: 12 }}>
          Showing top {topAuthors.length} contributor{topAuthors.length === 1 ? "" : "s"} by commit count
        </div>
        {topAuthors.map((a, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 0", borderTop: "1px solid rgba(255,255,255,0.07)" }}>
            <div>
              <div style={{ fontWeight: 600, color: "#fff" }}>
                #{i + 1} {a.name}
                {a.emails && a.emails.length > 1 && <span style={{ fontSize: 11, color: "rgba(255,255,255,0.35)", marginLeft: 8 }}>(merged: {a.emails.length} accounts)</span>}
              </div>
              <div style={{ fontSize: 12, color: "rgba(255,255,255,0.35)", marginTop: 4 }}>
                {(a.commits || 0).toLocaleString()} commits • {(a.files_changed || 0).toLocaleString()} files • {a.lines_added > 0 ? `+${a.lines_added.toLocaleString()}` : 0} / -{(a.lines_deleted || 0).toLocaleString()} lines
              </div>
              {(a.first_commit || a.last_commit) && (
                <div style={{ fontSize: 11, color: "rgba(255,255,255,0.28)", marginTop: 4 }}>
                  Active {a.first_commit ? `from ${String(a.first_commit).slice(0, 10)}` : ""}{a.last_commit ? ` to ${String(a.last_commit).slice(0, 10)}` : ""}
                </div>
              )}
            </div>
            <div style={{ fontSize: 18, fontWeight: 700, color: a.net_lines >= 0 ? "#4ade80" : "#f87171" }}>
              {a.net_lines >= 0 ? "+" : ""}{(a.net_lines || 0).toLocaleString()}
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}

// ─── App Root ─────────────────────────────────────────────────────────────────

export default function App() {
  const [page, setPage] = useState("Landing");
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [repoRefreshToken, setRepoRefreshToken] = useState(0);

  // Fetch repos list for dropdowns across pages
  const { data: reposData } = useApi("/repos", [repoRefreshToken]);
  const repos = (reposData?.repos || []).map(r => r.name || r);

  const refreshRepos = useCallback(() => {
    setRepoRefreshToken(token => token + 1);
  }, []);

  // Auto-select first repo if none selected
  useEffect(() => {
    if (!selectedRepo && repos.length > 0) {
      setSelectedRepo(repos[0]);
    }
  }, [repos, selectedRepo]);

  if (page === "Landing") {
    return <LandingPage setPage={setPage} />;
  }

  return (
    <div style={{ fontFamily: "'Inter', sans-serif", background: "#060b18", minHeight: "100vh", color: "#fff" }}>
      <Navbar page={page} setPage={setPage} />
      {page === "Dashboard" && <Dashboard setPage={setPage} setSelectedRepo={setSelectedRepo} onReposChanged={refreshRepos} />}
      {page === "Query" && <QueryPage selectedRepo={selectedRepo} setSelectedRepo={setSelectedRepo} repos={repos} />}
      {page === "Call Graph" && <CallGraphPage selectedRepo={selectedRepo} setSelectedRepo={setSelectedRepo} repos={repos} />}
      {page === "Onboarding" && <OnboardingPage selectedRepo={selectedRepo} setSelectedRepo={setSelectedRepo} repos={repos} />}
    </div>
  );
}
