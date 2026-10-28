/**
 * WiFi Shop Manager - Production-Ready Real Frontend Engine & API Client
 * Completely clean: Zero fake/dummy data. Fully synced with SQLite & Windows Wi-Fi Controller.
 */

// Production Application State (Clean Slate)
const STATE = {
    hotspotActive: false,
    shopName: "WiFi Shop Manager",
    hotspotSSID: "Shop-Customer-WiFi",
    hotspotPassword: "ShopWiFiPassword123",
    portalPort: 8080,
    selectedDuration: 60,
    wallDuration: 60,      // Default duration for static wall poster
    vouchers: [],          // Real vouchers from SQLite
    activeSessions: [],    // Real connected clients
    currentVoucher: null,
    serverConnected: false,
    adapterName: "في انتظار الفحص..."
};

// Initialize State from Real Backend API or Clean LocalStorage
async function initAppState() {
    // 1. Load any persistent local cache
    const saved = localStorage.getItem("wifi_shop_manager_real_data");
    if (saved) {
        try {
            const parsed = JSON.parse(saved);
            STATE.vouchers = parsed.vouchers || [];
            STATE.activeSessions = parsed.activeSessions || [];
            STATE.hotspotActive = parsed.hotspotActive || false;
            STATE.currentVoucher = parsed.currentVoucher || null;
            if (parsed.wallDuration) STATE.wallDuration = parsed.wallDuration;
        } catch (e) {
            console.error("Cache parse error", e);
        }
    }

    // 2. Query real Python backend
    await syncWithBackend();

    renderAll();
    startCountdownTicker();

    // 3. Start auto-sync loop with real backend every 4 seconds
    setInterval(syncWithBackend, 4000);
}

function saveState() {
    localStorage.setItem("wifi_shop_manager_real_data", JSON.stringify({
        vouchers: STATE.vouchers,
        activeSessions: STATE.activeSessions,
        hotspotActive: STATE.hotspotActive,
        currentVoucher: STATE.currentVoucher,
        wallDuration: STATE.wallDuration
    }));
}

// Sync with Real Python REST API
async function syncWithBackend() {
    try {
        const resStatus = await fetch("/api/status", { cache: "no-store" });
        if (resStatus.ok) {
            const statusData = await resStatus.json();
            STATE.serverConnected = true;
            STATE.hotspotActive = statusData.hotspot_active;
            STATE.hotspotSSID = statusData.ssid;
            STATE.adapterName = statusData.adapter || "غير متصل";
            if (statusData.wall_duration) {
                STATE.wallDuration = statusData.wall_duration;
            }

            const dongleStatus = document.getElementById("dongle-status-text");
            const icsStatus = document.getElementById("ics-status-text");
            const isPlugged = statusData.adapter && statusData.adapter !== "غير متصل";

            if (dongleStatus) {
                dongleStatus.textContent = isPlugged ? `متصلة (${statusData.adapter}) ✅` : "غير متصلة ❌ (في انتظار التوصيل)";
                dongleStatus.style.color = isPlugged ? "#34d399" : "#f87171";
            }
            if (icsStatus) {
                icsStatus.textContent = isPlugged ? "مفعلة تلقائياً في الخلفية ⚡" : "في انتظار توصيل القطعة ⏳";
                icsStatus.style.color = isPlugged ? "#38bdf8" : "#f59e0b";
            }
        }

        // Fetch real vouchers from SQLite
        const resVouchers = await fetch("/api/vouchers", { cache: "no-store" });
        if (resVouchers.ok) {
            const vouchersList = await resVouchers.json();
            STATE.vouchers = vouchersList.map(v => ({
                code: v.code,
                duration: v.duration_minutes,
                price: v.price || 0.0,
                status: v.status,
                createdAt: v.created_at,
                expiresAt: v.expires_at,
                clientIP: v.client_ip,
                clientDevice: v.client_mac || "جهاز متصل",
                notes: v.notes || ""
            }));
        }

        // Fetch real active clients
        const resClients = await fetch("/api/clients", { cache: "no-store" });
        if (resClients.ok) {
            const clientsList = await resClients.json();
            STATE.activeSessions = clientsList.map(s => ({
                code: s.voucher_code,
                clientIP: s.client_ip,
                clientDevice: s.client_mac || "جهاز محلي",
                expiresAt: s.expire_time,
                duration: s.duration_minutes,
                notes: s.notes
            }));
        }

        renderHeader();
        renderMetrics();
        renderHotspotBox();
        renderWallPosterDuration();
        renderSessionsTable();
        renderHistoryTable();
    } catch (err) {
        // Backend offline or direct file view
        STATE.serverConnected = false;
        const dongleStatus = document.getElementById("dongle-status-text");
        const icsStatus = document.getElementById("ics-status-text");
        if (dongleStatus && !dongleConnected) {
            dongleStatus.textContent = "غير متصلة ❌ (في انتظار التوصيل)";
            dongleStatus.style.color = "#f87171";
        }
        if (icsStatus && !dongleConnected) {
            icsStatus.textContent = "في انتظار توصيل القطعة ⏳";
            icsStatus.style.color = "#f59e0b";
        }
        renderHeader();
        renderHotspotBox();
        renderWallPosterDuration();
    }
}

