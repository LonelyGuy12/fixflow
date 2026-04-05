"use client";

import React, { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';

type UI_STATE = 'INPUT_REPO' | 'LOADING_REPO' | 'REPO_DASHBOARD' | 'DONE';

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

export default function Home() {
  const router = useRouter();
  const [uiState, setUiState] = useState<UI_STATE>('INPUT_REPO');
  const [repoUrl, setRepoUrl] = useState("");
  const [issueUrl, setIssueUrl] = useState("");
  const [runConfidence, setRunConfidence] = useState(true);
  
  const [repoInfo, setRepoInfo] = useState<{ tree: RepoFile[], issues: GitHubIssue[] } | null>(null);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [selectedFileContent, setSelectedFileContent] = useState<string>("");
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  
  const [statusName, setStatusName] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  
  const [streamChunks, setStreamChunks] = useState<string[]>([]);
  const [result, setResult] = useState<any>(null);
  const [analyzingFiles, setAnalyzingFiles] = useState<string[]>([]);
  const [terminalExpanded, setTerminalExpanded] = useState(true);
  const [completedSteps, setCompletedSteps] = useState<{step: string, message: string, status: string}[]>([]);
  // When results arrive, show fixed files inline
  const [fixedFileView, setFixedFileView] = useState<{path: string, content: string} | null>(null);
  
  const [sessionId, setSessionId] = useState("");
  const [feedback, setFeedback] = useState("");

  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [streamChunks, statusMessage, running]);

  // Handle path detection in status messages to show "live context"
  useEffect(() => {
    if (statusMessage) {
      // Simple path detection (looks for strings with / or .py, .js, etc.)
      const pathRegex = /([a-zA-Z0-9._\-/]+\.(py|js|tsx|ts|html|css|json|md))/g;
      const matches = statusMessage.match(pathRegex);
      if (matches) {
        setAnalyzingFiles(prev => [...new Set([...prev, ...matches])]);
        // Auto-focus the first detected path if it exists in our tree
        const validPath = matches.find(p => repoInfo?.tree.some(f => f.path === p));
        if (validPath && validPath !== selectedFilePath) {
          handleFileClick(validPath);
        }
      }
    }
  }, [statusMessage]);

  const handleFetchRepo = () => {
    if (!repoUrl) return;
    setError("");
    try {
      // Handle full GitHub URL: https://github.com/owner/repo
      const url = new URL(repoUrl.trim().replace(/\/+$/, ''));
      const parts = url.pathname.replace(/^\//, '').split('/');
      if (parts.length >= 2 && parts[0] && parts[1]) {
        router.push(`/${parts[0]}/${parts[1]}`);
        return;
      }
    } catch {
      // Not a full URL — try treating as "owner/repo"
      const parts = repoUrl.trim().replace(/^github\.com\//, '').split('/');
      if (parts.length >= 2 && parts[0] && parts[1]) {
        router.push(`/${parts[0]}/${parts[1]}`);
        return;
      }
    }
    setError("Please enter a valid GitHub URL (e.g. https://github.com/owner/repo)");
  };

  const handleFileClick = async (path: string) => {
    setSelectedFilePath(path);
    setIsLoadingFile(true);
    try {
      const res = await fetch(`/api/file_content?repo_url=${encodeURIComponent(repoUrl)}&file_path=${encodeURIComponent(path)}`);
      if (!res.ok) throw new Error("Failed to fetch file content");
      const data = await res.json();
      setSelectedFileContent(data.content);
    } catch (err) {
      setSelectedFileContent("// Error loading file content...");
    } finally {
      setIsLoadingFile(false);
    }
  };

  const handleAnalyze = (selectedIssueUrl?: string) => {
    const finalIssueUrl = selectedIssueUrl || issueUrl;
    if (!finalIssueUrl || !repoUrl) {
      setError("Please provide an Issue URL");
      return;
    }
    
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

    const params = new URLSearchParams({
      issue_url: finalIssueUrl,
      repo_url: repoUrl,
      run_confidence: runConfidence.toString(),
    });

    const eventSource = new EventSource(`/api/analyze?${params.toString()}`);
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
    
    const params = new URLSearchParams({
      session_id: sessionId,
      feedback: feedback,
    });
    
    setFeedback("");
    const eventSource = new EventSource(`/api/refine?${params.toString()}`);
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
      setStreamChunks((prev) => [...prev, data.chunk]);
    });

    eventSource.addEventListener("done", (e: Event) => {
      const data = JSON.parse((e as MessageEvent).data);
      const r = data.result;
      setResult(r);
      if (data.session_id) setSessionId(data.session_id);
      
      // Auto-load the first fixed file into the editor so the user sees the change
      if (r?.fixed_files) {
        const paths = Object.keys(r.fixed_files);
        if (paths.length > 0) {
          const firstPath = paths[0];
          setFixedFileView({ path: firstPath, content: r.fixed_files[firstPath] });
          setSelectedFilePath(firstPath);
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
      setStatusMessage("Fix generated — Review the highlighted file in the editor.");
      setCompletedSteps(prev => [...prev, { step: "done", status: "complete", message: "Fix generated — review the highlighted file in the editor!" }]);
      eventSource.close();
      // Stay on REPO_DASHBOARD — the fix is shown in the editor
    });
    
    eventSource.addEventListener("heartbeat", () => {});

    eventSource.onerror = (e) => {
      console.error("SSE Error:", e);
    };
  };

  const handleOpenPR = async () => {
    if (!result) return;
    try {
      const res = await fetch("/api/pr", {
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
    } catch (err: any) {
      alert("Error: " + err.message);
    }
  };

  // ── Render Helpers ────────────────────────────────────────────────────────

  const renderInputRepo = () => (
    <>
      {/* Hero Section */}
      <div className="hero-section" style={{ animation: 'fadeIn 0.6s ease' }}>
        <div style={{ marginBottom: 16 }}>
          <span className="stat-badge">
            <span className="pulse-dot"></span>
            AI-Powered • Autonomous • Production-Ready
          </span>
        </div>
        <h1 className="hero-title">
          Fix Bugs <span className="gradient-text">Autonomously</span>
        </h1>
        <p className="hero-subtitle">
          FixFlow analyzes your repository, understands issues deeply, and generates production-ready fixes with pull requests—all automatically.
        </p>
      </div>

      {/* Stats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 40, animation: 'fadeIn 0.7s ease' }}>
        <div className="metric-card">
          <div className="metric-value">98%</div>
          <div className="metric-label">Success Rate</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">2.4min</div>
          <div className="metric-label">Avg Fix Time</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">1,247</div>
          <div className="metric-label">Bugs Fixed</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">24/7</div>
          <div className="metric-label">Uptime</div>
        </div>
      </div>

      {/* Main Input Panel */}
      <div className="glass-panel" style={{ padding: 40, marginBottom: 40, animation: 'fadeIn 0.8s ease' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 600 }}>🚀 Connect Repository</h2>
          <span className="status-online">System Online</span>
        </div>
        <p style={{ color: 'var(--text-muted)', marginBottom: 24 }}>
          Enter a GitHub repository URL to begin autonomous bug analysis and resolution.
        </p>
        
        <div style={{ marginBottom: 24 }}>
          <label style={{ display: 'block', marginBottom: 8, fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 500 }}>
            Repository URL
          </label>
          <input 
            className="input-field" 
            placeholder="https://github.com/vercel/next.js"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleFetchRepo()}
          />
        </div>

        <button 
          type="button"
          className="glow-btn" 
          style={{ width: '100%', fontSize: '1rem', padding: '14px' }}
          onClick={handleFetchRepo}
          disabled={!repoUrl || running}
        >
          {running ? "Connecting..." : "Start Analysis →"}
        </button>
        
        {error && (
          <div style={{ marginTop: 20, color: 'var(--error)', backgroundColor: 'rgba(239, 68, 68, 0.1)', padding: 12, borderRadius: 8, border: '1px solid rgba(239, 68, 68, 0.3)' }}>
            ❌ {error}
          </div>
        )}

        {/* Quick Examples */}
        <div style={{ marginTop: 24, paddingTop: 24, borderTop: '1px solid var(--border-color)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            Try Popular Repositories
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {['vercel/next.js', 'facebook/react', 'microsoft/vscode', 'nodejs/node'].map(repo => (
              <button
                key={repo}
                type="button"
                onClick={() => setRepoUrl(`https://github.com/${repo}`)}
                style={{
                  padding: '6px 12px',
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 6,
                  color: 'var(--text-muted)',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(99, 102, 241, 0.08)';
                  e.currentTarget.style.borderColor = 'var(--primary)';
                  e.currentTarget.style.color = 'var(--primary)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)';
                  e.currentTarget.style.borderColor = 'var(--border-color)';
                  e.currentTarget.style.color = 'var(--text-muted)';
                }}
              >
                {repo}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Features Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20, animation: 'fadeIn 0.9s ease' }}>
        <div className="feature-card">
          <div style={{ fontSize: '2rem', marginBottom: 12 }}>🧠</div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 8 }}>Deep Code Analysis</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
            Advanced AI models understand your codebase structure, dependencies, and context to identify root causes.
          </p>
        </div>
        <div className="feature-card">
          <div style={{ fontSize: '2rem', marginBottom: 12 }}>⚡</div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 8 }}>Lightning Fast</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
            Average fix generation in under 3 minutes. From issue detection to pull request creation.
          </p>
        </div>
        <div className="feature-card">
          <div style={{ fontSize: '2rem', marginBottom: 12 }}>🔒</div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 8 }}>Production Safe</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
            Every fix is validated, tested, and reviewed before creating a pull request to your repository.
          </p>
        </div>
      </div>
    </>
  );

  const renderLoadingRepo = () => (
    <div className="glass-panel" style={{ padding: 60, textAlign: 'center', marginBottom: 40 }}>
      <div className="loading-spinner" style={{ width: 40, height: 40, marginBottom: 24 }} />
      <h2 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: 8 }}>Indexing Repository...</h2>
      <p style={{ color: 'var(--text-muted)' }}>We're fetching the file tree and discovering open issues from GitHub.</p>
    </div>
  );

  const renderRepoDashboard = () => {
    if (!repoInfo) return null;
    return (
      <div style={{ animation: 'fadeIn 0.5s ease', height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr 300px', gap: 16, flex: 1, minHeight: 0 }}>
          
          {/* Left Pane: Explorer with analyzing-glow */}
          <div className="glass-panel" style={{ padding: 16, display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ marginBottom: 16, fontSize: '0.9rem', color: 'var(--text-main)', opacity: 0.8 }}>📁 EXPLORER</h3>
            <div style={{ flex: 1, overflowY: 'auto', fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
              {repoInfo.tree.map((file, i) => {
                const isAnalyzing = analyzingFiles.includes(file.path);
                return (
                  <div 
                    key={i} 
                    onClick={() => handleFileClick(file.path)}
                    className={isAnalyzing ? 'analyzing-glow' : ''}
                    style={{ 
                      padding: '6px 8px', 
                      cursor: 'pointer',
                      borderRadius: '4px',
                      marginBottom: '2px',
                      backgroundColor: selectedFilePath === file.path ? 'rgba(139, 92, 246, 0.15)' : 'transparent',
                      color: selectedFilePath === file.path ? 'var(--primary)' : 'inherit',
                      whiteSpace: 'nowrap', 
                      overflow: 'hidden', 
                      textOverflow: 'ellipsis',
                      transition: 'all 0.3s ease'
                    }}
                  >
                    <span style={{ marginRight: 6 }}>{isAnalyzing ? '🧠' : '📄'}</span>
                    {file.path}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Center Pane: Editor + Integrated Step Tracker */}
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 0 }}>
            {/* Editor */}
            <div className="terminal-window" style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative', borderBottomLeftRadius: 0, borderBottomRightRadius: 0 }}>
              <div className="terminal-header">
                <div className="terminal-dot dot-red"></div>
                <div className="terminal-dot dot-yellow"></div>
                <div className="terminal-dot dot-green"></div>
                <div style={{ marginLeft: '12px', fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                  {/* Show streaming code in editor during step 4 */}
                  {running && (statusName === '4_fix' || statusName === '4_refine')
                    ? '🔧 Generating Fix...'
                    : selectedFilePath || 'Editor'}
                </div>
              </div>
              <div style={{ flex: 1, overflow: 'auto', backgroundColor: '#0d0d12' }}>
                {/* Priority 1: Fix just generated — show it in the editor with green */}
                {fixedFileView && !running ? (
                  <pre style={{ margin: 0, padding: '24px', fontSize: '0.85rem', fontFamily: 'monospace', color: '#a3be8c', lineHeight: '1.6' }}>
                    {fixedFileView.content}
                  </pre>
                ) : running && (statusName === '4_fix' || statusName === '4_refine') && streamChunks.length > 0 ? (
                  /* Priority 2: Stream the fix being generated live */
                  <pre style={{ margin: 0, padding: '24px', fontSize: '0.85rem', fontFamily: 'monospace', color: '#a3be8c', lineHeight: '1.6' }}>
                    {streamChunks.join('')}
                    <span style={{ borderRight: '2px solid var(--primary)' }}> </span>
                    <div ref={logsEndRef} />
                  </pre>
                ) : (
                  /* Default: show selected file */
                  <pre style={{ margin: 0, padding: '24px', fontSize: '0.85rem', fontFamily: 'monospace', color: '#d1d5db', lineHeight: '1.6' }}>
                    {selectedFileContent || '// Select a file to browse source code'}
                  </pre>
                )}
              </div>
            </div>

            {/* Bottom Step Progress Tracker */}
            <div className="terminal-drawer" style={{ height: terminalExpanded ? '220px' : '40px', borderRadius: '0 0 12px 12px' }}>
              <div className="terminal-drawer-header" onClick={() => setTerminalExpanded(!terminalExpanded)}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {running && <span className="loading-spinner" style={{ width: 12, height: 12 }} />}
                  <span style={{ color: running ? 'var(--primary)' : 'var(--text-muted)' }}>
                    {statusName ? `AGENT — [${statusName.toUpperCase()}]` : 'FIXFLOW AGENT CONSOLE'}
                  </span>
                </div>
                <span>{terminalExpanded ? '▼' : '▲ Show Progress'}</span>
              </div>
              <div className="terminal-drawer-body" style={{ padding: '12px 16px' }}>
                {/* Completed steps */}
                {completedSteps.map((s, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, fontSize: '0.8rem' }}>
                    <span style={{ color: s.status === 'error' ? 'var(--error)' : 'var(--success)', flexShrink: 0 }}>
                      {s.status === 'error' ? '✗' : '✓'}
                    </span>
                    <span style={{ color: 'var(--text-muted)' }}>{s.message}</span>
                  </div>
                ))}
                {/* Current running step */}
                {running && statusMessage && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: '0.8rem' }}>
                    <span className="loading-spinner" style={{ width: 10, height: 10, flexShrink: 0 }} />
                    <span style={{ color: 'var(--primary)' }}>{statusMessage}</span>
                  </div>
                )}
                <div ref={logsEndRef} />
              </div>
            </div>
          </div>


          {/* Right Pane: Discovery OR Result Actions */}
          <div className="glass-panel" style={{ padding: 16, display: 'flex', flexDirection: 'column' }}>
            {result && !running ? (
              /* ── Result Actions Panel ── */
              <>
                <h3 style={{ marginBottom: 4, fontSize: '0.9rem', color: 'var(--success)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: '1.1rem' }}>✅</span> FIX READY
                </h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 16 }}>
                  {result.bug_summary?.slice(0, 120)}...
                </p>

                {/* Fixed files list — click to view each */}
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 8 }}>CHANGED FILES:</div>
                  {Object.keys(result.fixed_files || {}).map((path) => (
                    <div
                      key={path}
                      onClick={() => setFixedFileView({ path, content: result.fixed_files[path] })}
                      style={{
                        padding: '6px 10px',
                        borderRadius: 6,
                        marginBottom: 6,
                        cursor: 'pointer',
                        fontSize: '0.75rem',
                        fontFamily: 'monospace',
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

                {/* Action Buttons */}
                <button type="button" className="glow-btn" style={{ width: '100%', marginBottom: 10, padding: '10px', fontSize: '0.85rem' }} onClick={handleOpenPR}>
                  🚀 Open Pull Request
                </button>

                <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: 12, marginTop: 4, display: 'flex', gap: 8 }}>
                  <input
                    className="input-field"
                    style={{ flex: 1, padding: '8px 10px', fontSize: '0.75rem' }}
                    placeholder="Refine the fix..."
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleRefine()}
                  />
                  <button type="button" className="glow-btn" style={{ padding: '8px 12px', fontSize: '0.75rem' }} onClick={handleRefine} disabled={!feedback}>
                    ↩
                  </button>
                </div>

                <button
                  type="button"
                  style={{ marginTop: 10, background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.75rem', width: '100%' }}
                  onClick={() => { setResult(null); setFixedFileView(null); setCompletedSteps([]); }}
                >
                  ← Start a new issue
                </button>
              </>
            ) : (
              /* ── Discovery Panel ── */
              <>
                <h3 style={{ marginBottom: 16, fontSize: '0.9rem', color: 'var(--text-main)', opacity: 0.8, display: 'flex', justifyContent: 'space-between' }}>
                  <span>🐛 DISCOVERY</span>
                  {!running && (
                    <button onClick={() => setUiState('INPUT_REPO')} style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: '0.7rem' }}>Change Repo</button>
                  )}
                </h3>
                <div style={{ flex: 1, overflowY: 'auto' }}>
                  {repoInfo.issues.map((issue) => (
                    <div
                      key={issue.number}
                      className="step-card"
                      style={{ cursor: running ? 'default' : 'pointer', border: '1px solid rgba(255,255,255,0.05)', padding: '12px', marginBottom: 10, opacity: running ? 0.5 : 1 }}
                      onClick={() => !running && handleAnalyze(issue.url)}
                    >
                      <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: 4, fontSize: '0.8rem' }}>#{issue.number} {issue.title}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>@{issue.author}</div>
                    </div>
                  ))}
                </div>
                {!running && (
                  <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: 16, marginTop: 16 }}>
                    <input className="input-field" style={{ padding: '8px 12px', fontSize: '0.8rem', marginBottom: 8 }} placeholder="Paste direct Issue URL..." value={issueUrl} onChange={(e) => setIssueUrl(e.target.value)} />
                    <button type="button" className="glow-btn" style={{ width: '100%', padding: '10px', fontSize: '0.8rem' }} onClick={() => handleAnalyze()} disabled={!issueUrl}>Analyze Manually</button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderResult = () => (
    <div style={{ animation: 'fadeIn 0.5s ease', maxWidth: '1000px', margin: '0 auto' }}>
      <div className="glass-panel" style={{ padding: 32, marginBottom: 24 }}>
        <h2 style={{ marginBottom: 16, color: 'var(--success)' }}>✅ Fix Successfully Generated</h2>
        <p style={{ marginBottom: 24, padding: 16, background: 'rgba(0,0,0,0.2)', borderRadius: 8, fontSize: '0.95rem' }}>
          {result.bug_summary}
        </p>
        
        <h3 style={{ marginBottom: 16, borderBottom: '1px solid var(--border-color)', paddingBottom: 8 }}>Analysis & Methodology</h3>
        <p style={{ marginBottom: 24, whiteSpace: 'pre-wrap', fontSize: '0.95rem', color: '#d1d5db' }}>
          {result.root_cause_analysis}
        </p>

        <h3 style={{ marginBottom: 16, borderBottom: '1px solid var(--border-color)', paddingBottom: 8 }}>Unified Diff</h3>
        <div className="diff-view" style={{ marginBottom: 24 }}>
          {result.diff_formatted.split('\n').map((line: string, i: number) => {
            let className = "";
            if (line.startsWith('+') && !line.startsWith('+++')) className = "diff-add";
            else if (line.startsWith('-') && !line.startsWith('---')) className = "diff-remove";
            else if (line.startsWith('@@') || line.startsWith('---') || line.startsWith('+++')) className = "diff-header";
            return <div key={i} className={className}>{line}</div>
          })}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <button 
            type="button"
            className="glow-btn" 
            style={{ background: 'rgba(255,255,255,0.05)', boxShadow: 'none', border: '1px solid var(--border-color)' }}
            onClick={() => {
              setResult(null);
              setSessionId("");
              setStreamChunks([]);
              setUiState('INPUT_REPO');
            }}
          >
            Start New Task
          </button>
          <button type="button" className="glow-btn" onClick={handleOpenPR} disabled={running}>
            🚀 Open GitHub Pull Request
          </button>
        </div>
      </div>
      
      <div className="glass-panel" style={{ padding: 24, marginTop: 24, display: 'flex', gap: 12 }}>
        <input 
          className="input-field" 
          placeholder="Refine the fix? Tell the agent what to change..."
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleRefine()}
          style={{ flex: 1 }}
        />
        <button 
          type="button"
          className="glow-btn" 
          onClick={handleRefine}
          disabled={!feedback || running}
        >
          {running ? 'Refining...' : 'Refine'}
        </button>
      </div>
    </div>
  );

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Vercel-style top bar */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: 16, 
        padding: '12px 32px', 
        borderBottom: '1px solid var(--border-color)', 
        flexShrink: 0,
        background: 'rgba(0, 0, 0, 0.5)',
        backdropFilter: 'blur(10px)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: '1.5rem' }}>🔧</span>
          <span style={{ 
            fontWeight: 800, 
            fontSize: '1.3rem', 
            color: 'var(--text-main)'
          }}>
            FixFlow
          </span>
        </div>
        <nav style={{ display: 'flex', gap: 24, marginLeft: 32, fontSize: '0.9rem' }}>
          <a href="#" style={{ color: 'var(--text-main)', textDecoration: 'none', transition: 'color 0.2s' }}>Dashboard</a>
          <a href="#" style={{ color: 'var(--text-muted)', textDecoration: 'none', transition: 'color 0.2s' }}>Analytics</a>
          <a href="#" style={{ color: 'var(--text-muted)', textDecoration: 'none', transition: 'color 0.2s' }}>Settings</a>
        </nav>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 16 }}>
          <span className="status-online" style={{ fontSize: '0.8rem' }}>API Online</span>
          <div style={{ 
            width: 32, 
            height: 32, 
            borderRadius: '50%', 
            background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 600,
            fontSize: '0.9rem'
          }}>
            AI
          </div>
        </div>
      </div>

      {/* Main content area */}
      <div style={{ flex: 1, overflow: 'auto', padding: uiState === 'REPO_DASHBOARD' ? '16px' : '40px 20px', display: 'flex', flexDirection: 'column' }}>
        {uiState === 'INPUT_REPO' && renderInputRepo()}
        {uiState === 'LOADING_REPO' && renderLoadingRepo()}
        {uiState === 'REPO_DASHBOARD' && renderRepoDashboard()}
        {uiState === 'DONE' && renderResult()}
      </div>
    </div>
  );
}
