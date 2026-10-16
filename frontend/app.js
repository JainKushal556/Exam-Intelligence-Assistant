// ==========================================================================
// EXAM INTELLIGENCE ASSISTANT — FRONTEND CONTROLLER
// ==========================================================================

// Configurable Backend API URL (Use localhost if running locally, or Render URL)
const API_BASE_URL = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:8000"
    : "https://rag-development-journey.onrender.com";

// DOM Elements
const healthStatus = document.getElementById("health-status");
const chatFeed = document.getElementById("chat-feed");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const welcomeCard = document.getElementById("welcome-card");
const heroPoster = document.getElementById("hero-poster");
const heroCancelBtn = document.getElementById("hero-cancel-btn");
const heroCtaBtn = document.getElementById("hero-cta-btn");
const heroToggleBtn = document.getElementById("hero-toggle-btn");

// Immediately wipe any legacy dismissal flag so it never hides the banner
try {
    localStorage.removeItem("exam_intelligence_hero_dismissed");
} catch (e) {}

// Configure Marked.js for rich markdown formatting
if (typeof marked !== "undefined") {
    marked.setOptions({
        gfm: true,
        breaks: true,
        headerIds: false,
        mangle: false
    });
}

// ==========================================================================
// 1. BACKEND HEALTH CHECK & STATS
// ==========================================================================
async function checkBackendHealth() {
    if (!healthStatus) return;
    const statusText = healthStatus.querySelector(".status-text");
    try {
        const response = await fetch(`${API_BASE_URL}/health`, { method: "GET" });
        if (response.ok) {
            healthStatus.className = "status-badge online";
            statusText.textContent = "Live";
        } else {
            healthStatus.className = "status-badge offline";
            statusText.textContent = "Server Error";
        }
    } catch (error) {
        healthStatus.className = "status-badge offline";
        statusText.textContent = "Offline";
    }
}

// ==========================================================================
// 2. CHAT RENDERING & EDITORIAL STRUCTURE
// ==========================================================================
function parseAnswerAndQuestions(rawText) {
    if (!rawText) return { mainMarkdown: "", questions: [], note: "" };

    // Matches section headers introducing previous-year questions
    const sectionSplitRegex = /(?:^|\n)(?:#{1,4}\s*)?(?:📚|🎓|🏛️)?\s*(?:Related\s+|University\s+)?(?:Previous-Year\s+|Past\s+)?(?:Exam\s+|Question\s+)?(?:Papers|Questions)(?:\s*Archive)?:?\s*(?:\n|$)/i;

    const match = rawText.match(sectionSplitRegex);
    if (!match) {
        return { mainMarkdown: rawText, questions: [], note: "" };
    }

    const splitIndex = match.index;
    const mainMarkdown = rawText.slice(0, splitIndex).trim();
    const pyqSection = rawText.slice(splitIndex + match[0].length).trim();

    const lines = pyqSection.split(/\r?\n/);
    const questions = [];
    let currentQ = null;
    let noteText = "";

    for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line) continue;

        // Check for footnote note
        if (line.toLowerCase().startsWith('*note:') || line.toLowerCase().startsWith('note:')) {
            noteText = line;
            continue;
        }

        // Question line: must explicitly start with "Question" or "**Question**"
        const qMatch = line.match(/^(?:\*\*|<strong>)?Question(?:\s*\d+)?:?\s*(?:\*\*|<\/strong>)?\s*(.+)$/i);
        if (qMatch) {
            if (currentQ && currentQ.year) {
                questions.push(currentQ);
            }
            currentQ = {
                text: qMatch[1].replace(/<\/?p>/g, '').replace(/<\/?strong>/g, '').trim(),
                year: '',
                sem: '',
                marks: 'Unspecified Marks'
            };
            continue;
        }

        // Year metadata line: Year: ... | Semester: ... | Marks: ...
        const metaMatch = line.match(/(?:\*\*|<strong>)?Year:?(?:\*\*|<\/strong>)?\s*(\d{4})\s*\|\s*(?:\*\*|<strong>)?Semester:?(?:\*\*|<\/strong>)?\s*([a-zA-Z0-9]+)(?:\s*\|\s*(?:\*\*|<strong>)?Marks:?(?:\*\*|<\/strong>)?\s*([\d.]+|None|N\/A))?/i);
        if (metaMatch && currentQ) {
            currentQ.year = metaMatch[1];
            currentQ.sem = metaMatch[2];
            const m = metaMatch[3];
            currentQ.marks = (m && m !== 'None' && m !== 'N/A') ? `${m} Marks` : 'Unspecified Marks';
            questions.push(currentQ);
            currentQ = null;
            continue;
        }

        // Continuation line of question text
        if (currentQ) {
            currentQ.text += ' ' + line;
        }
    }

    if (currentQ && currentQ.year) {
        questions.push(currentQ);
    }

    return { mainMarkdown, questions, note: noteText };
}