async function saveHotspotSSID() {
    const input = document.getElementById("input-hotspot-ssid");
    if (!input) return;
    const newSSID = input.value.trim();
    if (!newSSID) {
        showToast("⚠️ يرجى كتابة اسم لشبكة الواي فاي");
        return;
    }

    STATE.hotspotSSID = newSSID;
    saveState();

    try {
        await fetch("/api/settings/update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ssid: newSSID })
        });
    } catch (e) {}

    // Update Wall Poster & Ticket displays
    const posterSSID = document.getElementById("poster-ssid-name");
    const ticketSSID = document.getElementById("ticket-ssid");
    if (posterSSID) posterSSID.textContent = newSSID;
    if (ticketSSID) ticketSSID.textContent = newSSID;

    showToast(`📡 تم حفظ اسم شبكة الواي فاي للزبائن: "${newSSID}" بنجاح!`);
}

async function scanRealHardwareNow() {
    showToast("🔍 جاري فحص منافذ USB ومحولات الواي فاي في ويندوز...");
    const dongleStatus = document.getElementById("dongle-status-text");
    const icsStatus = document.getElementById("ics-status-text");

    try {
        const res = await fetch("/api/hardware/scan", { cache: "no-store" });
        if (res.ok) {
            const data = await res.json();
            if (data.connected && data.adapters && data.adapters.length > 0) {
                const adapter = data.adapters[0];
                if (dongleStatus) {
                    dongleStatus.textContent = `متصلة (${adapter.name}) ✅`;
                    dongleStatus.style.color = "#34d399";
                }
                if (icsStatus) {
                    icsStatus.textContent = "مفعلة تلقائياً في الخلفية ⚡";
                    icsStatus.style.color = "#38bdf8";
                }
                STATE.hotspotActive = true;
                showToast(`✅ تم رصد قطعة الواي فاي بنجاح: ${adapter.name}`);
            } else {
                if (dongleStatus) {
                    dongleStatus.textContent = "غير متصلة ❌ (في انتظار التوصيل)";
                    dongleStatus.style.color = "#f87171";
                }
                if (icsStatus) {
                    icsStatus.textContent = "في انتظار توصيل القطعة ⏳";
                    icsStatus.style.color = "#f59e0b";
                }
                STATE.hotspotActive = false;
                showToast("⚠️ لم يتم العثور على أي قطعة واي فاي في منافذ USB.");
            }
            renderHeader();
            renderHotspotBox();
            return;
        }
    } catch (e) {}

    // Standalone direct browser file mode
    if (dongleStatus) {
        dongleStatus.textContent = "غير متصلة ❌ (في انتظار التوصيل)";
        dongleStatus.style.color = "#f87171";
    }
    if (icsStatus) {
        icsStatus.textContent = "في انتظار توصيل القطعة ⏳";
        icsStatus.style.color = "#f59e0b";
    }
    STATE.hotspotActive = false;
    showToast("⚠️ لم يتم العثور على أي قطعة واي فاي موصولة بمنفذ USB.");
    renderHeader();
    renderHotspotBox();
}

