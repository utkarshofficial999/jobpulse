import React, { useState, useEffect } from 'react';
import { 
  Briefcase, 
  Send, 
  Search, 
  Cpu, 
  CheckCircle, 
  Sparkles, 
  ExternalLink, 
  Bookmark, 
  X, 
  RefreshCw, 
  MapPin, 
  Wifi, 
  FileText, 
  Layers,
  Bell,
  Clock,
  Check,
  ShieldCheck,
  Flame
} from 'lucide-react';
import './App.css';

const ROLE_OPTIONS = [
  "Senior Backend Engineer",
  "Staff Software Engineer",
  "Fullstack Engineer",
  "AI / ML Engineer",
  "Platform & DevOps",
  "Product Engineer",
  "Data Engineer"
];

const SENIORITY_OPTIONS = ["intern", "entry", "mid", "senior", "lead", "staff"];
const REMOTE_OPTIONS = ["remote", "hybrid", "onsite"];

export default function App() {
  const [activeTab, setActiveTab] = useState('studio'); // 'studio' | 'feed' | 'engine'
  
  // Candidate Profile State
  const [userId, setUserId] = useState(null);
  const [email, setEmail] = useState('utkarsh.candidate@pulseai.dev');
  const [fullName, setFullName] = useState('Utkarsh');
  const [telegramId, setTelegramId] = useState('8351653703');
  const [selectedRoles, setSelectedRoles] = useState(['Senior Backend Engineer', 'Staff Software Engineer']);
  const [selectedSeniorities, setSelectedSeniorities] = useState(['senior', 'staff']);
  const [selectedRemote, setSelectedRemote] = useState(['remote']);
  const [resumeText, setResumeText] = useState(
    "Senior Backend Engineer with 7 years of deep experience in Python, FastAPI, PostgreSQL, Redis, Celery, and Docker. Architected high-throughput microservices and distributed queue pipelines handling 50k requests/sec."
  );
  const [extractedSkills, setExtractedSkills] = useState(['Python', 'FastAPI', 'PostgreSQL', 'Redis', 'Celery', 'Docker']);
  const [hasEmbedding, setHasEmbedding] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  // Matches State
  const [matches, setMatches] = useState([]);
  const [isLoadingMatches, setIsLoadingMatches] = useState(false);
  const [alertSuccess, setAlertSuccess] = useState(null);
  const [isDispatchingAlert, setIsDispatchingAlert] = useState(false);

  // Job Feed State
  const [feedJobs, setFeedJobs] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);

  // Engine Operations State
  const [engineLogs, setEngineLogs] = useState([]);
  const [isEngineRunning, setIsEngineRunning] = useState(false);

  const addLog = (msg) => {
    setEngineLogs(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev.slice(0, 15)]);
  };

  // 1. Initialize or Register User on Mount
  useEffect(() => {
    initUser();
  }, []);

  const initUser = async () => {
    try {
      const res = await fetch('/api/users/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: `candidate.${Date.now().toString().slice(-4)}@pulseai.dev`,
          full_name: fullName,
          telegram_chat_id: `tg_${Date.now().toString().slice(-5)}`,
          alert_frequency: 'daily_9am',
          timezone: 'America/New_York',
          profile: {
            target_roles: selectedRoles,
            target_seniorities: selectedSeniorities,
            preferred_remote_types: selectedRemote,
            preferred_locations: ['Remote - US'],
            raw_resume_text: resumeText,
            min_similarity_score: 0.35
          }
        })
      });
      if (res.ok) {
        const data = await res.json();
        setUserId(data.id);
        if (data.profile) {
          setExtractedSkills(data.profile.parsed_skills || []);
          setHasEmbedding(data.profile.has_embedding);
        }
        fetchMatches(data.id);
      }
    } catch (err) {
      console.error("Init user error:", err);
    }
  };

  // 2. Save Profile & Re-embed
  const handleSaveProfile = async () => {
    if (!userId) return;
    setIsSavingProfile(true);
    try {
      const res = await fetch(`/api/users/${userId}/profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_roles: selectedRoles,
          target_seniorities: selectedSeniorities,
          preferred_remote_types: selectedRemote,
          preferred_locations: ['Remote - US'],
          raw_resume_text: resumeText,
          min_similarity_score: 0.35
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setExtractedSkills(updated.parsed_skills || []);
        setHasEmbedding(true);
        fetchMatches(userId);
      }
    } catch (err) {
      console.error("Save profile error:", err);
    } finally {
      setIsSavingProfile(false);
    }
  };

  // 3. Fetch Matches
  const fetchMatches = async (targetUserId = userId) => {
    if (!targetUserId) return;
    setIsLoadingMatches(true);
    try {
      const res = await fetch(`/api/users/${targetUserId}/matches?limit=10`);
      if (res.ok) {
        const data = await res.json();
        setMatches(data);
      }
    } catch (err) {
      console.error("Fetch matches error:", err);
    } finally {
      setIsLoadingMatches(false);
    }
  };

  // 4. Trigger 9 AM Digest Test Alert
  const handleTriggerAlert = async () => {
    if (!userId) return;
    setIsDispatchingAlert(true);
    setAlertSuccess(null);
    try {
      const res = await fetch(`/api/users/${userId}/trigger-digest`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setAlertSuccess(data);
      }
    } catch (err) {
      console.error("Trigger alert error:", err);
    } finally {
      setIsDispatchingAlert(false);
    }
  };

  // 5. User Feedback (Dismiss or Save)
  const handleFeedback = async (jobId, action) => {
    if (!userId) return;
    try {
      await fetch(`/api/users/${userId}/feedback?job_id=${jobId}&action=${action}`, { method: 'POST' });
      if (action === 'dismissed') {
        setMatches(prev => prev.filter(m => m.job_id !== jobId));
      }
    } catch (err) {
      console.error("Feedback error:", err);
    }
  };

  // 6. Fetch Job Feed or Search
  const fetchFeedJobs = async (query = '') => {
    setIsSearching(true);
    try {
      const endpoint = query ? `/api/jobs/search?q=${encodeURIComponent(query)}&limit=15` : `/api/jobs/?limit=20`;
      const res = await fetch(endpoint);
      if (res.ok) {
        const data = await res.json();
        setFeedJobs(data);
      }
    } catch (err) {
      console.error("Fetch feed error:", err);
    } finally {
      setIsSearching(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'feed') {
      fetchFeedJobs(searchQuery);
    }
  }, [activeTab]);

  // 7. Engine Operations Handlers
  const runOperation = async (name, endpoint, method = 'POST') => {
    setIsEngineRunning(true);
    addLog(`Initiating ${name}...`);
    try {
      const res = await fetch(endpoint, { method });
      const data = await res.json();
      addLog(`✓ ${name} completed: ${JSON.stringify(data)}`);
    } catch (err) {
      addLog(`✕ ${name} error: ${err.message}`);
    } finally {
      setIsEngineRunning(false);
    }
  };

  // Toggle Helpers
  const toggleRole = (r) => {
    setSelectedRoles(prev => prev.includes(r) ? prev.filter(x => x !== r) : [...prev, r]);
  };
  const toggleSeniority = (s) => {
    setSelectedSeniorities(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);
  };
  const toggleRemote = (rem) => {
    setSelectedRemote(prev => prev.includes(rem) ? prev.filter(x => x !== rem) : [...prev, rem]);
  };

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="logo-section">
          <div className="logo-icon-box">
            <Flame className="w-6 h-6 text-white" size={24} color="#FFF" />
          </div>
          <div>
            <div className="logo-title">
              Pulse <span className="gradient-text">AI</span>
              <span className="pipeline-badge">
                <span className="live-dot"></span> Pipeline Active
              </span>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Autonomous ATS Ingestion • Cross-Source Deduplication • 9 AM Telegram & Email Alerts
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="nav-tabs">
          <button 
            className={`nav-tab-btn ${activeTab === 'studio' ? 'active' : ''}`}
            onClick={() => setActiveTab('studio')}
          >
            <Sparkles size={16} /> Candidate Studio
          </button>
          <button 
            className={`nav-tab-btn ${activeTab === 'feed' ? 'active' : ''}`}
            onClick={() => setActiveTab('feed')}
          >
            <Briefcase size={16} /> Live Discovery Feed
          </button>
          <button 
            className={`nav-tab-btn ${activeTab === 'engine' ? 'active' : ''}`}
            onClick={() => setActiveTab('engine')}
          >
            <Cpu size={16} /> Engine Operations
          </button>
        </nav>
      </header>

      {/* Main Tab Views */}
      {activeTab === 'studio' && (
        <div>
          {/* Alert Success Banner */}
          {alertSuccess && (
            <div className="notification-banner">
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <CheckCircle size={24} color="#10B981" />
                <div>
                  <h4 style={{ color: '#F8FAFC', fontSize: '15px' }}>
                    9 AM Digest Dispatched via {alertSuccess.channel.toUpperCase()}!
                  </h4>
                  <p style={{ fontSize: '13px', color: '#94A3B8' }}>
                    Delivered {alertSuccess.matches_count} high-confidence opportunities to recipient <code>{alertSuccess.recipient}</code>. Outbox ID: <code>{alertSuccess.outbox_id?.slice(0, 8)}...</code>
                  </p>
                </div>
              </div>
              <button 
                onClick={() => setAlertSuccess(null)}
                style={{ background: 'transparent', border: 'none', color: '#94A3B8', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>
          )}

          <div className="studio-grid">
            {/* Left Column: Candidate Onboarding & Preferences */}
            <div className="glass-panel form-card">
              <div className="section-header">
                <h2><Sparkles size={20} color="#818CF8" /> Candidate Profile & Intent</h2>
                <p>Upload your resume and customize role targeting for reverse matching.</p>
              </div>

              {/* Target Roles */}
              <div className="form-group">
                <label className="form-label">Target Roles</label>
                <div className="pill-grid">
                  {ROLE_OPTIONS.map(role => (
                    <button
                      key={role}
                      type="button"
                      className={`pill-btn ${selectedRoles.includes(role) ? 'selected' : ''}`}
                      onClick={() => toggleRole(role)}
                    >
                      {role}
                    </button>
                  ))}
                </div>
              </div>

              {/* Seniority */}
              <div className="form-group">
                <label className="form-label">Seniority Preference</label>
                <div className="pill-grid">
                  {SENIORITY_OPTIONS.map(sen => (
                    <button
                      key={sen}
                      type="button"
                      className={`pill-btn ${selectedSeniorities.includes(sen) ? 'selected' : ''}`}
                      onClick={() => toggleSeniority(sen)}
                    >
                      {sen.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              {/* Remote Preference */}
              <div className="form-group">
                <label className="form-label">Workplace Policy</label>
                <div className="pill-grid">
                  {REMOTE_OPTIONS.map(rem => (
                    <button
                      key={rem}
                      type="button"
                      className={`pill-btn ${selectedRemote.includes(rem) ? 'selected' : ''}`}
                      onClick={() => toggleRemote(rem)}
                    >
                      <Wifi size={13} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
                      {rem.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              {/* Resume Ingestion */}
              <div className="form-group">
                <label className="form-label">Resume & Experience Text</label>
                <textarea
                  className="form-textarea"
                  value={resumeText}
                  onChange={(e) => setResumeText(e.target.value)}
                  placeholder="Paste work experience, technologies, accomplishments or resume summary..."
                />
              </div>

              {/* Extracted Skills Visualizer */}
              {extractedSkills.length > 0 && (
                <div className="form-group">
                  <label className="form-label">Extracted Core Skills ({extractedSkills.length})</label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {extractedSkills.map(skill => (
                      <span key={skill} className="skill-chip">
                        <Check size={12} /> {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Telegram & Email Channel Setup */}
              <div className="form-group">
                <label className="form-label">9:00 AM Alert Recipient</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <input
                    className="form-input"
                    value={telegramId}
                    onChange={(e) => setTelegramId(e.target.value)}
                    placeholder="Telegram Chat ID"
                  />
                  <input
                    className="form-input"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Email Address"
                  />
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                  Connected to transactional outbox dispatcher with exponential retry backoff.
                </div>
              </div>

              {/* Save & Embed Button */}
              <button
                className="btn-primary"
                style={{ width: '100%', marginTop: '8px' }}
                onClick={handleSaveProfile}
                disabled={isSavingProfile}
              >
                {isSavingProfile ? (
                  <>Embedding Intent Vector...</>
                ) : (
                  <>
                    <Cpu size={16} /> Save Profile & Generate 384-D Vector
                  </>
                )}
              </button>
            </div>

            {/* Right Column: Ranked Matches & 9 AM Alert Center */}
            <div>
              {/* Action Banner */}
              <div className="glass-panel" style={{ padding: '20px 24px', marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px' }}>
                <div>
                  <h3 style={{ fontSize: '18px', color: 'var(--text-primary)' }}>Personalized Match Stream</h3>
                  <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                    Ranked by Vector Cosine (60%) + Title Match (25%) + Recency Factor (15%)
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button 
                    className="btn-secondary"
                    onClick={() => fetchMatches(userId)}
                    disabled={isLoadingMatches}
                  >
                    <RefreshCw size={15} className={isLoadingMatches ? 'animate-spin' : ''} />
                    Refresh Matches
                  </button>
                  <button 
                    className="btn-primary btn-outline-emerald"
                    onClick={handleTriggerAlert}
                    disabled={isDispatchingAlert || matches.length === 0}
                  >
                    <Send size={15} />
                    {isDispatchingAlert ? 'Dispatching...' : 'Trigger 9 AM Alert Now'}
                  </button>
                </div>
              </div>

              {/* Matches List */}
              {isLoadingMatches ? (
                <div className="glass-panel" style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <RefreshCw size={32} style={{ animation: 'spin 1s infinite linear', margin: '0 auto 16px' }} />
                  <p>Running reverse matching engine across canonical jobs...</p>
                </div>
              ) : matches.length === 0 ? (
                <div className="glass-panel" style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <Briefcase size={36} style={{ margin: '0 auto 16px', opacity: 0.4 }} />
                  <p>No matches found matching your current hard filters. Try adding more target roles or updating seniority!</p>
                </div>
              ) : (
                <div className="matches-feed">
                  {matches.map(m => {
                    const matchPercent = Math.round((m.scores?.final_score || 0) * 100);
                    return (
                      <div key={m.job_id} className="glass-panel job-card">
                        <div className="job-card-header">
                          <div>
                            <div className="job-company">
                              <ShieldCheck size={14} color="#06B6D4" /> {m.company}
                            </div>
                            <h3 className="job-title">{m.title}</h3>
                          </div>
                          <div className="match-score-badge">
                            <span className="match-score-num">{matchPercent}%</span>
                            <span className="match-score-label">Match Score</span>
                          </div>
                        </div>

                        {/* Metadata row */}
                        <div className="job-meta-row">
                          <span className="meta-item">
                            <Wifi size={14} color="#A5B4FC" /> {m.remote_type?.toUpperCase()}
                          </span>
                          <span className="meta-item">
                            <Briefcase size={14} color="#A5B4FC" /> {m.seniority?.toUpperCase()}
                          </span>
                          {m.locations && m.locations.length > 0 && (
                            <span className="meta-item">
                              <MapPin size={14} color="#A5B4FC" /> {m.locations.join(', ')}
                            </span>
                          )}
                        </div>

                        {/* Match Reasons */}
                        {m.reasons && (
                          <div className="job-explanation">
                            💡 <strong>Match Rationale:</strong> {m.reasons}
                          </div>
                        )}

                        {/* Matched skills */}
                        {m.matched_skills && m.matched_skills.length > 0 && (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '14px' }}>
                            {m.matched_skills.map(s => (
                              <span key={s} className="skill-chip">
                                <Check size={12} /> {s}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Actions and Breakdown */}
                        <div className="job-actions">
                          <div className="score-breakdown">
                            <div>Vec: <span>{m.scores?.vector_similarity?.toFixed(2)}</span></div>
                            <div>Title: <span>{m.scores?.title_keyword_score?.toFixed(2)}</span></div>
                            <div>Recency: <span>{m.scores?.recency_score?.toFixed(2)}</span></div>
                          </div>

                          <div style={{ display: 'flex', gap: '8px' }}>
                            <button 
                              className="btn-secondary"
                              style={{ padding: '7px 12px', fontSize: '12px' }}
                              onClick={() => handleFeedback(m.job_id, 'saved')}
                              title="Save Opportunity"
                            >
                              <Bookmark size={14} /> Save
                            </button>
                            <button 
                              className="btn-secondary"
                              style={{ padding: '7px 12px', fontSize: '12px', color: '#F87171' }}
                              onClick={() => handleFeedback(m.job_id, 'dismissed')}
                              title="Dismiss from future recommendations"
                            >
                              <X size={14} /> Dismiss
                            </button>
                            <a
                              href={m.apply_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="btn-primary"
                              style={{ padding: '7px 14px', fontSize: '12px', textDecoration: 'none' }}
                            >
                              Apply Directly <ExternalLink size={13} />
                            </a>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Discovery Feed Tab */}
      {activeTab === 'feed' && (
        <div>
          <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <div style={{ position: 'relative', flex: 1 }}>
                <Search size={18} style={{ position: 'absolute', left: '14px', top: '13px', color: 'var(--text-muted)' }} />
                <input
                  className="form-input"
                  style={{ paddingLeft: '42px' }}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && fetchFeedJobs(searchQuery)}
                  placeholder="Semantic Vector Search: e.g. 'high throughput distributed systems python' or role title..."
                />
              </div>
              <button 
                className="btn-primary"
                onClick={() => fetchFeedJobs(searchQuery)}
                disabled={isSearching}
              >
                {isSearching ? 'Searching...' : 'Search Vectors'}
              </button>
            </div>
          </div>

          <div className="matches-feed">
            {feedJobs.map(job => (
              <div key={job.id} className="glass-panel job-card">
                <div className="job-card-header">
                  <div>
                    <div className="job-company">{job.company}</div>
                    <h3 className="job-title">{job.title}</h3>
                  </div>
                  {job.similarity_score !== undefined && (
                    <div className="match-score-badge">
                      <span className="match-score-num">{(job.similarity_score * 100).toFixed(0)}%</span>
                      <span className="match-score-label">Vector Sim</span>
                    </div>
                  )}
                </div>

                <div className="job-meta-row">
                  <span className="meta-item"><Wifi size={14} /> {job.remote_type?.toUpperCase()}</span>
                  <span className="meta-item"><Briefcase size={14} /> {job.seniority?.toUpperCase()}</span>
                  <span className="meta-item"><MapPin size={14} /> {(job.locations || []).join(', ') || 'Remote'}</span>
                </div>

                <p style={{ fontSize: '13px', color: '#94A3B8', marginBottom: '16px', lineHeight: 1.6 }}>
                  {job.description?.slice(0, 240)}...
                </p>

                <div className="job-actions">
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Source: <strong>{job.source_id?.slice(0, 12)}</strong> • Verification: <strong>{job.verification_status}</strong>
                  </span>
                  <a
                    href={job.apply_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-primary"
                    style={{ padding: '7px 14px', fontSize: '12px', textDecoration: 'none' }}
                  >
                    View Official Posting <ExternalLink size={13} />
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Engine Operations Tab */}
      {activeTab === 'engine' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '18px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Cpu size={20} color="#818CF8" /> Pipeline Trigger Controls
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px' }}>
              Execute background tasks directly. In production, Celery Beat runs these on periodic schedules.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <button 
                className="btn-secondary" 
                style={{ justifyContent: 'flex-start' }}
                onClick={() => runOperation('Cross-Source Deduplication', '/api/jobs/deduplicate')}
                disabled={isEngineRunning}
              >
                <Layers size={16} /> Run Cross-Source Deduplication & Clustering
              </button>
              <button 
                className="btn-secondary" 
                style={{ justifyContent: 'flex-start' }}
                onClick={() => runOperation('Link Verification', '/api/jobs/verify')}
                disabled={isEngineRunning}
              >
                <ShieldCheck size={16} /> Run Live Link Verification (404/Closure Detection)
              </button>
              <button 
                className="btn-secondary" 
                style={{ justifyContent: 'flex-start' }}
                onClick={() => runOperation('Batch Vector Embedding', '/api/jobs/embed')}
                disabled={isEngineRunning}
              >
                <Cpu size={16} /> Generate Vector Embeddings (FastEmbed 384-D)
              </button>
            </div>
          </div>

          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '18px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Clock size={20} color="#06B6D4" /> Operations Activity Log
            </h3>
            <div style={{ 
              background: '#040711', 
              borderRadius: '8px', 
              padding: '16px', 
              fontFamily: 'var(--font-mono)', 
              fontSize: '12px',
              minHeight: '220px',
              color: '#34D399',
              overflowY: 'auto'
            }}>
              {engineLogs.length === 0 ? (
                <span style={{ color: '#475569' }}>Awaiting pipeline actions...</span>
              ) : (
                engineLogs.map((log, i) => (
                  <div key={i} style={{ marginBottom: '6px' }}>{log}</div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
