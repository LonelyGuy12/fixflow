"use client";

import React, { useState, useRef, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

type UI_STATE = 'LOADING_REPO' | 'REPO_DASHBOARD';

interface GitHubIssue {
  title: string;
  number: number;
  url: string;
  author: string;
  created_at: string;
  body_snippet: string;
}

interface RepoFile {
  path: string;
  size: number;
  type: string;
}

export default function RepoDashboard() {
  const params = useParams();
  const router = useRouter();
  const owner = params.owner as string;
  const repo = params.repo as string;
  const repoUrl = `https://github.com/${owner}/${repo}`;

  const [uiState, setUiState] = useState<UI_STATE>('LOADING_REPO');
  const [repoInfo, setRepoInfo] = useState<{ tree: RepoFile[], issues: GitHubIssue[] } | null>(null);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [selectedFileContent, setSelectedFileContent] = useState<string>("");
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  const [error, setError] = useState("");

  const [issueUrl, setIssueUrl] = useState("");
  const [runConfidence] = useState(true);
  const [running, setRunning] = useState(false);
  const [statusName, setStatusName] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [streamChunks, setStreamChunks] = useState<string[]>([]);
  const [result, setResult] = useState<any>(null);
  const [analyzingFiles, setAnalyzingFiles] = useState<string[]>([]);
  const [terminalExpanded, setTerminalExpanded] = useState(true);
  const [completedSteps, setCompletedSteps] = useState<{step: string, message: string, status: string}[]>([]);
  const [fixedFileView, setFixedFileView] = useState<{path: string, content: string} | null>(null);
  const [sessionId, setSessionId] = useState("");
  const [feedback, setFeedback] = useState("");

  const logsEndRef = useRef<HTMLDivElement>(null);

  // Auto-load repo on mount
  useEffect(() => {
    const loadRepo = async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/repo_info?repo_url=${encodeURIComponent(repoUrl)}`);
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.detail || "Failed to fetch repository info");
        }
        const data = await res.json();
        setRepoInfo(data);
        setUiState('REPO_DASHBOARD');
        if (data.tree && data.tree.length > 0) {
          handleFileClick(data.tree[0].path, repoUrl);
        }
      } catch (err: any) {
        setError(err.message);
      }
    };
    loadRepo();
  }, [owner, repo]);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [streamChunks, statusMessage, running]);

  useEffect(() => {
    if (statusMessage) {
      const pathRegex = /([a-zA-Z0-9._\-/]+\.(py|js|tsx|ts|html|css|json|md))/g;
      const matches = statusMessage.match(pathRegex);
      if (matches) {
        setAnalyzingFiles(prev => [...new Set([...prev, ...matches])]);
        const validPath = matches.find(p => repoInfo?.tree.some(f => f.path === p));
        if (validPath && validPath !== selectedFilePath) {
          handleFileClick(validPath, repoUrl);
        }
      }
    }
  }, [statusMessage]);

  const handleFileClick = async (path: string, url?: string) => {
    const repoUrlToUse = url || repoUrl;
    setSelectedFilePath(path);
    setIsLoadingFile(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/api/file_content?repo_url=${encodeURIComponent(repoUrlToUse)}&file_path=${encodeURIComponent(path)}`);
      if (!res.ok) throw new Error("Failed to fetch file content");
      const data = await res.json();
      setSelectedFileContent(data.content);
    } catch {
      setSelectedFileContent("// Error loading file content...");
    } finally {
      setIsLoadingFile(false);
    }
  };

  const handleAnalyze = (selectedIssueUrl?: string) => {
    const finalIssueUrl = selectedIssueUrl || issueUrl;
    if (!finalIssueUrl) { setError("Please provide an Issue URL"); return; }

    setRunning(true);
    setError("");
    setResult(null);
    setStreamChunks([]);
    setAnalyzingFiles([]);
    setCompletedSteps([]);
    setFixedFileView(null);
    setTerminalExpanded(true);
    setStatusName("Starting");
    setStatusMessage("Connecting to FixFlow API...");

    const params = new URLSearchParams({ issue_url: finalIssueUrl, repo_url: repoUrl, run_confidence: runConfidence.toString() });
    const eventSource = new EventSource(`http://127.0.0.1:8000/api/analyze?${params.toString()}`);
    setupEventSource(eventSource);
  };

  const handleRefine = () => {
    if (!feedback || !sessionId) return;
    setRunning(true);
    setError("");
    setStreamChunks([]);
    setAnalyzingFiles([]);
    setCompletedSteps([]);
    setFixedFileView(null);
    setTerminalExpanded(true);
    setStatusName("Refining");
    setStatusMessage("Sending feedback to FixFlow...");
    const params = new URLSearchParams({ session_id: sessionId, feedback });
    setFeedback("");
    const eventSource = new EventSource(`http://127.0.0.1:8000/api/refine?${params.toString()}`);
    setupEventSource(eventSource);
  };

  const setupEventSource = (eventSource: EventSource) => {
    eventSource.addEventListener("status", (e: Event) => {
      const data = JSON.parse((e as MessageEvent).data);
      const { step, status, message } = data;
      setStatusName(step);
      setStatusMessage(message);
      if (status === "complete" || status === "error") {
        setCompletedSteps(prev => [...prev, { step, status, message }]);
      }
    });
    eventSource.addEventListener("stream", (e: Event) => {
      const data = JSON.parse((e as MessageEvent).data);
      setStreamChunks(prev => [...prev, data.chunk]);
    });
    eventSource.addEventListener("done", (e: Event) => {
      const data = JSON.parse((e as MessageEvent).data);
      const r = data.result;
      setResult(r);
      if (data.session_id) setSessionId(data.session_id);
      if (r?.fixed_files) {
        const paths = Object.keys(r.fixed_files);
        if (paths.length > 0) {
          setFixedFileView({ path: paths[0], content: r.fixed_files[paths[0]] });
          setSelectedFilePath(paths[0]);
        }
      }
    });
    eventSource.addEventListener("error", (e: Event) => {
      const data = JSON.parse((e as MessageEvent).data);
      setError(data.error || "Unknown stream error");
      setRunning(false);
      eventSource.close();
    });
    eventSource.addEventListener("eof", () => {
      setRunning(false);
      setStatusName("Done");
      setStatusMessage("Fix generated — review the highlighted file in the editor.");
      setCompletedSteps(prev => [...prev, { step: "done", status: "complete", message: "Fix generated — review highlighted file!" }]);
      eventSource.close();
    });
    eventSource.addEventListener("heartbeat", () => {});
    eventSource.onerror = (e) => console.error("SSE Error:", e);
  };

  const handleOpenPR = async () => {
    if (!result) return;
    try {
      const res = await fetch("http://127.0.0.1:8000/api/pr", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: repoUrl,
          title: result.issue_title,
          body: result.fix_explanation + "\n\n---\n*Generated autonomously by FixFlow*",
          fixed_files: result.fixed_files
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to create PR");
      window.open(data.url, "_blank");
    } catch (err: any) { alert("Error: " + err.message); }
  };

  // ── Loading Screen ────────────────────────────────────────────────────────
  if (uiState === 'LOADING_REPO') {
    return (
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 24px', borderBottom: '1px solid var(--border-color)', flexShrink: 0 }}>
          <span style={{ fontSize: '1.4rem', cursor: 'pointer' }} onClick={() => router.push('/')}>🔧</span>
          <span style={{ fontWeight: 800, fontSize: '1.2rem', background: 'linear-gradient(135deg, var(--primary), var(--secondary))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>FixFlow</span>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', fontFamily: 'monospace' }}>/ {owner} / {repo}</span>
        </div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 16 }}>
          <div className="loading-spinner" style={{ width: 36, height: 36 }} />
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Cloning <strong style={{ color: 'var(--text-main)' }}>{owner}/{repo}</strong>...</p>
          {error && <div style={{ color: 'var(--error)', fontSize: '0.85rem' }}>❌ {error}</div>}
        </div>
      </div>
    );
  }

  // ── IDE Dashboard ─────────────────────────────────────────────────────────
  if (!repoInfo) return null;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Top Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 24px', borderBottom: '1px solid var(--border-color)', flexShrink: 0 }}>
        <span style={{ fontSize: '1.4rem', cursor: 'pointer' }} onClick={() => router.push('/')}>🔧</span>
        <span style={{ fontWeight: 800, fontSize: '1.2rem', background: 'linear-gradient(135deg, var(--primary), var(--secondary))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>FixFlow</span>
        <span style={{ color: 'var(--border-color)' }}>/</span>
        <a href={repoUrl} target="_blank" rel="noreferrer" style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontFamily: 'monospace', textDecoration: 'none' }}>
          {owner}/<strong style={{ color: 'var(--text-main)' }}>{repo}</strong>
        </a>
        <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text-muted)' }}>{repoInfo.tree.length} files</span>
      </div>

      {/* Main IDE */}
      <div style={{ flex: 1, padding: '16px', display: 'flex', overflow: 'hidden' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr 300px', gap: 16, flex: 1, minHeight: 0 }}>

          {/* Left: Explorer */}
          <div className="glass-panel" style={{ padding: 16, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <h3 style={{ marginBottom: 12, fontSize: '0.8rem', color: 'var(--text-main)', opacity: 0.6, letterSpacing: '0.1em' }}>📁 EXPLORER</h3>
            <div style={{ flex: 1, overflowY: 'auto', fontSize: '0.78rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
              {repoInfo.tree.map((file, i) => {
                const isAnalyzing = analyzingFiles.includes(file.path);
                return (
                  <div
                    key={i}
                    onClick={() => handleFileClick(file.path)}
                    className={isAnalyzing ? 'analyzing-glow' : ''}
                    style={{
                      padding: '5px 8px',
                      cursor: 'pointer',
                      borderRadius: '4px',
                      marginBottom: '1px',
                      backgroundColor: selectedFilePath === file.path ? 'rgba(139, 92, 246, 0.15)' : 'transparent',
                      color: selectedFilePath === file.path ? 'var(--primary)' : 'inherit',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      transition: 'all 0.2s ease'
                    }}
                  >
                    <span style={{ marginRight: 6 }}>{isAnalyzing ? '🧠' : '📄'}</span>
                    {file.path}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Center: Editor + Terminal Drawer */}
          <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div className="terminal-window" style={{ flex: 1, display: 'flex', flexDirection: 'column', borderBottomLeftRadius: 0, borderBottomRightRadius: 0, minHeight: 0 }}>
              <div className="terminal-header">
                <div className="terminal-dot dot-red"></div>
                <div className="terminal-dot dot-yellow"></div>
                <div className="terminal-dot dot-green"></div>
                <div style={{ marginLeft: '12px', fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                  {running && (statusName === '4_fix' || statusName === '4_refine') ? '🔧 Generating Fix...' : selectedFilePath || 'Editor'}
                </div>
              </div>
              <div style={{ flex: 1, overflow: 'auto', backgroundColor: '#0d0d12' }}>
                {fixedFileView && !running ? (
                  <pre style={{ margin: 0, padding: '20px', fontSize: '0.83rem', fontFamily: 'monospace', color: '#a3be8c', lineHeight: '1.6' }}>
                    {fixedFileView.content}
                  </pre>
                ) : running && (statusName === '4_fix' || statusName === '4_refine') && streamChunks.length > 0 ? (
                  <pre style={{ margin: 0, padding: '20px', fontSize: '0.83rem', fontFamily: 'monospace', color: '#a3be8c', lineHeight: '1.6' }}>
                    {streamChunks.join('')}
                    <span style={{ borderRight: '2px solid var(--primary)' }}> </span>
                    <div ref={logsEndRef} />
                  </pre>
                ) : (
                  <pre style={{ margin: 0, padding: '20px', fontSize: '0.83rem', fontFamily: 'monospace', color: '#d1d5db', lineHeight: '1.6' }}>
                    {selectedFileContent || '// Select a file to browse source code'}
                  </pre>
                )}
              </div>
            </div>

            {/* Terminal Drawer */}
            <div className="terminal-drawer" style={{ height: terminalExpanded ? '200px' : '40px', borderRadius: '0 0 12px 12px' }}>
              <div className="terminal-drawer-header" onClick={() => setTerminalExpanded(!terminalExpanded)}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {running && <span className="loading-spinner" style={{ width: 12, height: 12 }} />}
                  <span style={{ color: running ? 'var(--primary)' : 'var(--text-muted)' }}>
                    {statusName ? `AGENT — [${statusName.toUpperCase()}]` : 'FIXFLOW AGENT CONSOLE'}
                  </span>
                </div>
                <span>{terminalExpanded ? '▼' : '▲ Show Progress'}</span>
              </div>
              <div className="terminal-drawer-body" style={{ padding: '10px 16px' }}>
                {completedSteps.map((s, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6, fontSize: '0.78rem' }}>
                    <span style={{ color: s.status === 'error' ? 'var(--error)' : 'var(--success)', flexShrink: 0 }}>
                      {s.status === 'error' ? '✗' : '✓'}
                    </span>
                    <span style={{ color: 'var(--text-muted)' }}>{s.message}</span>
                  </div>
                ))}
                {running && statusMessage && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: '0.78rem' }}>
                    <span className="loading-spinner" style={{ width: 10, height: 10, flexShrink: 0 }} />
                    <span style={{ color: 'var(--primary)' }}>{statusMessage}</span>
                  </div>
                )}
                <div ref={logsEndRef} />
              </div>
            </div>
          </div>

          {/* Right: Discovery or Result */}
          <div className="glass-panel" style={{ padding: 16, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {result && !running ? (
              <>
                <h3 style={{ marginBottom: 6, fontSize: '0.85rem', color: 'var(--success)' }}>✅ FIX READY</h3>
                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 12, lineHeight: 1.5 }}>
                  {result.bug_summary?.slice(0, 150)}...
                </p>
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 6, letterSpacing: '0.1em' }}>CHANGED FILES:</div>
                  {Object.keys(result.fixed_files || {}).map((path) => (
                    <div
                      key={path}
                      onClick={() => setFixedFileView({ path, content: result.fixed_files[path] })}
                      style={{
                        padding: '6px 10px', borderRadius: 6, marginBottom: 4, cursor: 'pointer',
                        fontSize: '0.72rem', fontFamily: 'monospace',
                        backgroundColor: fixedFileView?.path === path ? 'rgba(163, 190, 140, 0.15)' : 'rgba(255,255,255,0.04)',
                        color: fixedFileView?.path === path ? '#a3be8c' : 'var(--text-muted)',
                        border: fixedFileView?.path === path ? '1px solid rgba(163,190,140,0.3)' : '1px solid transparent',
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                      }}
                    >
                      📝 {path}
                    </div>
                  ))}
                </div>
                <div style={{ flex: 1 }} />
                <button type="button" className="glow-btn" style={{ width: '100%', marginBottom: 8, padding: '10px', fontSize: '0.82rem' }} onClick={handleOpenPR}>
                  🚀 Open Pull Request
                </button>
                <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                  <input className="input-field" style={{ flex: 1, padding: '7px 10px', fontSize: '0.75rem' }}
                    placeholder="Refine the fix..." value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleRefine()} />
                  <button type="button" className="glow-btn" style={{ padding: '8px 12px', fontSize: '0.8rem' }} onClick={handleRefine} disabled={!feedback}>↩</button>
                </div>
                <button type="button" style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.72rem' }}
                  onClick={() => { setResult(null); setFixedFileView(null); setCompletedSteps([]); }}>
                  ← Pick another issue
                </button>
              </>
            ) : (
              <>
                <h3 style={{ marginBottom: 12, fontSize: '0.8rem', color: 'var(--text-main)', opacity: 0.6, letterSpacing: '0.1em' }}>🐛 ISSUES</h3>
                <div style={{ flex: 1, overflowY: 'auto' }}>
                  {repoInfo.issues.length === 0 ? (
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', paddingTop: 20 }}>No open issues found.</p>
                  ) : repoInfo.issues.map((issue) => (
                    <div
                      key={issue.number}
                      className="step-card"
                      style={{ cursor: running ? 'default' : 'pointer', padding: '10px', marginBottom: 8, opacity: running ? 0.5 : 1 }}
                      onClick={() => !running && handleAnalyze(issue.url)}
                    >
                      <div style={{ fontWeight: 600, fontSize: '0.78rem', marginBottom: 2 }}>#{issue.number} {issue.title}</div>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>@{issue.author}</div>
                    </div>
                  ))}
                </div>
                {!running && (
                  <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: 12, marginTop: 8 }}>
                    <input className="input-field" style={{ padding: '8px 10px', fontSize: '0.78rem', marginBottom: 8 }}
                      placeholder="Paste issue URL..." value={issueUrl} onChange={(e) => setIssueUrl(e.target.value)} />
                    <button type="button" className="glow-btn" style={{ width: '100%', padding: '9px', fontSize: '0.78rem' }}
                      onClick={() => handleAnalyze()} disabled={!issueUrl}>
                      Analyze
                    </button>
                  </div>
                )}
              </>
            )}
            {error && <div style={{ marginTop: 8, fontSize: '0.75rem', color: 'var(--error)' }}>❌ {error}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