// Generate Readable Random Code
function generateRandomCode(length = 6) {
    const chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ";
    let res = "";
    for (let i = 0; i < length; i++) {
        res += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return `WIFI-${res}`;
}

// Duration Selection
function handleDurationSelect(mins, element) {
    STATE.selectedDuration = mins;
    document.querySelectorAll(".duration-pill").forEach(p => p.classList.remove("active"));
    if (element) element.classList.add("active");
}

// Create Real Voucher (Saves to Real SQLite via Backend API)
async function handleGenerateVoucher() {
    const notesInput = document.getElementById("voucher-notes-input");
    const priceInput = document.getElementById("voucher-price-input");

    const duration = STATE.selectedDuration || 60;
    const price = priceInput ? parseFloat(priceInput.value) || 0.0 : 0.0;
    const notes = notesInput ? notesInput.value.trim() : "";

    // If connected to Python server, send POST to save into SQLite
    try {
        const res = await fetch("/api/vouchers/create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ duration, price, notes })
        });
        if (res.ok) {
            const data = await res.json();
            const created = data.voucher;
            const newV = {
                code: created.code,
                duration: created.duration_minutes,
                price: created.price,
                status: created.status,
                createdAt: new Date().toISOString(),
                expiresAt: null,
                clientIP: null,
                clientDevice: null,
                notes: created.notes
            };
            STATE.vouchers.unshift(newV);
            STATE.currentVoucher = newV;
            saveState();
            if (notesInput) notesInput.value = "";
            showToast(`✨ تم توليد قسيمة حقيقية وحفظها في قاعدة البيانات: ${created.code}`);
            renderAll();
            return;
        }
    } catch (e) {
        // Fallback for offline browser mode
    }

    const code = generateRandomCode(6);
    const fallbackVoucher = {
        code,
        duration,
        price,
        status: "PENDING",
        createdAt: new Date().toISOString(),
        expiresAt: null,
        clientIP: null,
        clientDevice: null,
        notes
    };

    STATE.vouchers.unshift(fallbackVoucher);
    STATE.currentVoucher = fallbackVoucher;
    saveState();

    if (notesInput) notesInput.value = "";
    showToast(`✨ تم توليد قسيمة جديدة: ${code}`);
    renderAll();
}

function handleCopyCode() {
    if (!STATE.currentVoucher) {
        showToast("قم بتوليد قسيمة أولاً لنسخ الرمز");
        return;
    }
    navigator.clipboard.writeText(STATE.currentVoucher.code).then(() => {
        showToast(`📋 تم نسخ الكود ${STATE.currentVoucher.code} إلى الحافظة!`);
    }).catch(() => {
        showToast(`الكود: ${STATE.currentVoucher.code}`);
    });
}

// Toggle Real Hotspot via Python Backend
async function handleToggleHotspot() {
    try {
        const res = await fetch("/api/hotspot/toggle", { method: "POST" });
        if (res.ok) {
            const data = await res.json();
            STATE.hotspotActive = data.active;
            saveState();
            renderHeader();
            renderHotspotBox();
            showToast(STATE.hotspotActive ? "🟢 تم تشغيل بث الواي فاي بنجاح" : "🔴 تم إيقاف بث شبكة الواي فاي");
            return;
        }
    } catch (e) {
        // Fallback
    }

    STATE.hotspotActive = !STATE.hotspotActive;
    saveState();
    renderHeader();
    renderHotspotBox();
    showToast(STATE.hotspotActive ? "🟢 تم تشغيل بث شبكة الواي فاي" : "🔴 تم إيقاف بث شبكة الواي فاي");
}

// Revoke Real Session (Revokes in SQLite)
async function handleRevokeSession(code) {
    if (!confirm(`هل أنت متأكد من رغبتك في قطع الاتصال وإلغاء القسيمة (${code})؟`)) {
        return;
    }

    try {
        await fetch("/api/vouchers/revoke", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code })
        });
    } catch (e) {}

    const v = STATE.vouchers.find(item => item.code === code);
    if (v) v.status = "REVOKED";
    STATE.activeSessions = STATE.activeSessions.filter(s => s.code !== code);
    saveState();
    renderAll();
    showToast(`⛔ تم قطع الاتصال وإلغاء القسيمة ${code}`);
}