function renderMarkdownText(md) {
    if (!md) return "";
    if (typeof marked !== "undefined" && typeof marked.parse === "function") {
        try {
            return marked.parse(md);
        } catch (e) {
            console.warn("Marked.js parse warning:", e);
        }
    }
    return md.replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>");
}

function renderResponse(raw) {
    if (!raw) return "";
    const { mainMarkdown, questions, note } = parseAnswerAndQuestions(raw);
    
    let html = renderMarkdownText(mainMarkdown);

    if (questions.length > 0) {
        const questionItemsHtml = questions.map((q, idx) => `
            <li class="pyq-ref-item">
                <div class="pyq-ref-num">${String(idx + 1).padStart(2, '0')}</div>
                <div class="pyq-ref-body">
                    <p class="pyq-ref-question">${q.text}</p>
                    <div class="pyq-ref-meta">
                        <span class="meta-tag tag-yr">Year ${q.year}</span>
                        <span class="meta-dot">·</span>
                        <span class="meta-tag tag-sm">Semester ${q.sem}</span>
                        <span class="meta-dot">·</span>
                        <span class="meta-tag tag-mk">${q.marks}</span>
                    </div>
                </div>
            </li>
        `).join("");

        const referenceSection = `
            <div class="pyq-editorial-block">
                <div class="pyq-ref-header">
                    <div class="pyq-ref-title-group">
                        <span class="pyq-ref-badge">EXAM ARCHIVE</span>
                        <h4 class="pyq-ref-heading">Previous-Year Question Papers</h4>
                    </div>
                    <span class="pyq-ref-count">${questions.length} Match${questions.length > 1 ? 'es' : ''}</span>
                </div>
                <ul class="pyq-ref-list">
                    ${questionItemsHtml}
                </ul>
            </div>
        `;

        html += referenceSection;
    }

    if (note) {
        html += `<div class="pyq-note-block">${renderMarkdownText(note)}</div>`;
    }

    return html;
}

function finalizeAiMessage(contentEl, content, sources = []) {
    // Parse answer to check if any previous-year question chunks were returned
    const { questions } = parseAnswerAndQuestions(content);
    const hasChunks = Array.isArray(questions) && questions.length > 0;
    const renderedHtml = renderResponse(content);

    let sourcesHtml = "";
    // Only show source files if chunks were returned in the answer and sources exist
    if (hasChunks && Array.isArray(sources) && sources.length > 0) {
        const pills = sources.map(src => `<span class="source-file-pill" title="${src}">${src}</span>`).join("");
        sourcesHtml = `
            <div class="message-sources-bar">
                <div class="sources-label">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                    <span>Sources:</span>
                </div>
                <div class="sources-tags">
                    ${pills}
                </div>
            </div>
        `;
    }

    contentEl.innerHTML = `
        <div class="message-meta-bar">
            <span class="ai-source-label">Exam Assistant</span>
            <button type="button" class="btn-copy" title="Copy answer" aria-label="Copy answer">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
                <span>Copy</span>
            </button>
        </div>
        <div class="message-body">${renderedHtml}</div>
        ${sourcesHtml}
    `;

    // Attach Copy Event Handler
    const copyBtn = contentEl.querySelector(".btn-copy");
    if (copyBtn) {
        copyBtn.addEventListener("click", () => {
            navigator.clipboard.writeText(content).then(() => {
                const span = copyBtn.querySelector("span");
                const prev = span.textContent;
                span.textContent = "Copied!";
                copyBtn.classList.add("copied");
                setTimeout(() => {
                    span.textContent = prev;
                    copyBtn.classList.remove("copied");
                }, 2000);
            });
        });
    }
}

