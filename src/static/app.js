import React, { useState, useEffect, useRef, createContext, useContext } from 'react';
import { createRoot } from 'react-dom/client';
import htm from 'htm';
import Chart from 'chart.js';

// Initialize htm with React's element factory
const html = htm.bind(React.createElement);

// --- 1. AUTHENTICATION CONTEXT ---
const AuthContext = createContext(null);

function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    const fetchMe = async () => {
        try {
            const res = await fetch('/api/auth/me');
            if (res.ok) {
                const data = await res.json();
                setUser(data);
            } else {
                setUser(null);
            }
        } catch (e) {
            setUser(null);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchMe();
    }, []);

    const login = async (email, password) => {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Login failed.');
        await fetchMe();
        return data;
    };

    const signup = async (email, password) => {
        const res = await fetch('/api/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Signup failed.');
        return data;
    };

    const logout = async () => {
        await fetch('/api/auth/logout', { method: 'POST' });
        setUser(null);
    };

    return html`
        <${AuthContext.Provider} value=${{ user, loading, login, signup, logout, refreshUser: fetchMe }}>
            ${children}
        </${AuthContext.Provider}>
    `;
}

const useAuth = () => useContext(AuthContext);

// --- 2. GLASSMORPHIC AUTH SCREEN ---
function AuthScreen() {
    const { login, signup } = useAuth();
    const [isLogin, setIsLogin] = useState(true);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        if (!email.includes('@')) {
            setError('Please enter a valid email address.');
            return;
        }
        if (password.length < 6) {
            setError('Password must be at least 6 characters.');
            return;
        }

        setLoading(true);
        try {
            if (isLogin) {
                await login(email, password);
            } else {
                const data = await signup(email, password);
                alert(data.message);
                setIsLogin(true);
                setPassword('');
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return html`
        <div className="auth-container">
            <div className="auth-card">
                <span className="auth-logo">🚀</span>
                <h2>${isLogin ? 'Welcome Back' : 'Create Account'}</h2>
                <p className="auth-subtitle">
                    ${isLogin ? 'Sign in to access your AI portfolio insights' : 'Get started with autonomous daily advisor alerts'}
                </p>

                <form className="auth-form" onSubmit=${handleSubmit}>
                    <div className="auth-input-group">
                        <label>Email Address</label>
                        <input 
                            type="email" 
                            placeholder="you@example.com" 
                            value=${email} 
                            onChange=${(e) => setEmail(e.target.value)} 
                            required 
                            disabled=${loading}
                        />
                    </div>
                    
                    <div className="auth-input-group">
                        <label>Password</label>
                        <input 
                            type="password" 
                            placeholder="••••••••" 
                            value=${password} 
                            onChange=${(e) => setPassword(e.target.value)} 
                            required 
                            disabled=${loading}
                        />
                    </div>

                    ${error && html`<div className="auth-error">${error}</div>`}

                    <button type="submit" className="btn btn-primary" disabled=${loading}>
                        <span>${loading ? 'Processing...' : isLogin ? 'Sign In' : 'Sign Up'}</span>
                        ${loading && html`<div className="spinner"></div>`}
                    </button>
                </form>

                <div className="auth-switch">
                    ${isLogin ? "Don't have an account?" : 'Already have an account?'}
                    <button className="auth-switch-btn" onClick=${() => { setIsLogin(!isLogin); setError(''); }} disabled=${loading}>
                        ${isLogin ? 'Sign Up' : 'Sign In'}
                    </button>
                </div>
            </div>
        </div>
    `;
}

// --- 3. PREMIUM PORTFOLIO DASHBOARD ---
function Dashboard() {
    const { user, logout, refreshUser } = useAuth();
    
    // Model Selection & API configuration
    const [model, setModel] = useState('gpt-4o-mini');
    const [customApiKey, setCustomApiKey] = useState(() => {
        return localStorage.getItem('diversify_ai_custom_api_key') || '';
    });
    
    useEffect(() => {
        if (customApiKey) {
            localStorage.setItem('diversify_ai_custom_api_key', customApiKey);
        } else {
            localStorage.removeItem('diversify_ai_custom_api_key');
        }
    }, [customApiKey]);
    
    // File inputs & stateful analytical results
    const [selectedFile, setSelectedFile] = useState(null);
    const [dragActive, setDragActive] = useState(false);
    const [analyzing, setAnalyzing] = useState(false);
    const [result, setResult] = useState(null);
    
    // What-if state
    const [whatIfTicker, setWhatIfTicker] = useState('');
    const [whatIfAmount, setWhatIfAmount] = useState('');
    const [whatIfLoading, setWhatIfLoading] = useState(false);

    // Chat widget state
    const [chatMessage, setChatMessage] = useState('');
    const [chatHistory, setChatHistory] = useState([
        { sender: 'ai', text: "Hi! I'm your AI advisor. Try asking me: \"Which stock is riskiest?\" or \"How can I reduce volatility?\"" }
    ]);
    const [chatLoading, setChatLoading] = useState(false);

    // Daily Alerts state
    const [subEmail, setSubEmail] = useState(user.email);
    const [subStatus, setSubStatus] = useState('');
    const [subStatusColor, setSubStatusColor] = useState('#94a3b8');
    const [subActive, setSubActive] = useState(user.is_subscribed);
    const [alertsLoading, setAlertsLoading] = useState(false);

    // Active chart tab panel
    const [activeTab, setActiveTab] = useState('asset');
    const chartRefs = {
        asset: useRef(null),
        sector: useRef(null),
        mcap: useRef(null),
        risk: useRef(null)
    };
    const chartInstances = useRef({});

    // Load saved portfolio holdings on mount if user already has one!
    useEffect(() => {
        if (user.holdings && user.holdings.length > 0) {
            triggerAnalyzeHoldings(user.holdings);
        }
    }, [user.holdings]);

    // Handle Upstox OAuth Message callback
    useEffect(() => {
        const handleOauthMessage = (event) => {
            const data = event.data;
            if (data && data.success && data.is_raw_holdings) {
                triggerAnalyzeHoldings(data.holdings);
            } else if (data && !data.success && data.error) {
                alert(`Broker connection failed: ${data.error}`);
            }
        };

        window.addEventListener('message', handleOauthMessage);
        return () => window.removeEventListener('message', handleOauthMessage);
    }, []);

    // Render interactive charts when result or tab panel changes
    useEffect(() => {
        if (!result) return;
        renderTabCharts();
    }, [result, activeTab]);

    const getHeaders = () => {
        const headers = {};
        if (model) headers['X-Model'] = model;
        if (customApiKey) headers['X-API-Key'] = customApiKey;
        return headers;
    };

    const triggerAnalyzeHoldings = async (holdings) => {
        setAnalyzing(true);
        try {
            const res = await fetch('/api/analyze_holdings', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    ...getHeaders()
                },
                body: JSON.stringify({ holdings })
            });
            const data = await res.json();
            if (data.success) {
                setResult(data);
            } else {
                alert(`Analysis failed: ${data.error}`);
            }
        } catch (e) {
            alert('Failed to connect to analytics server.');
        } finally {
            setAnalyzing(false);
        }
    };

    // Chart.js renderer
    const renderTabCharts = () => {
        const palettes = {
            base: ["#6366f1", "#a855f7", "#10b981", "#f59e0b", "#ec4899", "#06b6d4", "#3b82f6", "#f43f5e"],
            mcap: ["#3b82f6", "#8b5cf6", "#f43f5e"],
            risk: ["#10b981", "#f59e0b", "#f43f5e"]
        };

        const createChart = (id, breakdown, labelCol, palette) => {
            if (chartInstances.current[id]) {
                chartInstances.current[id].destroy();
            }
            const canvas = document.getElementById(id);
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const labels = breakdown.map(item => item[labelCol]);
            const values = breakdown.map(item => item["Percentage"]);

            chartInstances.current[id] = new Chart(ctx, {
                type: "doughnut",
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: palette.slice(0, labels.length),
                        borderWidth: 1, borderColor: "rgba(255, 255, 255, 0.08)"
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "right", labels: { color: "#9ca3af", font: { family: "Outfit", size: 11 } } }
                    },
                    cutout: "65%"
                }
            });
        };

        if (activeTab === 'asset' && result.asset_type_breakdown) {
            createChart('assetChart', result.asset_type_breakdown, 'Asset Type', palettes.base);
        } else if (activeTab === 'sector' && result.sector_breakdown) {
            createChart('sectorChart', result.sector_breakdown, 'Sector', palettes.base.slice().reverse());
        } else if (activeTab === 'mcap' && result.market_cap_breakdown) {
            createChart('mcapChart', result.market_cap_breakdown, 'MarketCapCategory', palettes.mcap);
        } else if (activeTab === 'risk' && result.risk_breakdown) {
            createChart('riskChart', result.risk_breakdown, 'RiskCategory', palettes.risk);
        }
    };

    // File Dropzone handlers
    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setDragActive(true);
        } else if (e.type === 'dragleave') {
            setDragActive(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            const file = e.dataTransfer.files[0];
            if (file.name.endsWith('.csv')) {
                setSelectedFile(file);
            } else {
                alert('Only CSV files are supported!');
            }
        }
    };

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            setSelectedFile(e.target.files[0]);
        }
    };

    const handleAnalyzeClick = async () => {
        if (!selectedFile) return;
        setAnalyzing(true);
        
        const formData = new FormData();
        formData.append('file', selectedFile);

        try {
            const res = await fetch('/api/analyze', {
                method: 'POST',
                headers: getHeaders(),
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                setResult(data);
                refreshUser(); // Updates holdings inside user profile
            } else {
                alert(`Analysis failed: ${data.error}`);
            }
        } catch (e) {
            alert('Failed to connect to backend.');
        } finally {
            setAnalyzing(false);
        }
    };

    // Upstox popup trigger
    const handleUpstoxConnect = async () => {
        try {
            const res = await fetch('/api/auth/upstox/login');
            const data = await res.json();
            if (data.success && data.login_url) {
                const width = 600, height = 700;
                const left = (window.innerWidth - width) / 2;
                const top = (window.innerHeight - height) / 2;
                window.open(
                    data.login_url, 
                    'Upstox Integration', 
                    `width=${width},height=${height},left=${left},top=${top}`
                );
            } else {
                alert(`OAuth Initiation failed: ${data.error}`);
            }
        } catch (e) {
            alert('Failed to connect to auth server.');
        }
    };

    // What-If Simulation Click
    const handleWhatIfSimulate = async () => {
        if (!whatIfTicker || !whatIfAmount) return;
        setWhatIfLoading(true);
        try {
            const currentHoldings = result ? result.assets : [];
            const simulatedHoldings = [
                ...currentHoldings.map(h => ({
                    'Asset Name': h['Asset Name'],
                    'Ticker': h['Ticker'],
                    'Asset Type': h['Asset Type'],
                    'Sector': h['Sector'],
                    'Current Value': h['Current Value'],
                    'Currency': h['Currency'] || 'USD'
                })),
                {
                    'Asset Name': whatIfTicker,
                    'Ticker': whatIfTicker,
                    'Asset Type': 'Equity', // Standard assumption
                    'Sector': 'Technology',  // Standard assumption
                    'Current Value': parseFloat(whatIfAmount),
                    'Currency': 'USD'
                }
            ];

            const res = await fetch('/api/analyze_holdings', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    ...getHeaders()
                },
                body: JSON.stringify({ holdings: simulatedHoldings })
            });
            const data = await res.json();
            if (data.success) {
                setResult(data);
                alert(`Simulation completed! Simulated asset ${whatIfTicker} worth $${whatIfAmount} loaded.`);
            } else {
                alert(`Simulation failed: ${data.error}`);
            }
        } catch (e) {
            alert('Simulation connection error.');
        } finally {
            setWhatIfLoading(false);
            setWhatIfTicker('');
            setWhatIfAmount('');
        }
    };

    // Chat handler
    const handleSendChat = async () => {
        if (!chatMessage.trim()) return;
        const msgText = chatMessage;
        setChatMessage('');
        setChatHistory(prev => [...prev, { sender: 'user', text: msgText }]);
        setChatLoading(true);

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...getHeaders()
                },
                body: JSON.stringify({
                    message: msgText,
                    holdings: result ? result.assets : []
                })
            });
            const data = await res.json();
            if (data.success) {
                setChatHistory(prev => [...prev, { sender: 'ai', text: data.reply }]);
            } else {
                setChatHistory(prev => [...prev, { sender: 'ai', text: `Error: ${data.error}` }]);
            }
        } catch (e) {
            setChatHistory(prev => [...prev, { sender: 'ai', text: 'Chat failed to connect to backend server.' }]);
        } finally {
            setChatLoading(false);
        }
    };

    // Daily Alerts Actions
    const handleSubscribe = async () => {
        setAlertsLoading(true);
        setSubStatus('Registering subscription...');
        setSubStatusColor('#94a3b8');
        try {
            const res = await fetch('/api/subscriptions/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    holdings: result ? result.assets : [],
                    model: model,
                    api_key: customApiKey
                })
            });
            const data = await res.json();
            if (data.success) {
                setSubStatus(data.message);
                setSubStatusColor('#10b981');
                setSubActive(true);
            } else {
                setSubStatus(`Error: ${data.error}`);
                setSubStatusColor('#ef4444');
            }
        } catch (e) {
            setSubStatus('Connection failed.');
            setSubStatusColor('#ef4444');
        } finally {
            setAlertsLoading(false);
        }
    };

    const handleUnsubscribe = async () => {
        setAlertsLoading(true);
        setSubStatus('Disabling alerts...');
        setSubStatusColor('#94a3b8');
        try {
            const res = await fetch('/api/subscriptions/unsubscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (data.success) {
                setSubStatus(data.message);
                setSubStatusColor('#f43f5e');
                setSubActive(false);
            } else {
                setSubStatus(`Error: ${data.error}`);
                setSubStatusColor('#ef4444');
            }
        } catch (e) {
            setSubStatus('Connection failed.');
            setSubStatusColor('#ef4444');
        } finally {
            setAlertsLoading(false);
        }
    };

    const handleTriggerTest = async () => {
        setAlertsLoading(true);
        setSubStatus('Aggregating headlines and invoking Gemini...');
        setSubStatusColor('#94a3b8');
        try {
            const res = await fetch('/api/subscriptions/trigger_test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...getHeaders()
                },
                body: JSON.stringify({ 
                    holdings: result ? result.assets : [],
                    model: model,
                    api_key: customApiKey
                })
            });
            const data = await res.json();
            if (data.success) {
                setSubStatus(data.message);
                setSubStatusColor('#10b981');
                setSubActive(true);
                if (data.report) {
                    setResult(prev => ({ ...prev, report: data.report }));
                }
            } else {
                setSubStatus(`Error: ${data.error}`);
                setSubStatusColor('#ef4444');
            }
        } catch (e) {
            setSubStatus('Connection failed.');
            setSubStatusColor('#ef4444');
        } finally {
            setAlertsLoading(false);
        }
    };

    const formatCurrency = (value) => {
        return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 }).format(value);
    };

    return html`
        <div className="app-container">
            <!-- Header section -->
            <header className="app-header">
                <div className="brand">
                    <span className="logo-icon">🚀</span>
                    <div className="brand-text">
                        <h1>DiversifyAI</h1>
                        <p>GenAI Portfolio Advisor</p>
                    </div>
                </div>
                
                <div className="api-key-config">
                    <div className="input-row">
                        <div className="input-group provider-group">
                            <label>Model Name</label>
                            <select value=${model} onChange=${(e) => setModel(e.target.value)}>
                                <option value="gpt-4o-mini">GPT-4o Mini</option>
                                <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                            </select>
                        </div>
                        <div className="input-group key-group">
                            <label>API Key (Optional)</label>
                            <input 
                                type="password" 
                                placeholder="Paste API Key here..." 
                                value=${customApiKey}
                                onChange=${(e) => setCustomApiKey(e.target.value)}
                            />
                        </div>
                        
                        <!-- Premium user sign-out -->
                        <div style=${{ display: 'flex', flexDirection: 'column', gap: '0.25rem', marginLeft: '1rem', borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '1rem' }}>
                            <span style=${{ fontSize: '0.75rem', color: '#9ca3af', fontWeight: '500' }}>${user.email}</span>
                            <button className="btn btn-secondary btn-sm" onClick=${logout} style=${{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}>Logout</button>
                        </div>
                    </div>
                </div>
            </header>

            <main className="app-main">
                <!-- Left panel -->
                <section className="workspace-section control-panel">
                    
                    <!-- Upload holdings card -->
                    <div className="glass-card upload-card">
                        <h2>Analyze Portfolio</h2>
                        <p className="card-subtitle">Upload your holdings in CSV format to calculate distributions and invoke the AI Advisor.</p>
                        
                        <div 
                            className=${`dropzone ${dragActive ? 'active' : ''}`}
                            onDragEnter=${handleDrag}
                            onDragOver=${handleDrag}
                            onDragLeave=${handleDrag}
                            onDrop=${handleDrop}
                            onClick=${() => document.getElementById('react-file-input').click()}
                        >
                            <input 
                                type="file" 
                                id="react-file-input" 
                                accept=".csv" 
                                className="hidden-file-input" 
                                onChange=${handleFileChange}
                            />
                            
                            ${!selectedFile ? html`
                                <div className="dropzone-content">
                                    <span className="upload-icon">📥</span>
                                    <p className="dropzone-text"><strong className="highlight">Choose a file</strong> or drag it here</p>
                                    <p className="dropzone-subtext">CSV files only (Holdings table)</p>
                                </div>
                            ` : html`
                                <div className="file-info">
                                    <span className="file-icon">📄</span>
                                    <span className="file-name">${selectedFile.name}</span>
                                    <button className="remove-file-btn" onClick=${(e) => { e.stopPropagation(); setSelectedFile(null); }}>×</button>
                                </div>
                            `}
                        </div>

                        <button className="btn btn-primary" onClick=${handleAnalyzeClick} disabled=${!selectedFile || analyzing}>
                            <span>${analyzing ? 'Analyzing holdings...' : 'Analyze Portfolio'}</span>
                            ${analyzing && html`<div className="spinner"></div>`}
                        </button>
                        
                        <div className="sample-download-note">
                            <p>Test using our <a href="data/sample_portfolio.csv" download className="sample-link">sample_portfolio.csv</a></p>
                        </div>

                        <div className="broker-integrations" style=${{ marginTop: '2rem' }}>
                            <h3 style=${{ fontSize: '1rem', marginBottom: '1rem', color: '#e5e7eb' }}>Or Import from Broker</h3>
                            <div className="broker-buttons">
                                <button className="btn btn-secondary" onClick=${handleUpstoxConnect} style=${{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(87,50,214,0.1)', borderColor: 'rgba(87,50,214,0.3)', color: '#5732d6', width: '100%' }}>
                                    <span>Connect Upstox</span>
                                    <img src="https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=https://upstox.com&size=64" alt="Upstox" style=${{ height: '20px', width: '20px', borderRadius: '4px' }} />
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Daily Advisor Settings card (Visible when portfolio is loaded) -->
                    ${result && html`
                        <div className="glass-card" style=${{ marginTop: '0.25rem' }}>
                            <h2 style=${{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.25rem' }}>
                                <span>⏰</span> Daily Advisor Agent
                            </h2>
                            <p className="card-subtitle" style=${{ fontSize: '0.85rem', color: '#9ca3af', marginTop: '0.25rem', lineHeight: '1.4' }}>
                                Aggregates stock news every morning, analyzes holdings risk via Gemini, and sends a styled HTML advisor report directly to your inbox.
                            </p>
                            
                            <div style=${{ display: 'flex', flexDirection: 'column', gap: '0.85rem', marginTop: '1rem' }}>
                                <div style=${{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                    <label style=${{ fontSize: '0.8rem', fontWeight: 500, color: '#9ca3af' }}>Subscriber Email</label>
                                    <input 
                                        type="email" 
                                        value=${subEmail}
                                        onChange=${(e) => setSubEmail(e.target.value)}
                                        disabled
                                        style=${{ width: '100%', padding: '0.75rem 1rem', borderRadius: '8px', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', color: 'white', boxSizing: 'border-box', fontFamily: 'inherit' }} 
                                    />
                                </div>
                                <div style=${{ display: 'flex', gap: '0.75rem' }}>
                                    <button className="btn btn-primary" onClick=${handleSubscribe} disabled=${alertsLoading} style=${{ flex: 1.2, padding: '0.75rem', fontSize: '0.9rem' }}>
                                        ${alertsLoading ? 'Saving...' : 'Enable Alerts'}
                                    </button>
                                    <button className="btn btn-secondary" onClick=${handleTriggerTest} disabled=${alertsLoading} style=${{ flex: 1, padding: '0.75rem', fontSize: '0.9rem', whiteSpace: 'nowrap', borderColor: 'rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.05)', color: '#cbd5e0' }}>
                                        Test Mail
                                    </button>
                                </div>
                                
                                ${subActive && html`
                                    <button className="btn" onClick=${handleUnsubscribe} disabled=${alertsLoading} style=${{ padding: '0.75rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#ef4444', fontSize: '0.9rem', borderRadius: '8px', cursor: 'pointer', transition: 'background 0.2s' }}>
                                        Disable Alerts
                                    </button>
                                `}
                                
                                ${subStatus && html`<div style=${{ fontSize: '0.8rem', textAlign: 'center', color: subStatusColor, fontWeight: '500' }}>${subStatus}</div>`}
                            </div>
                        </div>
                    `}

                    <!-- Interactive Metrics summary -->
                    ${result && html`
                        <div className="glass-card" style=${{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', padding: '1.5rem' }}>
                            <div className="metric-item">
                                <span className="metric-label">Total Assets</span>
                                <h3 style=${{ fontSize: '1.5rem', background: 'none', WebkitTextFillColor: 'initial', color: 'white' }}>${formatCurrency(result.total_value)}</h3>
                                <span className="badge">${result.assets ? result.assets.length : 0} holdings</span>
                            </div>
                            <div className="metric-item">
                                <span className="metric-label">Health Score</span>
                                <h3 style=${{ fontSize: '1.5rem', background: 'none', WebkitTextFillColor: 'initial', color: '#10b981' }}>
                                    ${result.report && result.report.health_score ? `${result.report.health_score}/100` : '--/100'}
                                </h3>
                                <span className="badge" style=${{ background: 'rgba(16,185,129,0.1)', color: '#10b981' }}>
                                    vs NIFTY 50: ${result.benchmark && result.benchmark.nifty_comparison ? result.benchmark.nifty_comparison : 'Good'}
                                </span>
                            </div>
                            <div className="metric-item">
                                <span className="metric-label">Risk Score</span>
                                <h3 style=${{ fontSize: '1.5rem', background: 'none', WebkitTextFillColor: 'initial', color: '#f43f5e' }}>
                                    ${result.report && result.report.risk_score ? `${result.report.risk_score}/10` : '--/10'}
                                </h3>
                                <span className="badge" style=${{ background: 'rgba(244,63,94,0.1)', color: '#f43f5e' }}>Volatility Based</span>
                            </div>
                        </div>
                    `}

                    <!-- Stateful charts visualization -->
                    ${result && html`
                        <div className="glass-card charts-card">
                            <div className="tabs-header">
                                <button className=${`tab-btn ${activeTab === 'asset' ? 'active' : ''}`} onClick=${() => setActiveTab('asset')}>Asset Type</button>
                                <button className=${`tab-btn ${activeTab === 'sector' ? 'active' : ''}`} onClick=${() => setActiveTab('sector')}>Sector</button>
                                <button className=${`tab-btn ${activeTab === 'mcap' ? 'active' : ''}`} onClick=${() => setActiveTab('mcap')}>Market Cap</button>
                                <button className=${`tab-btn ${activeTab === 'risk' ? 'active' : ''}`} onClick=${() => setActiveTab('risk')}>Risk Dist.</button>
                            </div>
                            <div className="tab-content">
                                ${activeTab === 'asset' && html`<div className="chart-container"><canvas id="assetChart"></canvas></div>`}
                                ${activeTab === 'sector' && html`<div className="chart-container"><canvas id="sectorChart"></canvas></div>`}
                                ${activeTab === 'mcap' && html`<div className="chart-container"><canvas id="mcapChart"></canvas></div>`}
                                ${activeTab === 'risk' && html`<div className="chart-container"><canvas id="riskChart"></canvas></div>`}
                            </div>
                        </div>
                    `}

                </section>

                <!-- Right panel: AI analysis display grids -->
                <section className="workspace-section display-panel">
                    
                    ${!result ? html`
                        <!-- Welcome splash screen -->
                        <div className="glass-card welcome-card">
                            <div className="welcome-graphics">🤖🔮📊</div>
                            <h2>Welcome to DiversifyAI, ${user.email.split('@')[0]}!</h2>
                            <p>Load your investment portfolio to calculate instant allocations and generate a comprehensive diversification strategy powered by GenAI.</p>
                            
                            <div className="features-list">
                                <div className="feature-item">
                                    <span className="f-icon">📊</span>
                                    <div>
                                        <strong>Diversification Analysis</strong>
                                        <p>Inspect multi-dimensional allocation models by asset type, volatility, market capitalization, and sector overlays instantly.</p>
                                    </div>
                                </div>
                                <div className="feature-item">
                                    <span className="f-icon">🤖</span>
                                    <div>
                                        <strong>GenAI Strategic Advisor</strong>
                                        <p>Receive tailor-made diversification strategies detailing immediate threats, positive allocations, and model-specific optimization advisories.</p>
                                    </div>
                                </div>
                                <div className="feature-item">
                                    <span className="f-icon">⏰</span>
                                    <div>
                                        <strong>Proactive Daily Monitor</strong>
                                        <p>Subscribe to our agentic alert system to monitor real-time stock news impact vectors in your inbox automatically every morning.</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    ` : html`
                        <!-- Executive Summary & Threat Highlights -->
                        ${result.report && html`
                            <div className="glass-card" style=${{ borderLeft: '4px solid #3b82f6' }}>
                                <h3 style=${{ marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <span>✨</span> Executive Summary
                                </h3>
                                <p style=${{ lineHeight: 1.6, color: '#e5e7eb' }}>
                                    ${result.report.executive_summary}
                                </p>
                            </div>
                        `}

                        ${result.report && html`
                            <div className="glass-card" style=${{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                                <div>
                                    <h3 style=${{ color: '#f43f5e', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <span>⚠</span> Top Risks
                                    </h3>
                                    <ul style=${{ paddingLeft: '1.2rem', color: '#fecdd3', lineHeight: 1.5, fontSize: '0.95rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                        ${result.report.top_risks && result.report.top_risks.map((risk, i) => html`<li key=${i}>${risk}</li>`)}
                                    </ul>
                                </div>
                                <div>
                                    <h3 style=${{ color: '#10b981', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <span>✔</span> Positive Aspects
                                    </h3>
                                    <ul style=${{ paddingLeft: '1.2rem', color: '#a7f3d0', lineHeight: 1.5, fontSize: '0.95rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                        ${result.report.positive_aspects && result.report.positive_aspects.map((pos, i) => html`<li key=${i}>${pos}</li>`)}
                                    </ul>
                                </div>
                            </div>
                        `}

                        <!-- Sandbox What-If Simulator -->
                        <div className="glass-card">
                            <h3 style=${{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <span>🧪</span> What-If Simulation
                            </h3>
                            <p style=${{ fontSize: '0.9rem', color: '#9ca3af', marginBottom: '1rem' }}>Test how adding a new asset changes your risk and health scores.</p>
                            <div style=${{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                                <input 
                                    type="text" 
                                    placeholder="Ticker (e.g. RELIANCE)" 
                                    value=${whatIfTicker}
                                    onChange=${(e) => setWhatIfTicker(e.target.value)}
                                    style=${{ flex: 1, padding: '0.75rem', borderRadius: '8px', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }} 
                                />
                                <input 
                                    type="number" 
                                    placeholder="Amount ($)" 
                                    value=${whatIfAmount}
                                    onChange=${(e) => setWhatIfAmount(e.target.value)}
                                    style=${{ flex: 1, padding: '0.75rem', borderRadius: '8px', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }} 
                                />
                                <button className="btn btn-secondary" onClick=${handleWhatIfSimulate} disabled=${whatIfLoading || !whatIfTicker || !whatIfAmount} style=${{ whiteSpace: 'nowrap', width: 'auto' }}>
                                    <span>${whatIfLoading ? 'Simulating...' : 'Simulate'}</span>
                                </button>
                            </div>
                        </div>

                        <!-- Table Grid view of raw holdings -->
                        <div className="glass-card holdings-card">
                            <h2>Portfolio Holdings</h2>
                            <div className="table-container">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Asset Name</th>
                                            <th>Ticker</th>
                                            <th>Sector</th>
                                            <th className="text-right">Avg Buy Price</th>
                                            <th className="text-right">Current Price</th>
                                            <th className="text-right">Daily Change</th>
                                            <th className="text-right">Value</th>
                                            <th className="text-right">Allocation</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${result.assets && result.assets.map((asset, index) => {
                                            const buyPrice = asset['Buy Price'] || 0.0;
                                            const curPrice = asset['Current Price'] || 0.0;
                                            const prevClose = asset['Previous Close'] || 0.0;
                                            const priceChange = curPrice - prevClose;
                                            const changePct = prevClose > 0 ? (priceChange / prevClose) * 100 : 0.0;
                                            const isUp = priceChange >= 0;

                                            return html`
                                                <tr key=${index}>
                                                    <td>${asset['Asset Name']}</td>
                                                    <td><span className="badge" style=${{ background: 'rgba(99,102,241,0.1)', borderColor: 'rgba(99,102,241,0.2)', color: '#a5b4fc' }}>${asset['Ticker']}</span></td>
                                                    <td>${asset['Sector']}</td>
                                                    <td className="text-right" style=${{ color: '#e2e8f0', fontWeight: '500' }}>
                                                        ${buyPrice > 0 ? formatCurrency(buyPrice) : '--'}
                                                    </td>
                                                    <td className="text-right" style=${{ fontWeight: '500' }}>
                                                        ${curPrice > 0 ? formatCurrency(curPrice) : '--'}
                                                    </td>
                                                    <td className="text-right">
                                                        ${curPrice > 0 ? html`
                                                            <span 
                                                                className="badge" 
                                                                style=${{ 
                                                                    background: isUp ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)', 
                                                                    borderColor: isUp ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)', 
                                                                    color: isUp ? '#10b981' : '#ef4444', 
                                                                    fontWeight: '600' 
                                                                }}
                                                            >
                                                                ${isUp ? '▲' : '▼'} ${isUp ? '+' : ''}${changePct.toFixed(2)}%
                                                            </span>
                                                        ` : html`
                                                            <span className="badge" style=${{ background: 'rgba(255,255,255,0.05)', color: '#9ca3af' }}>--</span>
                                                        `}
                                                    </td>
                                                    <td className="text-right" style=${{ fontWeight: '500' }}>${formatCurrency(asset['Current Value'])}</td>
                                                    <td className="text-right" style=${{ color: '#cbd5e1', fontWeight: '600' }}>${asset.Percentage ? `${asset.Percentage.toFixed(1)}%` : '0%'}</td>
                                                </tr>
                                            `;
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <!-- Markdown Advisor reports -->
                        ${result.report && result.report.executive_summary && html`
                            <div className="glass-card report-card">
                                <div className="card-header-actions">
                                    <h2>Detailed AI Insights</h2>
                                </div>
                                <div className="report-scroll-container">
                                    <div 
                                        className="markdown-body" 
                                        dangerouslySetInnerHTML=${{ __html: marked.parse(result.report.insights ? result.report.insights.map(ins => `### ${ins.title}\n\n${ins.description}`).join('\n\n') : '') }}
                                    />
                                </div>
                            </div>
                        `}

                        <!-- Stateful GenAI chat cards widget -->
                        <div className="glass-card" style=${{ display: 'flex', flexDirection: 'column', height: '350px' }}>
                            <h3 style=${{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.5rem' }}>
                                <span>💬</span> Ask about your portfolio...
                            </h3>
                            <div style=${{ flex: 1, overflowY: 'auto', paddingRight: '0.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                ${chatHistory.map((msg, i) => html`
                                    <div 
                                        key=${i} 
                                        className=${`chat-msg ${msg.sender === 'ai' ? 'ai-msg' : 'user-msg'}`}
                                        style=${{
                                            alignSelf: msg.sender === 'ai' ? 'flex-start' : 'flex-end',
                                            background: msg.sender === 'ai' ? 'rgba(59,130,246,0.1)' : 'rgba(99,102,241,0.2)',
                                            border: msg.sender === 'ai' ? '1px solid rgba(59,130,246,0.2)' : '1px solid rgba(99,102,241,0.3)',
                                            padding: '0.75rem 1rem',
                                            borderRadius: '12px',
                                            maxWidth: '80%',
                                            borderBottomLeftRadius: msg.sender === 'ai' ? '4px' : '12px',
                                            borderBottomRightRadius: msg.sender === 'user' ? '4px' : '12px',
                                            fontSize: '0.9rem',
                                            color: '#f1f5f9'
                                        }}
                                    >
                                        ${msg.text}
                                    </div>
                                `)}
                                ${chatLoading && html`
                                    <div style=${{ alignSelf: 'flex-start', background: 'rgba(255,255,255,0.05)', padding: '0.75rem 1rem', borderRadius: '12px', color: '#94a3b8', fontSize: '0.9rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                        <span>Thinking...</span>
                                        <div className="spinner" style=${{ width: '12px', height: '12px' }}></div>
                                    </div>
                                `}
                            </div>
                            
                            <!-- Chat prompts shortcuts -->
                            <div style=${{ display: 'flex', gap: '0.5rem', margin: '0.5rem 0', flexWrap: 'wrap' }}>
                                <button className="btn btn-secondary btn-sm" onClick=${() => { setChatMessage("Which stock has the highest risk factor?"); }} style=${{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}>Highest Risk Ticker?</button>
                                <button className="btn btn-secondary btn-sm" onClick=${() => { setChatMessage("How can I minimize overall sector concentration?"); }} style=${{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}>Reduce Concentration?</button>
                            </div>

                            <div style=${{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                                <input 
                                    type="text" 
                                    placeholder="Type your question..." 
                                    value=${chatMessage}
                                    onChange=${(e) => setChatMessage(e.target.value)}
                                    onKeyDown=${(e) => e.key === 'Enter' && handleSendChat()}
                                    style=${{ flex: 1, padding: '0.75rem', borderRadius: '8px', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', color: 'white' }} 
                                />
                                <button className="btn btn-primary" onClick=${handleSendChat} disabled=${chatLoading || !chatMessage.trim()} style=${{ padding: '0.75rem 1.5rem', width: 'auto' }}>
                                    Send
                                </button>
                            </div>
                        </div>
                    `}

                </section>
            </main>
            
            <footer className="app-footer">
                <p>© 2026 DiversifyAI — Autonomous Portfolio Diversification Platform. Secure session alerts active.</p>
            </footer>
        </div>
    `;
}

// --- 4. ROOT SWITCH COMPONENT ---
function MainApp() {
    const { user, loading } = useAuth();

    if (loading) {
        return html`
            <div style=${{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyCenter: 'center', height: '100vh', backgroundColor: '#0f172a', color: '#f1f5f9', fontFamily: 'Outfit', gap: '1.5rem', justifyContent: 'center' }}>
                <div className="spinner" style=${{ width: '40px', height: '40px', borderTopColor: '#6366f1' }}></div>
                <div style=${{ fontSize: '1.1rem', fontWeight: '500', color: '#94a3b8' }}>Restoring User Session...</div>
            </div>
        `;
    }

    return html`
        ${user ? html`<${Dashboard} />` : html`<${AuthScreen} />`}
    `;
}

// Bootstrapping App Client
const root = createRoot(document.getElementById('root'));
root.render(html`
    <${AuthProvider}>
        <${MainApp} />
    </${AuthProvider}>
`);