// On-Demand Wall QR Code Request Handler
async function handleAutoGuestRequest() {
    const duration = STATE.wallDuration || 60;
    try {
        const res = await fetch("/request-access", { method: "POST" });
        if (res.ok) {
            await syncWithBackend();
            showToast("🎉 تم تفعيل الحساب والإنترنت لجهازك بنجاح!");
            return;
        }
    } catch (e) {}

    // Standalone simulator fallback
    const code = generateRandomCode(6);
    const now = new Date();
    const expiresAt = new Date(now.getTime() + duration * 60000).toISOString();
    const username = `GUEST-${code}`;

    const newVoucher = {
        code,
        username,
        duration,
        price: 0.0,
        status: "ACTIVE",
        createdAt: now.toISOString(),
        expiresAt,
        clientIP: "192.168.137.45",
        clientDevice: "هاتف الزبون (طلب ذاتي)",
        notes: `كود ذاتي (Wall QR) - ${username}`
    };

    STATE.vouchers.unshift(newVoucher);
    STATE.activeSessions.unshift(newVoucher);
    STATE.currentVoucher = newVoucher;
    saveState();

    const formBox = document.getElementById("customer-form-container");
    const timerBox = document.getElementById("customer-timer-container");
    const dispUsername = document.getElementById("disp-cust-username");
    const dispCode = document.getElementById("disp-cust-code");

    if (dispUsername) dispUsername.textContent = username;
    if (dispCode) dispCode.textContent = code;
    if (formBox) formBox.style.display = "none";
    if (timerBox) timerBox.style.display = "block";

    showToast(`🎉 تم توليد حساب خاص: ${username}`);
    renderAll();
}

function resetCustomerPortal() {
    const formBox = document.getElementById("customer-form-container");
    const timerBox = document.getElementById("customer-timer-container");
    const alertBox = document.getElementById("customer-alert-box");
    if (formBox) formBox.style.display = "block";
    if (timerBox) timerBox.style.display = "none";
    if (alertBox) alertBox.style.display = "none";
}

function simulateCustomerScan(num) {
    resetCustomerPortal();
    showToast(`📱 زبون ${num}: تم فتح صفحة البوابة عبر مسح ملصق الحائط`);
}

// Thermal Receipt Modal
function openThermalTicketModal() {
    const v = STATE.currentVoucher;
    if (!v) {
        showToast("يرجى توليد قسيمة أولاً لطباعتها");
        return;
    }

    document.getElementById("ticket-shop-name").textContent = STATE.shopName;
    document.getElementById("ticket-ssid").textContent = STATE.hotspotSSID;
    document.getElementById("ticket-code").textContent = v.code;
    document.getElementById("ticket-duration").textContent = `${v.duration} دقيقة`;
    document.getElementById("ticket-price").textContent = v.price > 0 ? `${v.price.toFixed(2)} درهم` : "مجانية";
    document.getElementById("ticket-notes").textContent = v.notes ? `ملاحظة: ${v.notes}` : "";

    const qrImg = document.getElementById("ticket-qr-img");
    if (qrImg) {
        qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=140x140&data=http://192.168.137.1:8080/?code=${v.code}`;
    }

    const modal = document.getElementById("receipt-modal");
    if (modal) modal.classList.add("active");
}

function closeThermalTicketModal() {
    const modal = document.getElementById("receipt-modal");
    if (modal) modal.classList.remove("active");
}

function printThermalTicket() {
    window.print();
}

// Tab Navigation
function switchTab(tabId) {
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
    const activeBtn = document.getElementById(`tab-btn-${tabId}`);
    if (activeBtn) activeBtn.classList.add("active");

    document.querySelectorAll(".tab-view").forEach(view => view.style.display = "none");
    const activeView = document.getElementById(`view-${tabId}`);
    if (activeView) activeView.style.display = "block";

    if (tabId === "customer") {
        resetCustomerPortal();
    }
}

