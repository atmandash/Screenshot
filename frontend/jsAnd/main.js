/**
 * RealityGap — Constellation Core (Restored)
 */

// ── DOM Interaction ─────────────────────────────────────────

const els = {
    landing: document.getElementById("landing-page"),
    uploadZone: document.getElementById("upload-zone"),
    inputTrigger: document.getElementById("input-trigger"),
    fileInput: document.getElementById("file-input"),
    btnAnalyze: document.getElementById("btn-analyze"),

    analyzing: document.getElementById("analyzing-section"),
    analyzingText: document.getElementById("analyzing-text"),
    progressBar: document.getElementById("progress-bar"),

    results: document.getElementById("results-section"),
    verdictTitle: document.getElementById("verdict-title"),
    verdictMsg: document.getElementById("verdict-message"),
    scoreVal: document.getElementById("score-value"),
    cardsContainer: document.getElementById("analyzer-cards"),
    elaViewer: document.getElementById("ela-viewer"),
    elaOrig: document.getElementById("ela-original"),
    elaRes: document.getElementById("ela-result"),
    btnRecheck: document.getElementById("btn-recheck")
};

const API_URL = "/api/analyze";

// ── Canvas Logic: Constellation Sphere ─────────────

(function initScene() {
    const canvas = document.getElementById("constellation-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    // Globals
    let width, height;

    // ── Constellation Logic ──
    let nodes = [];
    const NODE_COUNT = 100; // Restored high node count
    const RADIUS = 280; // Constellation Sphere Radius
    const CONNECTION_DIST = 100;

    function init() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;

        // Setup Constellation Nodes
        nodes = [];
        for (let i = 0; i < NODE_COUNT; i++) {
            const phi = Math.acos(-1 + (2 * i) / NODE_COUNT);
            const theta = Math.sqrt(NODE_COUNT * Math.PI) * phi;
            nodes.push({
                x: RADIUS * Math.cos(theta) * Math.sin(phi),
                y: RADIUS * Math.sin(theta) * Math.sin(phi),
                z: RADIUS * Math.cos(phi)
            });
        }
    }

    window.addEventListener("resize", init);
    init();

    // ── Widget DOM Sync Setup ──
    const widgetElements = document.querySelectorAll('.gw-revolving');
    let widgets = [];
    widgetElements.forEach(el => {
        const lat = parseFloat(el.dataset.lat || 0) * (Math.PI / 180);
        const lon = parseFloat(el.dataset.lon || 0) * (Math.PI / 180);
        // Slightly larger radius for widgets so they float outside
        widgets.push({ el, lat, lon });
    });

    // ── Animation Loop ──
    let angleX = 0;
    let angleY = 0;

    function rotate(node, angX, angY) {
        let x = node.x * Math.cos(angY) - node.z * Math.sin(angY);
        let z = node.x * Math.sin(angY) + node.z * Math.cos(angY);
        let y = node.y;

        let ynew = y * Math.cos(angX) - z * Math.sin(angX);
        let znew = y * Math.sin(angX) + z * Math.cos(angX);
        return { x: x, y: ynew, z: znew };
    }

    function draw() {
        ctx.clearRect(0, 0, width, height);

        const isMobile = window.innerWidth < 900;
        const cx = isMobile ? width * 0.5 : width * 0.75;
        // Shift center UP to avoid footer overlap
        const cy = height * 0.45;

        angleY += 0.002;
        angleX += 0.001;

        const projected = nodes.map(n => {
            const r = rotate(n, angleX, angleY);
            const scale = 2000 / (2000 - r.z);
            return {
                x: cx + r.x * scale,
                y: cy + r.y * scale,
                z: r.z,
                alpha: (r.z + RADIUS) / (2 * RADIUS)
            };
        });

        // Connections
        ctx.strokeStyle = "rgba(0, 240, 255, 0.15)";
        ctx.lineWidth = 1;
        for (let i = 0; i < projected.length; i++) {
            const p1 = projected[i];
            if (p1.alpha < 0.1) continue;
            for (let j = i + 1; j < projected.length; j++) {
                const p2 = projected[j];
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                if (Math.sqrt(dx * dx + dy * dy) < CONNECTION_DIST) {
                    ctx.beginPath();
                    ctx.moveTo(p1.x, p1.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.stroke();
                }
            }
        }

        // Nodes
        for (const p of projected) {
            ctx.beginPath();
            ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 255, 255, ${p.alpha})`;
            ctx.fill();
        }

        // 4. Update Widget DOM Positions
        if (els.landing.style.display !== 'none') {
            widgets.forEach(w => {
                // Calculate Base Position on Sphere
                const r0 = RADIUS + 40;
                const bx = r0 * Math.cos(w.lat) * Math.cos(w.lon);
                const by = r0 * Math.sin(w.lat);
                const bz = r0 * Math.cos(w.lat) * Math.sin(w.lon);

                // Rotate
                const rot = rotate({ x: bx, y: by, z: bz }, angleX, angleY);

                // Apply flattened Y for footer clearance safety
                rot.y *= 0.6;

                const scale = 2000 / (2000 - rot.z);
                const opacity = Math.max(0.2, (rot.z + RADIUS * 1.5) / (2 * RADIUS));
                const zIndex = Math.floor(rot.z + 1000);

                w.el.style.transform = `translate(-50%, -50%) translate3d(${rot.x}px, ${rot.y}px, ${rot.z}px) scale(${scale})`;
                w.el.style.opacity = opacity;
                w.el.style.zIndex = zIndex;
            });
        }

        requestAnimationFrame(draw);
    }

    // Start the loop
    draw();
})();


// ── Event Logic (Upload/Analysis - Unchanged) ────────────────

function triggerUpload() { els.fileInput.click(); }

if (els.uploadZone) {
    els.uploadZone.addEventListener("click", triggerUpload);
    els.uploadZone.addEventListener("dragover", e => { e.preventDefault(); els.uploadZone.style.borderColor = "var(--accent-cyan)"; });
    els.uploadZone.addEventListener("dragleave", () => { els.uploadZone.style.borderColor = ""; });
    els.uploadZone.addEventListener("drop", e => {
        e.preventDefault();
        els.uploadZone.style.borderColor = "";
        if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
    });
}
if (els.inputTrigger) els.inputTrigger.addEventListener("click", (e) => { e.stopPropagation(); triggerUpload(); });
if (els.btnAnalyze) els.btnAnalyze.addEventListener("click", (e) => { e.stopPropagation(); triggerUpload(); });

if (els.fileInput) {
    els.fileInput.addEventListener("change", e => {
        if (e.target.files[0]) handleFile(e.target.files[0]);
    });
}

if (els.btnRecheck) els.btnRecheck.addEventListener("click", resetUI);

let fileBlob = null;

function handleFile(file) {
    if (!file.type.startsWith("image/")) { alert("Images only, please."); return; }
    if (fileBlob) URL.revokeObjectURL(fileBlob);
    fileBlob = URL.createObjectURL(file);
    showState("analyzing");
    analyze(file);
}

async function analyze(file) {
    const fd = new FormData();
    fd.append("file", file);

    let progress = 0;
    const timer = setInterval(() => {
        progress += 5;
        if (progress > 90) progress = 90;
        if (els.progressBar) els.progressBar.style.width = progress + "%";
    }, 200);

    try {
        const res = await fetch(API_URL, { method: "POST", body: fd });
        clearInterval(timer);
        if (els.progressBar) els.progressBar.style.width = "100%";

        if (!res.ok) throw new Error("API Error");
        const data = await res.json();

        await new Promise(r => setTimeout(r, 600));
        renderResults(data);

    } catch (e) {
        clearInterval(timer);
        if (els.analyzingText) els.analyzingText.textContent = "Error: " + e.message;
        setTimeout(resetUI, 3000);
    }
}

function renderResults(report) {
    const ov = report.overall;
    const az = report.analyzers;

    els.verdictTitle.textContent = ov.verdict.toUpperCase();
    els.verdictMsg.textContent = ov.message;
    els.scoreVal.textContent = ov.score;

    let hue = "var(--success)";
    if (ov.score > 50) hue = "var(--danger)";
    else if (ov.score > 20) hue = "var(--accent-blue)";
    els.verdictTitle.style.color = hue;

    els.cardsContainer.innerHTML = "";

    const defs = [
        { id: "metadata", label: "Metadata" },
        { id: "noise", label: "Noise Analysis" },
        { id: "compression", label: "Compression" }
    ];

    defs.forEach(d => {
        const res = az[d.id];
        if (!res) return;

        const el = document.createElement("div");
        el.className = "glass-widget";
        el.style.position = "static";
        el.style.transform = "none";
        el.style.animation = "none";

        let status = "Clear";
        let col = "var(--success)";
        if (res.score > 50) { status = "Anomalies"; col = "var(--danger)"; }

        el.innerHTML = `
            <span class="gw-label">${d.label}</span>
            <div class="gw-value-lg" style="color: ${col}; font-size: 1.2rem;">${res.score}%</div>
            <div style="font-size: 0.8rem; color: #888; margin-top: 4px;">${status}</div>
        `;
        els.cardsContainer.appendChild(el);
    });

    if (az.ela && az.ela.ela_image) {
        els.elaOrig.src = fileBlob;
        els.elaRes.src = az.ela.ela_image;
        els.elaViewer.classList.remove("hidden");
    } else {
        els.elaViewer.classList.add("hidden");
    }

    showState("results");
}

function showState(s) {
    els.landing.style.display = (s === "landing") ? "flex" : "none";
    els.analyzing.classList.toggle("hidden", s !== "analyzing");
    els.results.classList.toggle("hidden", s !== "results");
}

function resetUI() {
    els.fileInput.value = "";
    if (els.progressBar) els.progressBar.style.width = "0%";
    if (els.analyzingText) els.analyzingText.textContent = "Initiating Core Scan...";
    showState("landing");
}
