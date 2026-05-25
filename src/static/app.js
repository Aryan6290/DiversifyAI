/* ==========================================
   Client-Side Controller - DiversifyAI
   ========================================== */

document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("file-input");
    const fileInfo = document.getElementById("file-info");
    const fileNameDisplay = document.getElementById("file-name");
    const removeFileBtn = document.getElementById("remove-file");
    const analyzeBtn = document.getElementById("analyze-btn");
    const btnSpinner = document.getElementById("btn-spinner");
    const customApiKeyInput = document.getElementById("custom-api-key");
    const modelInput = document.getElementById("model-input");
    const btnUpstox = document.getElementById("btn-upstox");
    
    // Cards to show/hide
    const welcomeCard = document.getElementById("welcome-card");
    const metricsCard = document.getElementById("metrics-card");
    const chartsCard = document.getElementById("charts-card");
    const reportCard = document.getElementById("report-card");
    const holdingsCard = document.getElementById("holdings-card");
    const aiSummaryCard = document.getElementById("ai-summary-card");
    const risksCard = document.getElementById("risks-card");
    const whatifCard = document.getElementById("whatif-card");
    const chatCard = document.getElementById("chat-card");
    
    // Data display fields
    const totalAssetsVal = document.getElementById("total-assets-val");
    const assetsCountBadge = document.getElementById("assets-count-badge");
    const healthScoreVal = document.getElementById("health-score-val");
    const riskScoreVal = document.getElementById("risk-score-val");
    const benchmarkVal = document.getElementById("benchmark-val");
    
    const aiExecSummary = document.getElementById("ai-exec-summary");
    const topRisksList = document.getElementById("top-risks-list");
    const positiveAspectsList = document.getElementById("positive-aspects-list");
    
    const reportContent = document.getElementById("report-content");
    const holdingsTableBody = document.querySelector("#holdings-table tbody");
    
    // Chat & What-If Elements
    const chatInput = document.getElementById("chat-input");
    const chatBtn = document.getElementById("chat-btn");
    const chatHistory = document.getElementById("chat-history");
    const whatifTicker = document.getElementById("whatif-ticker");
    const whatifAmount = document.getElementById("whatif-amount");
    const whatifBtn = document.getElementById("whatif-btn");
    
    // Tab switching
    const tabButtons = document.querySelectorAll(".tab-btn");
    const tabPanels = document.querySelectorAll(".tab-panel");

    // State Variables
    let selectedFile = null;
    let chartInstances = {};
    let rawHoldings = [];
    let chatMessages = [];

    // Drag & Drop
    dropzone.addEventListener("click", (e) => {
        if (e.target.closest("#remove-file")) return;
        fileInput.click();
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) handleFileSelection(e.target.files[0]);
    });

    ["dragenter", "dragover"].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => { e.preventDefault(); e.stopPropagation(); dropzone.classList.add("active"); }, false);
    });

    ["dragleave", "drop"].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => { e.preventDefault(); e.stopPropagation(); dropzone.classList.remove("active"); }, false);
    });

    dropzone.addEventListener("drop", (e) => {
        if (e.dataTransfer.files.length > 0) handleFileSelection(e.dataTransfer.files[0]);
    });

    function handleFileSelection(file) {
        if (!file.name.endsWith(".csv")) { alert("Please select a valid CSV."); return; }
        selectedFile = file;
        fileNameDisplay.textContent = file.name;
        fileInfo.classList.remove("hidden");
        analyzeBtn.disabled = false;
        dropzone.querySelector(".dropzone-content").classList.add("hidden");
    }

    removeFileBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        selectedFile = null;
        fileInput.value = "";
        fileInfo.classList.add("hidden");
        analyzeBtn.disabled = true;
        dropzone.querySelector(".dropzone-content").classList.remove("hidden");
    });

    // Tabs
    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetPanel = btn.getAttribute("data-tab");
            tabButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            tabPanels.forEach(panel => {
                if (panel.id === targetPanel) panel.classList.add("active");
                else panel.classList.remove("active");
            });
        });
    });

    // API Analysis
    analyzeBtn.addEventListener("click", async () => {
        if (!selectedFile) return;
        analyzeBtn.disabled = true;
        btnSpinner.classList.remove("hidden");
        
        const formData = new FormData();
        formData.append("file", selectedFile);
        
        await performAnalysis("/api/analyze", { method: "POST", body: formData });
    });

    if (btnUpstox) {
        btnUpstox.addEventListener("click", async () => {
            const customKey = customApiKeyInput.value.trim();
            if (!customKey) {
                alert("Please enter your API Key before connecting to the broker.");
                return;
            }
            
            try {
                const btnOriginalText = btnUpstox.innerText;
                btnUpstox.innerText = "Connecting...";
                btnUpstox.disabled = true;

                // Open Upstox Login in a popup synchronously to avoid popup blocker
                const popup = window.open('', 'UpstoxLogin', 'width=600,height=700,status=yes,scrollbars=yes');
                if (popup) {
                    popup.document.write("<h2 style='font-family: sans-serif; text-align: center; margin-top: 50px;'>Loading Upstox login...</h2>");
                }

                const res = await fetch("/api/auth/upstox/login");
                const data = await res.json();
                
                if (!data.success) {
                    if (popup) popup.close();
                    throw new Error(data.error);
                }

                if (popup) {
                    popup.location.href = data.login_url;
                }
                
                // Listen for success message from popup
                const messageHandler = (event) => {
                    if (!event.origin.includes("localhost") && !event.origin.includes("127.0.0.1")) return;

                    const result = event.data;
                    if (result && typeof result.success !== 'undefined') {
                        window.removeEventListener('message', messageHandler);
                        btnUpstox.innerText = btnOriginalText;
                        btnUpstox.disabled = false;

                        if (result.success) {
                            if (result.is_raw_holdings) {
                                btnUpstox.innerText = "Analyzing...";
                                btnUpstox.disabled = true;
                                btnSpinner.classList.remove("hidden");
                                
                                const selectedModel = modelInput.value.trim();
                                const cleanApiKey = customApiKeyInput.value.trim().replace(/[^\x00-\x7F]/g, "");
                                
                                fetch("/api/analyze_holdings", {
                                    method: "POST",
                                    headers: {
                                        "Content-Type": "application/json",
                                        "X-Model": selectedModel,
                                        "X-API-Key": cleanApiKey
                                    },
                                    body: JSON.stringify({ holdings: result.holdings })
                                })
                                .then(res => res.json())
                                .then(analysisResult => {
                                    btnUpstox.innerText = btnOriginalText;
                                    btnUpstox.disabled = false;
                                    btnSpinner.classList.add("hidden");
                                    
                                    if (!analysisResult.success) {
                                        alert(`⚠️ Analysis Error: ${analysisResult.error}`);
                                        return;
                                    }
                                    
                                    // Success Transition
                                    welcomeCard.classList.add("hidden");
                                    metricsCard.classList.remove("hidden");
                                    chartsCard.classList.remove("hidden");
                                    reportCard.classList.remove("hidden");
                                    holdingsCard.classList.remove("hidden");
                                    aiSummaryCard.classList.remove("hidden");
                                    risksCard.classList.remove("hidden");
                                    whatifCard.classList.remove("hidden");
                                    chatCard.classList.remove("hidden");

                                    rawHoldings = analysisResult.assets;
                                    renderMetrics(analysisResult);
                                    renderCharts(analysisResult);
                                    renderHoldingsTable(analysisResult.assets);
                                    renderAIReport(analysisResult.report);
                                })
                                .catch(err => {
                                    console.error(err);
                                    alert(`⚠️ Failed to analyze holdings: ${err.message}`);
                                    btnUpstox.innerText = btnOriginalText;
                                    btnUpstox.disabled = false;
                                    btnSpinner.classList.add("hidden");
                                });
                            }
                        } else {
                            alert(`⚠️ Upstox Connect Error: ${result.error}`);
                        }
                    }
                };
                
                window.addEventListener('message', messageHandler);

                const checkPopup = setInterval(() => {
                    if (popup.closed) {
                        clearInterval(checkPopup);
                        window.removeEventListener('message', messageHandler);
                        btnUpstox.innerText = btnOriginalText;
                        btnUpstox.disabled = false;
                    }
                }, 1000);

            } catch (err) {
                console.error(err);
                alert(`⚠️ Failed to init Upstox login: ${err.message}`);
                btnUpstox.innerText = "Connect Upstox";
                btnUpstox.disabled = false;
            }
        });
    }

    
    // What-If Simulation
    whatifBtn.addEventListener("click", async () => {
        const ticker = whatifTicker.value.trim();
        const amount = parseFloat(whatifAmount.value.trim());
        
        if (!ticker || isNaN(amount) || amount <= 0) {
            alert("Please enter a valid ticker and amount.");
            return;
        }
        
        whatifBtn.disabled = true;
        whatifBtn.textContent = "Running...";
        
        // Clone current holdings and append mock row
        const mockHoldings = JSON.parse(JSON.stringify(rawHoldings));
        mockHoldings.push({
            "Asset Name": "Simulated " + ticker,
            "Ticker": ticker,
            "Asset Type": "Equity",
            "Sector": "Unclassified",
            "Current Value": amount,
            "Currency": "USD"
        });
        
        await performAnalysis("/api/analyze_holdings", {
            method: "POST",
            body: JSON.stringify({ holdings: mockHoldings })
        });
        
        whatifBtn.disabled = false;
        whatifBtn.textContent = "Simulate";
    });
    
    // Chat Interface
    chatBtn.addEventListener("click", async () => {
        const msg = chatInput.value.trim();
        if (!msg) return;
        
        // Add user msg to UI
        appendChatMessage(msg, "user");
        chatInput.value = "";
        
        chatBtn.disabled = true;
        chatBtn.textContent = "...";
        
        try {
            const headers = getHeaders();
            headers["Content-Type"] = "application/json";
            
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: headers,
                body: JSON.stringify({
                    message: msg,
                    history: chatMessages,
                    holdings: rawHoldings
                })
            });
            const data = await res.json();
            if (data.success) {
                appendChatMessage(data.reply, "ai");
                chatMessages.push({"role": "user", "content": msg});
                chatMessages.push({"role": "assistant", "content": data.reply});
            } else {
                appendChatMessage("Error: " + data.error, "error");
            }
        } catch (e) {
            appendChatMessage("Connection error.", "error");
        } finally {
            chatBtn.disabled = false;
            chatBtn.textContent = "Send";
        }
    });
    
    function appendChatMessage(text, sender) {
        const div = document.createElement("div");
        div.className = `chat-msg ${sender}-msg`;
        div.style.padding = "0.75rem 1rem";
        div.style.borderRadius = "12px";
        div.style.maxWidth = "80%";
        
        if (sender === "user") {
            div.style.alignSelf = "flex-end";
            div.style.background = "rgba(16,185,129,0.1)";
            div.style.border = "1px solid rgba(16,185,129,0.2)";
            div.style.borderBottomRightRadius = "4px";
            div.style.color = "#a7f3d0";
        } else {
            div.style.alignSelf = "flex-start";
            div.style.background = "rgba(59,130,246,0.1)";
            div.style.border = "1px solid rgba(59,130,246,0.2)";
            div.style.borderBottomLeftRadius = "4px";
            div.style.color = "#e5e7eb";
        }
        
        div.textContent = text;
        chatHistory.appendChild(div);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function getHeaders() {
        const customKey = customApiKeyInput.value.trim().replace(/[^\x00-\x7F]/g, "");
        const selectedModel = modelInput.value.trim();
        const headers = { "X-Model": selectedModel };
        if (customKey) headers["X-API-Key"] = customKey;
        return headers;
    }

    async function performAnalysis(endpoint, options) {
        try {
            options.headers = options.headers || {};
            Object.assign(options.headers, getHeaders());
            if (endpoint === "/api/analyze_holdings" && !options.headers["Content-Type"]) {
                options.headers["Content-Type"] = "application/json";
            }

            const response = await fetch(endpoint, options);
            const result = await response.json();

            if (!response.ok || !result.success) throw new Error(result.error || "Failed to analyze.");

            // Success Transition
            welcomeCard.classList.add("hidden");
            metricsCard.classList.remove("hidden");
            chartsCard.classList.remove("hidden");
            reportCard.classList.remove("hidden");
            holdingsCard.classList.remove("hidden");
            aiSummaryCard.classList.remove("hidden");
            risksCard.classList.remove("hidden");
            whatifCard.classList.remove("hidden");
            chatCard.classList.remove("hidden");

            rawHoldings = result.assets; // Store for what-if
            renderMetrics(result);
            renderCharts(result);
            renderHoldingsTable(result.assets);
            renderAIReport(result.report);

        } catch (error) {
            console.error(error);
            alert(`⚠️ Error: ${error.message}`);
        } finally {
            analyzeBtn.disabled = false;
            btnSpinner.classList.add("hidden");
        }
    }

    function renderMetrics(data) {
        totalAssetsVal.textContent = formatCurrency(data.total_value);
        assetsCountBadge.textContent = `${data.assets.length} holdings`;
        
        // Render Scores (assuming report is structured JSON from new analyzer)
        if (data.report && typeof data.report === 'object') {
            const hs = data.report.health_score || data.calculated_health_score || 0;
            const rs = data.report.risk_score || data.calculated_risk_score || 0;
            
            healthScoreVal.textContent = `${hs}/100`;
            healthScoreVal.style.color = hs > 70 ? "#10b981" : (hs > 40 ? "#f59e0b" : "#f43f5e");
            
            riskScoreVal.textContent = `${rs}/10`;
            riskScoreVal.style.color = rs > 7 ? "#f43f5e" : (rs > 4 ? "#f59e0b" : "#10b981");
        }
        
        if (data.benchmark) {
            benchmarkVal.textContent = `vs ${data.benchmark.benchmark_name}: ${data.benchmark.outperformance} outperformance`;
        }
    }

    function renderAIReport(report) {
        if (typeof report !== 'object') {
            // Fallback if not JSON
            reportContent.innerHTML = `<pre style="white-space:pre-wrap;">${escapeHTML(report)}</pre>`;
            return;
        }
        
        aiExecSummary.textContent = report.executive_summary || "Analysis complete.";
        
        topRisksList.innerHTML = "";
        (report.top_risks || []).forEach(risk => {
            const li = document.createElement("li");
            li.textContent = risk;
            topRisksList.appendChild(li);
        });
        
        positiveAspectsList.innerHTML = "";
        (report.positive_aspects || []).forEach(pos => {
            const li = document.createElement("li");
            li.textContent = pos;
            positiveAspectsList.appendChild(li);
        });
        
        reportContent.innerHTML = "";
        (report.insights || []).forEach(insight => {
            const div = document.createElement("div");
            div.style.marginBottom = "1rem";
            div.style.padding = "1rem";
            div.style.borderRadius = "8px";
            div.style.background = "rgba(255,255,255,0.03)";
            div.style.borderLeft = `4px solid ${insight.type === 'warning' ? '#f43f5e' : (insight.type === 'positive' ? '#10b981' : '#3b82f6')}`;
            
            div.innerHTML = `
                <h4 style="margin-bottom: 0.5rem; color: #fff;">${escapeHTML(insight.title)}</h4>
                <p style="color: #9ca3af; font-size: 0.95rem; line-height: 1.5;">${escapeHTML(insight.description)}</p>
            `;
            reportContent.appendChild(div);
        });
    }

    function renderHoldingsTable(assets) {
        holdingsTableBody.innerHTML = "";
        assets.forEach(asset => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td><strong>${escapeHTML(asset["Asset Name"])}</strong></td>
                <td><code style="background: rgba(255,255,255,0.06); padding: 0.2rem 0.4rem; border-radius: 4px;">${escapeHTML(asset["Ticker"])}</code></td>
                <td>${escapeHTML(asset["Sector"])}</td>
                <td class="text-right">${formatCurrency(asset["Current Value"])}</td>
                <td class="text-right font-medium" style="color: var(--color-primary); font-weight:600;">${asset["Percentage"].toFixed(2)}%</td>
            `;
            holdingsTableBody.appendChild(row);
        });
    }

    function renderCharts(data) {
        const palettes = {
            base: ["#6366f1", "#a855f7", "#10b981", "#f59e0b", "#ec4899", "#06b6d4", "#3b82f6", "#f43f5e"],
            mcap: ["#3b82f6", "#8b5cf6", "#f43f5e"],
            risk: ["#10b981", "#f59e0b", "#f43f5e"]
        };

        const createChart = (id, breakdown, labelCol, palette) => {
            if (chartInstances[id]) chartInstances[id].destroy();
            const ctx = document.getElementById(id).getContext("2d");
            const labels = breakdown.map(item => item[labelCol]);
            const values = breakdown.map(item => item["Percentage"]);
            
            chartInstances[id] = new Chart(ctx, {
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

        createChart("assetChart", data.asset_type_breakdown, "Asset Type", palettes.base);
        createChart("sectorChart", data.sector_breakdown, "Sector", palettes.base.slice().reverse());
        createChart("mcapChart", data.market_cap_breakdown, "MarketCapCategory", palettes.mcap);
        createChart("riskChart", data.risk_breakdown, "RiskCategory", palettes.risk);
    }

    function formatCurrency(value) {
        return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 }).format(value);
    }

    function escapeHTML(str) {
        if (!str) return "";
        return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }
});