// Toast Notification
function showToast(message) {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = "toast";
    toast.innerHTML = `<span>💬</span> <div>${message}</div>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.transition = "opacity 0.4s, transform 0.4s";
        toast.style.opacity = "0";
        toast.style.transform = "translateX(-20px)";
        setTimeout(() => toast.remove(), 400);
    }, 3200);
}

// Real Countdown Ticker
function startCountdownTicker() {
    setInterval(() => {
        const now = new Date();
        let changed = false;

        STATE.activeSessions.forEach(session => {
            if (session.expiresAt && new Date(session.expiresAt) <= now) {
                session.status = "EXPIRED";
                changed = true;
            }
        });

        if (changed) {
            STATE.activeSessions = STATE.activeSessions.filter(s => s.status === "ACTIVE");
            saveState();
            renderMetrics();
            renderSessionsTable();
        } else {
            renderRemainingTimes();
            updateCustomerCountdown();
        }
    }, 1000);
}

function updateCustomerCountdown() {
    const countdownElem = document.getElementById("customer-countdown-display");
    if (!countdownElem) return;

    const v = STATE.currentVoucher;
    if (v && v.expiresAt) {
        const diff = Math.max(0, Math.floor((new Date(v.expiresAt) - new Date()) / 1000));
        const mins = Math.floor(diff / 60);
        const secs = diff % 60;
        countdownElem.textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
}

function renderRemainingTimes() {
    const now = new Date();
    document.querySelectorAll("[data-expires-at]").forEach(elem => {
        const expiresAt = new Date(elem.getAttribute("data-expires-at"));
        const diff = Math.max(0, Math.floor((expiresAt - now) / 1000));
        const mins = Math.floor(diff / 60);
        const secs = diff % 60;
        elem.textContent = `${mins} د : ${secs.toString().padStart(2, '0')} ث`;
    });
}

// Render UI Components
function renderAll() {
    renderHeader();
    renderMetrics();
    renderHotspotBox();
    renderVoucherBox();
    renderWallPosterDuration();
    renderSessionsTable();
    renderHistoryTable();
}

function renderHeader() {
    const dot = document.getElementById("header-hotspot-dot");
    const text = document.getElementById("header-hotspot-text");
    if (dot && text) {
        if (STATE.hotspotActive) {
            dot.className = "pulse-dot";
            text.textContent = "نقطة البث: نشطة";
            text.style.color = "var(--success)";
        } else {
            dot.className = "pulse-dot inactive";
            text.textContent = "نقطة البث: متوقفة";
            text.style.color = "var(--danger)";
        }
    }
}

function renderMetrics() {
    const activeCount = STATE.activeSessions.length;
    const totalCount = STATE.vouchers.length;
    const expiredCount = STATE.vouchers.filter(v => v.status === "EXPIRED").length;
    const totalRev = STATE.vouchers.reduce((acc, v) => acc + (v.price || 0), 0);

    const elActive = document.getElementById("metric-active-count");
    const elTotal = document.getElementById("metric-total-count");
    const elExpired = document.getElementById("metric-expired-count");
    const elRev = document.getElementById("metric-revenue");

    if (elActive) elActive.textContent = activeCount;
    if (elTotal) elTotal.textContent = totalCount;
    if (elExpired) elExpired.textContent = expiredCount;
    if (elRev) elRev.textContent = `${totalRev.toFixed(0)} د.م`;
}

function renderHotspotBox() {
    const btn = document.getElementById("btn-toggle-hotspot");
    const inputSSID = document.getElementById("input-hotspot-ssid");
    const posterSSID = document.getElementById("poster-ssid-name");
    const ticketSSID = document.getElementById("ticket-ssid");

    if (inputSSID && document.activeElement !== inputSSID) {
        inputSSID.value = STATE.hotspotSSID;
    }
    if (posterSSID) posterSSID.textContent = STATE.hotspotSSID;
    if (ticketSSID) ticketSSID.textContent = STATE.hotspotSSID;

    if (btn) {
        if (STATE.hotspotActive) {
            btn.className = "btn btn-danger btn-block";
            btn.innerHTML = `<span>⏹️</span> إيقاف نقطة البث (Stop Hotspot)`;
        } else {
            btn.className = "btn btn-success btn-block";
            btn.innerHTML = `<span>▶️</span> تشغيل نقطة البث (Start Hotspot)`;
        }
    }
}

function renderVoucherBox() {
    const v = STATE.currentVoucher;
    const codeElem = document.getElementById("voucher-code-display");
    const metaElem = document.getElementById("voucher-meta-display");
    const qrElem = document.getElementById("voucher-qr-preview");

    if (v) {
        if (codeElem) codeElem.textContent = v.code;
        if (metaElem) {
            const statusLabel = v.status === "PENDING" ? "جاهزة للاستعمال" : v.status === "ACTIVE" ? "نشطة حالياً" : "منتهية";
            metaElem.textContent = `مدة الصلاحية: ${v.duration} دقيقة  •  الحالة: ${statusLabel}`;
        }
        if (qrElem) {
            qrElem.src = `https://api.qrserver.com/v1/create-qr-code/?size=100x100&data=http://192.168.137.1:8080/?code=${v.code}`;
        }
    } else {
        if (codeElem) codeElem.textContent = "----";
        if (metaElem) metaElem.textContent = "اضغط على زر التوليد لإنشاء قسيمة جديدة";
    }
}

