import React, { useState, useEffect, useRef } from 'react';
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
  Flame,
  Upload,
  Plus,
  Trash2,
  Filter,
  Calendar
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

const POPULAR_SKILLS = [
  "Python", "FastAPI", "React", "TypeScript", "Node.js", "PostgreSQL", 
  "Redis", "Docker", "GraphQL", "Kubernetes", "AWS", "Go", 
  "Distributed Systems", "Microservices", "Next.js", "Celery"
];

export default function App() {
  const [activeTab, setActiveTab] = useState('studio'); // 'studio' | 'feed' | 'engine'
  const fileInputRef = useRef(null);
  
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

  // Resume Upload & Skill State
  const [isUploadingResume, setIsUploadingResume] = useState(false);
  const [uploadSuccessMsg, setUploadSuccessMsg] = useState(null);
  const [customSkillInput, setCustomSkillInput] = useState('');
  const [minScore, setMinScore] = useState(0.70); // Enforce 70% match threshold
  const [maxDays, setMaxDays] = useState(3);       // Enforce <= 3 days older
  const [parsedMetadata, setParsedMetadata] = useState(null);

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
            parsed_skills: extractedSkills,
            min_similarity_score: 0.70
          }
        })
      });
      if (res.ok) {
        const data = await res.json();
        setUserId(data.id);
        if (data.profile) {
          setExtractedSkills(data.profile.parsed_skills || extractedSkills);
          setHasEmbedding(data.profile.has_embedding);
        }
        fetchMatches(data.id, 0.70, 3);
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
          parsed_skills: extractedSkills,
          min_similarity_score: minScore
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setExtractedSkills(updated.parsed_skills || []);
        setHasEmbedding(true);
        fetchMatches(userId, minScore, maxDays);
      }
    } catch (err) {
      console.error("Save profile error:", err);
    } finally {
      setIsSavingProfile(false);
    }
  };

  // 3. Resume File Upload Handler
  const handleFileUpload = async (file) => {
    if (!file || !userId) return;
    setIsUploadingResume(true);
    setUploadSuccessMsg(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`/api/users/${userId}/resume`, {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        if (data.raw_resume_text) setResumeText(data.raw_resume_text);
        if (data.parsed_skills && data.parsed_skills.length > 0) {
          setExtractedSkills(data.parsed_skills);
        }
        if (data.target_roles && data.target_roles.length > 0) {
          setSelectedRoles(data.target_roles);
        }
        if (data.seniority && !selectedSeniorities.includes(data.seniority)) {
          setSelectedSeniorities([data.seniority]);
        }
        setParsedMetadata(data);
        setUploadSuccessMsg(`✓ Successfully parsed "${file.name}"! Extracted ${data.parsed_skills?.length || 0} skills & updated profile.`);
        fetchMatches(userId, minScore, maxDays);
      } else {
        const err = await res.json();
        alert(`Resume upload failed: ${err.detail || 'Could not parse document'}`);
      }
    } catch (err) {
      console.error("Upload error:", err);
    } finally {
      setIsUploadingResume(false);
    }
  };

  // Skill Management Helpers
  const toggleSkill = (skill) => {
    setExtractedSkills(prev => 
      prev.includes(skill) ? prev.filter(s => s !== skill) : [...prev, skill]
    );
  };

  const removeSkill = (skillToRemove) => {
    setExtractedSkills(prev => prev.filter(s => s !== skillToRemove));
  };

  const addCustomSkill = () => {
    const clean = customSkillInput.trim();
    if (clean && !extractedSkills.includes(clean)) {
      setExtractedSkills(prev => [...prev, clean]);
      setCustomSkillInput('');
    }
  };

  // 4. Fetch Matches (strictly >= 70% score, <= 3 days old)
  const fetchMatches = async (targetUserId = userId, threshold = minScore, days = maxDays) => {
    if (!targetUserId) return;
    setIsLoadingMatches(true);
    try {
      const res = await fetch(`/api/users/${targetUserId}/matches?limit=10&min_score=${threshold}&max_days=${days}`);
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
                <CheckCircle size={24} color="#059669" />
                <div>
                  <h4 style={{ color: '#065F46', fontSize: '15px', fontWeight: 700 }}>
                    9 AM Digest Dispatched via {alertSuccess.channel.toUpperCase()}!
                  </h4>
                  <p style={{ fontSize: '13px', color: '#047857' }}>
                    Delivered {alertSuccess.matches_count} high-confidence opportunities to recipient <code>{alertSuccess.recipient}</code>. Outbox ID: <code>{alertSuccess.outbox_id?.slice(0, 8)}...</code>
                  </p>
                </div>
              </div>
              <button 
                onClick={() => setAlertSuccess(null)}
                style={{ background: 'transparent', border: 'none', color: '#065F46', cursor: 'pointer' }}
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
                <p>Upload your resume to automatically extract details, or customize your skills & target roles.</p>
              </div>

              {/* 1. Resume Document Upload Dropzone */}
              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label className="form-label" style={{ marginBottom: 0 }}>
                    Upload Resume Document
                  </label>
                  <span style={{ fontSize: '11px', color: '#4F46E5', fontWeight: 600 }}>
                    PDF, DOCX, TXT
                  </span>
                </div>
                
                <div 
                  className={`resume-upload-zone ${isUploadingResume ? 'is-uploading' : ''}`}
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                      handleFileUpload(e.dataTransfer.files[0]);
                    }
                  }}
                  title="Click or drop resume file here"
                >
                  <input 
                    type="file" 
                    ref={fileInputRef}
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        handleFileUpload(e.target.files[0]);
                      }
                    }}
                    accept=".pdf,.docx,.txt"
                    style={{ display: 'none' }}
                  />
                  <div className="resume-upload-icon">
                    {isUploadingResume ? (
                      <RefreshCw size={20} className="animate-spin" />
                    ) : (
                      <Upload size={20} />
                    )}
                  </div>
                  <div className="resume-upload-title">
                    {isUploadingResume ? 'Parsing Resume & Extracting Competencies...' : 'Click or Drop Resume File Here'}
                  </div>
                  <div className="resume-upload-sub">
                    Automatically extracts tech skills, experience & filters 70%+ matches
                  </div>
                </div>

                {uploadSuccessMsg && (
                  <div style={{ 
                    fontSize: '12px', 
                    color: '#065F46', 
                    background: '#ECFDF5', 
                    padding: '8px 12px', 
                    borderRadius: '6px', 
                    border: '1px solid #A7F3D0', 
                    marginBottom: '10px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}>
                    <CheckCircle size={14} color="#059669" />
                    <span>{uploadSuccessMsg}</span>
                  </div>
                )}
              </div>

              {/* 2. Interactive Technical Skills Selection */}
              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label className="form-label" style={{ marginBottom: 0 }}>
                    Selected Technical Skills ({extractedSkills.length})
                  </label>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Core matching factor
                  </span>
                </div>

                {/* Active Skills Tag Box */}
                <div className="selected-skills-box">
                  {extractedSkills.length === 0 ? (
                    <span style={{ fontSize: '12px', color: '#94A3B8', fontStyle: 'italic' }}>
                      No skills selected yet. Select popular skills below or upload your resume.
                    </span>
                  ) : (
                    extractedSkills.map(skill => (
                      <span key={skill} className="skill-tag-active">
                        {skill}
                        <button 
                          type="button" 
                          className="skill-tag-remove" 
                          onClick={() => removeSkill(skill)}
                          title={`Remove ${skill}`}
                        >
                          <X size={12} />
                        </button>
                      </span>
                    ))
                  )}
                </div>

                {/* Add Custom Skill Input */}
                <div className="skill-add-input-row">
                  <input 
                    className="form-input"
                    style={{ padding: '6px 12px', fontSize: '13px' }}
                    placeholder="Add skill (e.g. Next.js, Kafka, Temporal)..."
                    value={customSkillInput}
                    onChange={(e) => setCustomSkillInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addCustomSkill();
                      }
                    }}
                  />
                  <button 
                    type="button" 
                    className="btn-secondary"
                    style={{ padding: '6px 14px', fontSize: '13px', whiteSpace: 'nowrap' }}
                    onClick={addCustomSkill}
                  >
                    <Plus size={14} /> Add
                  </button>
                </div>

                {/* Quick Toggle Popular Skills */}
                <div style={{ marginTop: '8px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Quick Select Skills:
                  </div>
                  <div className="suggested-skills-grid">
                    {POPULAR_SKILLS.map(skill => {
                      const isSelected = extractedSkills.includes(skill);
                      return (
                        <button
                          key={skill}
                          type="button"
                          className={`suggested-skill-btn ${isSelected ? 'active' : ''}`}
                          onClick={() => toggleSkill(skill)}
                        >
                          {isSelected ? '✓ ' : '+ '} {skill}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* 3. Resume & Experience Text */}
              <div className="form-group">
                <label className="form-label">Resume & Experience Text</label>
                <textarea
                  className="form-textarea"
                  rows={4}
                  value={resumeText}
                  onChange={(e) => setResumeText(e.target.value)}
                  placeholder="Paste work experience, technologies, accomplishments or resume summary..."
                />
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
                  <>Embedding Intent & Re-ranking...</>
                ) : (
                  <>
                    <Cpu size={16} /> Save Profile & Re-Rank Matches
                  </>
                )}
              </button>
            </div>

            {/* Right Column: Ranked Matches & 9 AM Alert Center */}
            <div>
              {/* Action Banner */}
              <div className="glass-panel" style={{ padding: '20px 24px', marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <h3 style={{ fontSize: '18px', color: 'var(--text-primary)', margin: 0 }}>Personalized Match Stream</h3>
                    <span className="match-threshold-badge">
                      🎯 ≥ 70% Match
                    </span>
                    <span className="recency-badge">
                      ⚡ Max 3 Days Old
                    </span>
                  </div>
                  <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Ranked by Experience Fit (35%) + Skills Match (35%) + Title Alignment (20%) + Recency (10%)
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <button 
                    className="btn-secondary"
                    onClick={() => fetchMatches(userId, minScore, maxDays)}
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
                  <p>Running reverse matching engine for ≥ 70% matches within the past 3 days...</p>
                </div>
              ) : matches.length === 0 ? (
                <div className="glass-panel" style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <Briefcase size={36} style={{ margin: '0 auto 16px', opacity: 0.4 }} />
                  <h4 style={{ color: 'var(--text-primary)', marginBottom: '8px' }}>No matches found with ≥ 70% match score</h4>
                  <p style={{ maxWidth: '420px', margin: '0 auto' }}>
                    All matched jobs must score at least 70% against your selected skills & experience and be at most 3 days old. Try selecting relevant skills like <strong>React</strong>, <strong>TypeScript</strong>, <strong>Node.js</strong>, or <strong>GraphQL</strong>!
                  </p>
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
                              <ShieldCheck size={14} color="#0284C7" /> {m.company}
                              <span style={{ 
                                marginLeft: '8px', 
                                fontSize: '11px', 
                                fontWeight: 600, 
                                background: '#EFF6FF', 
                                color: '#2563EB', 
                                padding: '2px 8px', 
                                borderRadius: '4px' 
                              }}>
                                ⚡ Latest (≤ 3d)
                              </span>
                            </div>
                            <h3 className="job-title">{m.title}</h3>
                          </div>
                          <div className="match-score-badge" style={{ background: matchPercent >= 70 ? 'linear-gradient(135deg, #ECFDF5, #D1FAE5)' : undefined, borderColor: matchPercent >= 70 ? '#A7F3D0' : undefined }}>
                            <span className="match-score-num" style={{ color: matchPercent >= 70 ? '#059669' : undefined }}>
                              {matchPercent}%
                            </span>
                            <span className="match-score-label">
                              {matchPercent >= 70 ? 'Strong Match' : 'Match Score'}
                            </span>
                          </div>
                        </div>

                        {/* Metadata row */}
                        <div className="job-meta-row">
                          <span className="meta-item">
                            <Wifi size={14} color="#6366F1" /> {m.remote_type?.toUpperCase()}
                          </span>
                          <span className="meta-item">
                            <Briefcase size={14} color="#6366F1" /> {m.seniority?.toUpperCase()}
                          </span>
                          {m.locations && m.locations.length > 0 && (
                            <span className="meta-item">
                              <MapPin size={14} color="#6366F1" /> {m.locations.join(', ')}
                            </span>
                          )}
                        </div>

                        {/* Match Reasons */}
                        {m.reasons && (
                          <div className="job-explanation">
                            💡 <strong>Match Rationale:</strong> {Array.isArray(m.reasons) ? m.reasons.join(' • ') : m.reasons}
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
                            <div>Exp Vec: <span>{m.scores?.vector_similarity?.toFixed(2)}</span></div>
                            {m.scores?.skill_score !== undefined && (
                              <div>Skills: <span>{m.scores?.skill_score?.toFixed(2)}</span></div>
                            )}
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
                              style={{ padding: '7px 12px', fontSize: '12px', color: '#DC2626' }}
                              onClick={() => handleFeedback(m.job_id, 'dismissed')}
                              title="Dismiss from future recommendations"
                            >
                              <X size={14} /> Dismiss
                            </button>
                            <a
                              href={m.apply_url || '#'}
                              target="_blank"
                              rel="noreferrer"
                              className="btn-primary"
                              style={{ padding: '7px 16px', fontSize: '12px', textDecoration: 'none' }}
                              onClick={() => handleFeedback(m.job_id, 'applied')}
                            >
                              Apply Directly <ExternalLink size={13} style={{ marginLeft: '4px' }} />
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