function appendMessage(sender, content, isMarkdown = false, sources = []) {
    if (!chatFeed) return;

    if (heroPoster && heroPoster.style.display !== "none") {
        heroPoster.style.display = "none";
    }
    if (welcomeCard && welcomeCard.style.display !== "none") {
        welcomeCard.style.display = "none";
    }

    const messageEl = document.createElement("div");
    messageEl.className = `message message-${sender}`;

    const contentEl = document.createElement("div");
    contentEl.className = "message-content";

    if (sender === "ai" && isMarkdown) {
        finalizeAiMessage(contentEl, content, sources);
    } else if (isMarkdown) {
        contentEl.innerHTML = renderResponse(content);
    } else {
        const p = document.createElement("p");
        p.textContent = content;
        contentEl.appendChild(p);
    }

    messageEl.appendChild(contentEl);
    chatFeed.appendChild(messageEl);
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

// ==========================================================================
// 3. QUERY SUBMISSION (WITH REAL-TIME TOKEN STREAMING)
// ==========================================================================
async function submitQuery(queryText) {
    const query = (queryText || chatInput.value).trim();
    if (!query) return;

    appendMessage("user", query);
    chatInput.value = "";
    adjustTextareaHeight();
    sendBtn.disabled = true;

    // Add typing indicator
    const typingId = "typing-" + Date.now();
    const typingEl = document.createElement("div");
    typingEl.className = "message message-ai typing-msg";
    typingEl.id = typingId;
    typingEl.innerHTML = `
        <div class="message-content">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
            <span class="typing-text">Searching past exam papers & synthesizing answer...</span>
        </div>
    `;
    chatFeed.appendChild(typingEl);
    chatFeed.scrollTop = chatFeed.scrollHeight;

    let aiMessageEl = null;
    let contentEl = null;
    let bodyEl = null;
    let accumulatedText = "";
    let streamSources = [];

    function initStreamBubble() {
        document.getElementById(typingId)?.remove();

        aiMessageEl = document.createElement("div");
        aiMessageEl.className = "message message-ai";

        contentEl = document.createElement("div");
        contentEl.className = "message-content";
        contentEl.innerHTML = `
            <div class="message-meta-bar">
                <span class="ai-source-label">Exam Assistant</span>
            </div>
            <div class="message-body"></div>
        `;

        bodyEl = contentEl.querySelector(".message-body");
        aiMessageEl.appendChild(contentEl);
        chatFeed.appendChild(aiMessageEl);
        chatFeed.scrollTop = chatFeed.scrollHeight;
    }

    try {
        const streamUrl = `${API_BASE_URL}/query-stream?query=${encodeURIComponent(query)}`;
        const response = await fetch(streamUrl, { method: "POST" });

        if (!response.ok) {
            throw new Error(`Stream HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const blocks = buffer.split("\n\n");
            buffer = blocks.pop() || "";

            for (const block of blocks) {
                const line = block.trim();
                if (!line.startsWith("data:")) continue;
                const jsonStr = line.slice(5).trim();
                if (!jsonStr) continue;

                try {
                    const data = JSON.parse(jsonStr);
                    if (data.type === "sources") {
                        streamSources = data.sources || [];
                    } else if (data.type === "token") {
                        if (!aiMessageEl) initStreamBubble();
                        accumulatedText += data.token;
                        if (bodyEl) {
                            bodyEl.innerHTML = renderResponse(accumulatedText);
                            chatFeed.scrollTop = chatFeed.scrollHeight;
                            // Yield to the browser paint cycle so words animate block-by-block
                            await new Promise(resolve => setTimeout(resolve, 15));
                        }
                    } else if (data.type === "done") {
                        // Stream done
                    }
                } catch (jsonErr) {
                    console.warn("SSE json parse error:", jsonErr);
                }
            }
        }

        // Finalize editorial card & sources when streaming completes
        if (aiMessageEl && contentEl) {
            finalizeAiMessage(contentEl, accumulatedText, streamSources);
            chatFeed.scrollTop = chatFeed.scrollHeight;
        } else {
            document.getElementById(typingId)?.remove();
            appendMessage("ai", accumulatedText || "No answer generated.", true, streamSources);
        }

    } catch (streamErr) {
        console.warn("Streaming unavailable, falling back to legacy query:", streamErr);
        try {
            const fallbackRes = await fetch(`${API_BASE_URL}/query?query=${encodeURIComponent(query)}`, {
                method: "POST"
            });
            const data = await fallbackRes.json();
            document.getElementById(typingId)?.remove();

            if (fallbackRes.ok && data.answer) {
                appendMessage("ai", data.answer, true, data.sources || []);
            } else {
                const errorMsg = data.detail || "Unable to get an answer from the database.";
                appendMessage("ai", `❌ **Error**: ${errorMsg}`, true);
            }
        } catch (error) {
            document.getElementById(typingId)?.remove();
            console.error("Query API Error:", error);
            appendMessage("ai", `❌ **Connection Error**: Could not connect to the backend server (${API_BASE_URL}).`, true);
        }
    } finally {
        sendBtn.disabled = false;
        chatInput.focus();
    }
}

// Auto-expand textarea
function adjustTextareaHeight() {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + "px";
}

// ==========================================================================
// 4. HERO POSTER CONTROLLER (DISPLAY & DISMISSAL)
// ==========================================================================
function dismissHeroPoster() {
    if (!heroPoster) return;
    heroPoster.classList.add("hero-poster-closing");
    setTimeout(() => {
        heroPoster.style.display = "none";
        heroPoster.classList.remove("hero-poster-closing");
        if (welcomeCard && !chatFeed.querySelector(".message")) {
            welcomeCard.style.display = "block";
        }
    }, 260);
}

function showHeroPoster() {
    if (!heroPoster) return;
    heroPoster.classList.remove("hero-poster-closing");
    heroPoster.style.display = "block";
    if (welcomeCard) {
        welcomeCard.style.display = "none";
    }
    if (chatFeed) {
        chatFeed.scrollTo({ top: 0, behavior: "smooth" });
    }
}

// ==========================================================================
// 5. EVENT LISTENERS
// ==========================================================================
chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    submitQuery();
});

chatInput.addEventListener("input", adjustTextareaHeight);

chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        submitQuery();
    }
});

// Hero Section Actions
if (heroCancelBtn) {
    heroCancelBtn.addEventListener("click", () => {
        dismissHeroPoster();
    });
}

if (heroCtaBtn) {
    heroCtaBtn.addEventListener("click", () => {
        // CTA connects to existing question interface
        dismissHeroPoster();
        if (chatInput) {
            chatInput.focus();
            chatInput.scrollIntoView({ behavior: "smooth", block: "center" });
            const form = document.getElementById("chat-form");
            if (form) {
                form.classList.add("input-pulse");
                setTimeout(() => form.classList.remove("input-pulse"), 1600);
            }
        }
    });
}

if (heroToggleBtn) {
    heroToggleBtn.addEventListener("click", () => {
        const isHidden = !heroPoster || heroPoster.style.display === "none" || getComputedStyle(heroPoster).display === "none";
        if (isHidden) {
            showHeroPoster();
        } else {
            dismissHeroPoster();
        }
    });
}

// Clickable suggestion chips
document.addEventListener("click", (e) => {
    const chip = e.target.closest(".suggestion-chip");
    if (chip) {
        const query = chip.getAttribute("data-query");
        if (query) {
            submitQuery(query);
        }
    }
});

// ==========================================================================
// 6. INITIALIZATION (PHONE & LAPTOP AUTO-LOAD)
// ==========================================================================
function initApp() {
    checkBackendHealth();

    // Clean up any legacy localStorage flag so it never hides the banner
    try {
        localStorage.removeItem("exam_intelligence_hero_dismissed");
    } catch (e) {}

    // Every time the app loads fresh (on phone or laptop), show the hero banner automatically
    if (heroPoster) {
        heroPoster.classList.remove("hero-poster-closing");
        heroPoster.style.display = "block";
    }
    if (welcomeCard) {
        welcomeCard.style.display = "none";
    }

    // Scroll chat feed and window to top so the banner is immediately in view
    if (chatFeed) {
        chatFeed.scrollTop = 0;
    }
    window.scrollTo(0, 0);

    // On mobile devices, avoid autofocusing so the virtual keyboard does not pop up
    // and obscure the hero banner immediately upon opening the app.
    const isMobileDevice = window.innerWidth <= 768 || /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    if (!isMobileDevice && chatInput) {
        chatInput.focus({ preventScroll: true });
    }
}

// Ensure initApp runs regardless of readyState timing
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
} else {
    initApp();
}

// Recurring health check
setInterval(checkBackendHealth, 12 * 60 * 1000);

// Handle mobile browser back/forward cache or tab wake-up
window.addEventListener("pageshow", () => {
    if (heroPoster && !chatFeed?.querySelector(".message")) {
        heroPoster.style.display = "block";
        heroPoster.classList.remove("hero-poster-closing");
        if (welcomeCard) welcomeCard.style.display = "none";
        if (chatFeed) chatFeed.scrollTop = 0;
    }
});