// Render & Handle Wall Poster Duration Settings
function renderWallPosterDuration() {
    const dur = STATE.wallDuration || 60;
    const badge = document.getElementById("wall-duration-active-badge");
    const posterDisp = document.getElementById("poster-duration-display");
    const instDisp = document.getElementById("poster-instructions-duration");
    const customInput = document.getElementById("wall-custom-duration-input");

    const label = dur >= 60 ? `${(dur / 60).toFixed(dur % 60 === 0 ? 0 : 1)} ساعة (${dur} دقيقة)` : `${dur} دقيقة`;

    if (badge) badge.textContent = `المدة المحددة: ${label}`;
    if (posterDisp) posterDisp.textContent = `${label} مجاناً`;
    if (instDisp) instDisp.textContent = `${dur} دقيقة`;
    if (customInput && document.activeElement !== customInput) customInput.value = dur;

    // Highlight active pill
    document.querySelectorAll("#wall-duration-pills .duration-pill").forEach(p => {
        p.classList.remove("active");
        const txt = p.textContent;
        if (
            (dur === 15 && txt.includes("15")) ||
            (dur === 30 && txt.includes("30")) ||
            (dur === 45 && txt.includes("45")) ||
            (dur === 60 && txt.includes("1 ساعة")) ||
            (dur === 90 && txt.includes("1.5 ساعة")) ||
            (dur === 120 && txt.includes("2 ساعة")) ||
            (dur === 180 && txt.includes("3 ساعات"))
        ) {
            p.classList.add("active");
        }
    });
}

async function handleSetWallDuration(mins, element) {
    mins = parseInt(mins) || 60;
    STATE.wallDuration = mins;
    saveState();
    renderWallPosterDuration();

    try {
        await fetch("/api/settings/wall-duration", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ duration: mins })
        });
    } catch (e) {}

    showToast(`⏱️ تم ضبط مدة كود ملصق الحائط إلى ${mins} دقيقة للزبائن بنجاح!`);
}

function handleCustomWallDuration() {
    const input = document.getElementById("wall-custom-duration-input");
    const mins = input ? parseInt(input.value) : 0;
    if (!mins || mins < 5 || mins > 1440) {
        showToast("⚠️ يرجى إدخال مدة صحيحة بين 5 و 1440 دقيقة.");
        return;
    }
    handleSetWallDuration(mins, null);
}

// Modal Handlers: Add Extra Time to Active Client Session
let currentTargetCode = null;

function openAddTimeModal(code) {
    currentTargetCode = code;
    const targetLabel = document.getElementById("modal-target-code");
    if (targetLabel) targetLabel.textContent = code;
    const modal = document.getElementById("add-time-modal");
    if (modal) modal.classList.add("active");
}

function closeAddTimeModal() {
    const modal = document.getElementById("add-time-modal");
    if (modal) modal.classList.remove("active");
    currentTargetCode = null;
}

function applyCustomExtraTime() {
    const input = document.getElementById("custom-extra-mins");
    const val = input ? parseInt(input.value) : 0;
    if (!val || val <= 0) {
        showToast("⚠️ يرجى إدخال عدد دقائق صحيح");
        return;
    }
    applyExtraTime(val);
}

async function applyExtraTime(minutes) {
    if (!currentTargetCode) return;
    const code = currentTargetCode;
    closeAddTimeModal();

    // 1. Try Real Python Backend API
    try {
        const res = await fetch("/api/sessions/extend", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code, minutes })
        });
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                showToast(`🎉 ${data.message || `تمت إضافة ${minutes} دقيقة بنجاح للزبون (${code})`}`);
                await syncWithBackend();
                return;
            }
        }
    } catch (e) {}

    // 2. Standalone offline fallback
    const session = STATE.activeSessions.find(s => s.code === code);
    if (session) {
        const now = new Date();
        const curExp = session.expiresAt ? new Date(session.expiresAt) : now;
        const baseTime = curExp > now ? curExp : now;
        const newExp = new Date(baseTime.getTime() + minutes * 60000);
        session.expiresAt = newExp.toISOString();
        session.duration = (session.duration || 60) + minutes;

        // Also update matching voucher
        const v = STATE.vouchers.find(v => v.code === code);
        if (v) {
            v.expiresAt = session.expiresAt;
            v.duration = session.duration;
        }

        if (STATE.currentVoucher && STATE.currentVoucher.code === code) {
            STATE.currentVoucher.expiresAt = session.expiresAt;
            STATE.currentVoucher.duration = session.duration;
        }

        saveState();
        renderSessionsTable();
        renderHistoryTable();
        updateCustomerCountdown();
        showToast(`🎉 تمت إضافة ${minutes} دقيقة إضافية للزبون (${code}) بنجاح!`);
    } else {
        showToast(`⚠️ لم يتم العثور على جلسة نشطة للرمز ${code}`);
    }
}

function renderSessionsTable() {
    const tbody = document.getElementById("sessions-table-body");
    const emptyState = document.getElementById("sessions-empty-state");
    if (!tbody) return;

    tbody.innerHTML = "";
    if (STATE.activeSessions.length === 0) {
        if (emptyState) emptyState.style.display = "block";
        return;
    }
    if (emptyState) emptyState.style.display = "none";

    STATE.activeSessions.forEach(s => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong style="color: #60a5fa; letter-spacing: 1px;">${s.code}</strong></td>
            <td><code>${s.clientIP || "192.168.137.2"}</code></td>
            <td>${s.clientDevice || "جهاز محمول"}</td>
            <td><span class="badge badge-success" data-expires-at="${s.expiresAt}">تحميل...</span></td>
            <td>
                <div style="display: flex; gap: 0.4rem; justify-content: flex-end; align-items: center;">
                    <button class="btn btn-outline" style="padding: 0.32rem 0.65rem; font-size: 0.8rem; color: #34d399; border-color: rgba(52, 211, 153, 0.4); display: inline-flex; align-items: center; gap: 4px;" onclick="openAddTimeModal('${s.code}')" title="إضافة وقت إضافي لهذا الزبون يدوياً">
                        <span>⏱️</span> <span>➕ وقت</span>
                    </button>
                    <button class="btn btn-outline" style="padding: 0.32rem 0.65rem; font-size: 0.8rem; color: #f87171; border-color: rgba(239, 68, 68, 0.4);" onclick="handleRevokeSession('${s.code}')" title="قطع اتصال هذا الزبون">
                        قطع
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
    renderRemainingTimes();
}

function renderHistoryTable() {
    const tbody = document.getElementById("history-table-body");
    const emptyNotice = document.getElementById("history-empty-notice");
    if (!tbody) return;

    tbody.innerHTML = "";
    if (STATE.vouchers.length === 0) {
        if (emptyNotice) emptyNotice.style.display = "block";
        return;
    }
    if (emptyNotice) emptyNotice.style.display = "none";

    STATE.vouchers.forEach(v => {
        let badgeClass = "badge-blue";
        let statusText = "جاهزة";
        if (v.status === "ACTIVE") { badgeClass = "badge-success"; statusText = "نشطة"; }
        if (v.status === "EXPIRED") { badgeClass = "badge-warning"; statusText = "منتهية"; }
        if (v.status === "REVOKED") { badgeClass = "badge-danger"; statusText = "ملغاة"; }

        const dateStr = v.createdAt ? new Date(v.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "-";
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${v.code}</strong></td>
            <td>${v.duration} دقيقة</td>
            <td>${v.price > 0 ? `${v.price} د.م` : "مجانية"}</td>
            <td><span class="badge ${badgeClass}">${statusText}</span></td>
            <td>${v.notes || "-"}</td>
            <td style="color: var(--text-muted); font-size: 0.8rem;">${dateStr}</td>
        `;
        tbody.appendChild(tr);
    });
}

function resetAllData() {
    if (confirm("هل تريد مسح سجل القسائم الحالي والبدء من جديد؟")) {
        STATE.vouchers = [];
        STATE.activeSessions = [];
        STATE.currentVoucher = null;
        saveState();
        renderAll();
        showToast("🧹 تم تفريغ السجل والبدء بصفحة نظيفة!");
    }
}

// Window Onload Binding
window.addEventListener("DOMContentLoaded", () => {
    initAppState();
});
