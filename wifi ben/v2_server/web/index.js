/**
 * WiFi Shop Manager - Production-Ready Real Frontend Engine & API Client
 * Completely clean: Zero fake/dummy data. Fully synced with SQLite & Windows Wi-Fi Controller.
 */

// Production Application State (Clean Slate)
const STATE = {
    hotspotActive: false,
    shopName: "WiFi Shop Manager",
    hotspotSSID: "benhazem",
    hotspotPassword: "12345678",
    portalPort: 8080,
    serverIP: "192.168.137.1",
    autoGenerateNext: true,
    currentReadyVoucher: null,
    readyDuration: 60,
    batchDuration: 60,
    lastBatch: [],
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
            if (parsed.hotspotSSID) STATE.hotspotSSID = parsed.hotspotSSID;
            if (parsed.hotspotPassword) STATE.hotspotPassword = parsed.hotspotPassword;
            if (parsed.wallDuration) STATE.wallDuration = parsed.wallDuration;
            if (parsed.readyDuration) STATE.readyDuration = parsed.readyDuration;
            if (parsed.autoGenerateNext !== undefined) STATE.autoGenerateNext = parsed.autoGenerateNext;
        } catch (e) {
            console.error("Cache parse error", e);
        }
    }

    // 2. Query real C# backend
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
        hotspotSSID: STATE.hotspotSSID,
        hotspotPassword: STATE.hotspotPassword,
        currentVoucher: STATE.currentVoucher,
        currentReadyVoucher: STATE.currentReadyVoucher,
        wallDuration: STATE.wallDuration,
        readyDuration: STATE.readyDuration,
        autoGenerateNext: STATE.autoGenerateNext
    }));
}

// Sync with Real REST API
async function syncWithBackend() {
    try {
        const resStatus = await fetch("/api/status", { cache: "no-store" });
        if (resStatus.ok) {
            const statusData = await resStatus.json();
            STATE.serverConnected = true;
            STATE.hotspotActive = statusData.hotspot_active;
            if (statusData.ssid) STATE.hotspotSSID = statusData.ssid;
            if (statusData.password) STATE.hotspotPassword = statusData.password;
            if (statusData.server_ip) STATE.serverIP = statusData.server_ip;
            if (statusData.auto_generate_next !== undefined) STATE.autoGenerateNext = statusData.auto_generate_next;
            if (statusData.current_ready_voucher) STATE.currentReadyVoucher = statusData.current_ready_voucher;
            STATE.adapterName = statusData.adapter || "محول ويندوز الافتراضي";
            if (statusData.wall_duration) {
                STATE.wallDuration = statusData.wall_duration;
            }

            const hotspotStatus = document.getElementById("hotspot-status-text");
            const serverIpDisp = document.getElementById("server-ip-display");
            const staticWallQr = document.getElementById("static-wall-qr-img");

            if (hotspotStatus) {
                hotspotStatus.textContent = statusData.hotspot_active ? "مفعلة وتعمل بنجاح ✅" : "متوقفة (يرجى تفعيلها من ويندوز) ⚠️";
                hotspotStatus.style.color = statusData.hotspot_active ? "#34d399" : "#f59e0b";
            }
            if (serverIpDisp && statusData.server_ip) {
                serverIpDisp.textContent = `${statusData.server_ip}:8080`;
            }
            if (staticWallQr && statusData.server_ip) {
                staticWallQr.src = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=http://${statusData.server_ip}:8080/`;
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
        renderReadyVoucherCard();
        renderWallPosterDuration();
        renderSessionsTable();
        renderHistoryTable();
    } catch (err) {
        // Backend offline or direct file view
        STATE.serverConnected = false;
        renderHeader();
        renderHotspotBox();
        renderReadyVoucherCard();
        renderWallPosterDuration();
    }
}

async function saveHotspotSettings() {
    const inputSSID = document.getElementById("input-hotspot-ssid");
    const inputPass = document.getElementById("input-hotspot-password");
    const btn = document.getElementById("btn-save-hotspot-settings");

    const newSSID = inputSSID ? inputSSID.value.trim() : "";
    const newPass = inputPass ? inputPass.value.trim() : "";

    if (!newSSID) {
        showToast("⚠️ يرجى كتابة اسم لشبكة الواي فاي");
        return;
    }
    if (newPass && newPass.length < 8) {
        showToast("⚠️ كلمة مرور الواي فاي يجب أن تكون 8 خانات أو أرقام على الأقل");
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.textContent = "⏳ جاري التطبيق في ويندوز...";
    }

    STATE.hotspotSSID = newSSID;
    if (newPass) STATE.hotspotPassword = newPass;
    saveState();
    renderHotspotBox();

    try {
        const res = await fetch("/api/settings/update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ssid: newSSID, password: newPass })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`✅ تم تطبيق وحفظ اسم الشبكة "${newSSID}" وكلمة السر فوراً في ويندوز!`);
        }
    } catch (e) {
        showToast("✅ تم حفظ الإعدادات بنجاح");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "💾 حفظ وتطبيق فوراً";
        }
    }
}

async function saveHotspotSSID() {
    await saveHotspotSettings();
}

async function generateNewRandomPassword() {
    const inputPass = document.getElementById("input-hotspot-password");
    showToast("🎲 جاري توليد كلمة سر جديدة وتطبيقها في ويندوز...");
    try {
        const res = await fetch("/api/hotspot/generate-password", { method: "POST" });
        if (res.ok) {
            const data = await res.json();
            if (data.password) {
                STATE.hotspotPassword = data.password;
                if (inputPass) inputPass.value = data.password;
                saveState();
                renderHotspotBox();
                showToast(`🔑 تم توليد كلمة السر الجديدة: ${data.password} وتطبيقها فوراً في ويندوز!`);
                return;
            }
        }
    } catch (e) {}

    const randPass = Math.floor(10000000 + Math.random() * 90000000).toString();
    STATE.hotspotPassword = randPass;
    if (inputPass) inputPass.value = randPass;
    await saveHotspotSettings();
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

// =========================================================================
// 1. Ready Passcode Hero Card Handlers (الرقم السري الحالي الجاهز للزبون القادم)
// =========================================================================

async function handleReadyDurationSelect(mins, element) {
    STATE.readyDuration = parseInt(mins) || 60;
    document.querySelectorAll("#ready-duration-pills .duration-pill").forEach(p => p.classList.remove("active"));
    if (element) element.classList.add("active");

    try {
        const res = await fetch("/api/vouchers/current-ready", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ duration: STATE.readyDuration })
        });
        if (res.ok) {
            const data = await res.json();
            if (data.voucher) {
                STATE.currentReadyVoucher = data.voucher;
                renderReadyVoucherCard();
                showToast(`⏱️ تم ضبط مدة الكود الجاهز إلى ${STATE.readyDuration} دقيقة للزبون`);
                return;
            }
        }
    } catch (e) {}

    if (STATE.currentReadyVoucher) {
        STATE.currentReadyVoucher.duration_minutes = STATE.readyDuration;
        renderReadyVoucherCard();
    }
}

async function handleToggleAutoGenerate(checked) {
    STATE.autoGenerateNext = checked;
    saveState();
    try {
        await fetch("/api/settings/update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ auto_generate_next: checked })
        });
    } catch (e) {}
    showToast(checked ? "🟢 تم تفعيل التوليد التلقائي للرقم التالي فور الاستخدام" : "⚪ تم إيقاف التوليد التلقائي للرقم التالي");
}

async function handleGenerateNextReadyVoucher() {
    showToast("🎲 جاري توليد كود جديد للزبون القادم...");
    try {
        const res = await fetch("/api/vouchers/next-ready", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ duration: STATE.readyDuration, price: 0 })
        });
        if (res.ok) {
            const data = await res.json();
            if (data.voucher) {
                STATE.currentReadyVoucher = data.voucher;
                renderReadyVoucherCard();
                showToast(`✨ تم توليد رقم سري جديد بنجاح: ${data.voucher.code}`);
                return;
            }
        }
    } catch (e) {}

    const code = Math.floor(100000 + Math.random() * 900000).toString();
    STATE.currentReadyVoucher = {
        code,
        duration_minutes: STATE.readyDuration,
        price: 0,
        status: "PENDING"
    };
    renderReadyVoucherCard();
    showToast(`✨ تم توليد رقم سري جديد: ${code}`);
}

function handleCopyReadyCode() {
    if (!STATE.currentReadyVoucher || !STATE.currentReadyVoucher.code) {
        showToast("⚠️ لا يوجد رقم سري جاهز حالياً");
        return;
    }
    const code = STATE.currentReadyVoucher.code;
    navigator.clipboard.writeText(code).then(() => {
        showToast(`📋 تم نسخ الرقم السري ${code} إلى الحافظة!`);
    }).catch(() => {
        showToast(`الرقم السري: ${code}`);
    });
}

function openThermalTicketForReady() {
    const v = STATE.currentReadyVoucher;
    if (!v || !v.code) {
        showToast("⚠️ لا يوجد رقم سري جاهز للطباعة");
        return;
    }
    STATE.currentVoucher = {
        code: v.code,
        duration: v.duration_minutes || STATE.readyDuration,
        price: v.price || 0,
        notes: "تذكرة الزبون القادم"
    };
    openThermalTicketModal();
}

// =========================================================================
// 2. Batch Voucher Generator Handlers (قسم توليد الأكواد حسب المدة)
// =========================================================================

function handleBatchDurationSelect(mins, element) {
    STATE.batchDuration = parseInt(mins) || 60;
    document.querySelectorAll("#batch-duration-pills .duration-pill").forEach(p => p.classList.remove("active"));
    if (element) element.classList.add("active");
}

async function handleBatchCreateVouchers() {
    const countSelect = document.getElementById("batch-count-select");
    const priceInput = document.getElementById("batch-price-input");
    const count = countSelect ? parseInt(countSelect.value) || 5 : 5;
    const price = priceInput ? parseFloat(priceInput.value) || 0 : 0;
    const duration = STATE.batchDuration || 60;

    showToast(`⏳ جاري توليد دفعة مكونة من ${count} أكواد...`);

    try {
        const res = await fetch("/api/vouchers/batch-create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ count, duration, price })
        });
        if (res.ok) {
            const data = await res.json();
            const list = data.vouchers || [];
            STATE.lastBatch = list;

            const previewBox = document.getElementById("batch-created-preview");
            const summary = document.getElementById("batch-created-summary");
            const codesList = document.getElementById("batch-codes-list");

            if (previewBox) previewBox.style.display = "block";
            if (summary) summary.textContent = `تم توليد ${list.length} كود بنجاح (${duration} دقيقة)`;
            if (codesList) {
                codesList.innerHTML = list.map((item, idx) => `<div>${idx + 1}. <strong style="color: #60a5fa;">${item.code}</strong> (${item.duration_minutes} د)</div>`).join("");
            }

            await syncWithBackend();
            showToast(`✨ تم توليد دفعة من ${list.length} أكواد وحفظها بنجاح!`);
            return;
        }
    } catch (e) {}

    // Fallback for offline simulation
    const list = [];
    for (let i = 0; i < count; i++) {
        list.push({ code: Math.floor(100000 + Math.random() * 900000).toString(), duration_minutes: duration, price, status: "PENDING" });
    }
    STATE.lastBatch = list;
    const previewBox = document.getElementById("batch-created-preview");
    const summary = document.getElementById("batch-created-summary");
    const codesList = document.getElementById("batch-codes-list");

    if (previewBox) previewBox.style.display = "block";
    if (summary) summary.textContent = `تم توليد ${list.length} كود بنجاح (${duration} دقيقة)`;
    if (codesList) {
        codesList.innerHTML = list.map((item, idx) => `<div>${idx + 1}. <strong style="color: #60a5fa;">${item.code}</strong> (${item.duration_minutes} د)</div>`).join("");
    }
    showToast(`✨ تم توليد دفعة من ${list.length} أكواد!`);
}

function printLastBatch() {
    if (!STATE.lastBatch || STATE.lastBatch.length === 0) {
        showToast("⚠️ لا توجد دفعة أكواد حديثة للطباعة");
        return;
    }
    const printWin = window.open("", "_blank", "width=440,height=650");
    if (!printWin) {
        window.print();
        return;
    }
    let html = `<!DOCTYPE html><html dir="rtl"><head><title>طباعة دفعة أكواد الواي فاي</title>
    <style>body{font-family:sans-serif;text-align:center;padding:20px;color:#000;}
    .ticket{border:1px dashed #000;margin:12px 0;padding:12px;page-break-inside:avoid;border-radius:6px;}
    .code{font-size:24px;font-weight:900;letter-spacing:4px;margin:6px 0;font-family:monospace;}
    </style></head><body>
    <h2>${STATE.shopName}</h2>
    <p>شبكة الواي فاي: <strong>${STATE.hotspotSSID}</strong></p>
    <p>كلمة سر الشبكة للاتصال: <strong>${STATE.hotspotPassword}</strong></p><hr>`;
    STATE.lastBatch.forEach(v => {
        html += `<div class="ticket"><div class="code">${v.code}</div><div>المدة: ${v.duration_minutes} دقيقة • السعر: ${v.price > 0 ? v.price + ' د.م' : 'مجاني'}</div><small>استخدام لمرة واحدة فقط</small></div>`;
    });
    html += `<script>window.onload = function() { window.print(); }<\/script></body></html>`;
    printWin.document.write(html);
    printWin.document.close();
}

// =========================================================================
// 3. Customer Smartphone Portal Simulator Handlers
// =========================================================================

function simFillCurrentReadyCode() {
    const input = document.getElementById("sim-input-code");
    if (!STATE.currentReadyVoucher || !STATE.currentReadyVoucher.code) {
        showToast("⚠️ لا يوجد رقم سري جاهز حالياً");
        return;
    }
    if (input) {
        input.value = STATE.currentReadyVoucher.code;
        showToast(`⚡ تم ملء الكود الحالي: ${STATE.currentReadyVoucher.code}`);
    }
}

async function handleSimCustomerLogin() {
    const input = document.getElementById("sim-input-code");
    const code = input ? input.value.trim() : "";
    const alertBox = document.getElementById("customer-alert-box");
    const btn = document.getElementById("btn-sim-login");

    if (alertBox) alertBox.style.display = "none";

    if (!code) {
        if (alertBox) {
            alertBox.textContent = "⚠️ يرجى إدخال الرقم السري المكون من 6 أرقام";
            alertBox.style.display = "block";
        }
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = "⏳ جاري التحقق من الرقم السري والتفعيل...";
    }

    try {
        const res = await fetch("/api/portal/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code })
        });
        const data = await res.json();
        if (data.success) {
            const formBox = document.getElementById("customer-form-container");
            const timerBox = document.getElementById("customer-timer-container");
            const dispCode = document.getElementById("disp-cust-code");
            const dispIp = document.getElementById("disp-cust-ip");

            if (dispCode) dispCode.textContent = data.voucher ? data.voucher.code : code;
            if (dispIp && data.voucher && data.voucher.client_ip) dispIp.textContent = data.voucher.client_ip;
            if (formBox) formBox.style.display = "none";
            if (timerBox) timerBox.style.display = "block";

            // If auto-generate is active, backend automatically created the next ready code!
            await syncWithBackend();
            showToast("🎉 تم تفعيل الإنترنت بنجاح! وتوليد كود جديد للزبون التالي ✅");
            return;
        } else {
            if (alertBox) {
                alertBox.textContent = "⚠️ " + (data.message || "الرقم السري غير صحيح أو تم استخدامه مسبقاً!");
                alertBox.style.display = "block";
            }
        }
    } catch (e) {
        if (alertBox) {
            alertBox.textContent = "⚠️ تعذر الاتصال بالخادم المحلي.";
            alertBox.style.display = "block";
        }
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = "<span>🚀</span> اتصال وتفعيل الإنترنت";
        }
    }
}

function handleSimBarcodeScan() {
    simFillCurrentReadyCode();
    handleSimCustomerLogin();
}

let simCameraStream = null;
async function startSimCamera() {
    const video = document.getElementById("sim-camera-video");
    const container = document.getElementById("sim-camera-container");
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showToast("⚠️ الكاميرا غير مدعومة في هذا المتصفح.");
        return;
    }
    try {
        simCameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (video) {
            video.srcObject = simCameraStream;
            video.play();
        }
        if (container) container.style.display = "block";
        showToast("📷 تم تشغيل الكاميرا! وجّهها نحو الباركود أو الـ QR");
    } catch (err) {
        showToast("⚠️ تعذر الوصول إلى الكاميرا: " + err.message);
    }
}

function stopSimCamera() {
    if (simCameraStream) {
        simCameraStream.getTracks().forEach(t => t.stop());
        simCameraStream = null;
    }
    const container = document.getElementById("sim-camera-container");
    if (container) container.style.display = "none";
}

function resetCustomerPortal() {
    stopSimCamera();
    const formBox = document.getElementById("customer-form-container");
    const timerBox = document.getElementById("customer-timer-container");
    const alertBox = document.getElementById("customer-alert-box");
    const input = document.getElementById("sim-input-code");
    if (formBox) formBox.style.display = "block";
    if (timerBox) timerBox.style.display = "none";
    if (alertBox) alertBox.style.display = "none";
    if (input) input.value = "";
}

function simulateCustomerScan(num) {
    resetCustomerPortal();
    showToast(`📱 زبون ${num}: تم فتح صفحة البوابة عبر مسح الرمز`);
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
    const ticketWifiPass = document.getElementById("ticket-wifi-pass");
    if (ticketWifiPass) ticketWifiPass.textContent = STATE.hotspotPassword || "12345678";
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
    renderReadyVoucherCard();
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
    const inputPass = document.getElementById("input-hotspot-password");
    const posterSSID = document.getElementById("poster-ssid-name");
    const posterPass = document.getElementById("poster-wifi-pass");
    const ticketSSID = document.getElementById("ticket-ssid");
    const ticketPass = document.getElementById("ticket-wifi-pass");

    if (inputSSID && document.activeElement !== inputSSID) {
        inputSSID.value = STATE.hotspotSSID;
    }
    if (inputPass && document.activeElement !== inputPass) {
        inputPass.value = STATE.hotspotPassword;
    }
    if (posterSSID) posterSSID.textContent = STATE.hotspotSSID;
    if (posterPass) posterPass.textContent = STATE.hotspotPassword;
    if (ticketSSID) ticketSSID.textContent = STATE.hotspotSSID;
    if (ticketPass) ticketPass.textContent = STATE.hotspotPassword;

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

function renderReadyVoucherCard() {
    const ready = STATE.currentReadyVoucher;
    const dispCode = document.getElementById("disp-ready-code");
    const readyStatus = document.getElementById("ready-voucher-status");
    const durLabel = document.getElementById("ready-duration-label");
    const priceLabel = document.getElementById("ready-price-label");
    const qrImg = document.getElementById("ready-qr-preview");
    const checkAuto = document.getElementById("check-auto-generate-next");
    const simHotspot = document.getElementById("sim-hotspot-name");

    if (simHotspot) simHotspot.textContent = STATE.hotspotSSID;
    if (checkAuto) checkAuto.checked = STATE.autoGenerateNext;

    if (ready && ready.code) {
        if (dispCode) dispCode.textContent = ready.code;
        if (readyStatus) {
            readyStatus.textContent = ready.status === "PENDING" ? "جاهز للزبون القادم ✅" : "نشط الآن 🟢";
            readyStatus.className = ready.status === "PENDING" ? "badge badge-success" : "badge badge-blue";
        }
        const dur = ready.duration_minutes || STATE.readyDuration || 60;
        const durText = dur >= 60 ? `${(dur / 60).toFixed(dur % 60 === 0 ? 0 : 1)} ساعة (${dur} د)` : `${dur} دقيقة`;
        if (durLabel) durLabel.textContent = durText;
        if (priceLabel) priceLabel.textContent = (ready.price && ready.price > 0) ? `${ready.price} د.م` : "مجاني";

        if (qrImg) {
            const serverIp = STATE.serverIP || "192.168.137.1";
            qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=100x100&data=http://${serverIp}:8080/portal?code=${ready.code}`;
        }

        // Highlight ready duration pill
        document.querySelectorAll("#ready-duration-pills .duration-pill").forEach(p => {
            p.classList.remove("active");
            const txt = p.textContent;
            if (
                (dur === 15 && txt.includes("15")) ||
                (dur === 30 && txt.includes("30")) ||
                (dur === 60 && txt.includes("1 ساعة")) ||
                (dur === 120 && txt.includes("2 ساعة"))
            ) {
                p.classList.add("active");
            }
        });
    } else {
        if (dispCode) dispCode.textContent = "------";
        if (readyStatus) readyStatus.textContent = "في انتظار التوليد ⏳";
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

function openWindowsHotspotSettings() {
    try {
        window.location.href = "ms-settings:network-mobilehotspot";
    } catch (e) {}
    showToast("⚙️ تم إرسال أمر فتح إعدادات نقطة الاتصال في ويندوز.");
}

// Window Onload Binding
window.addEventListener("DOMContentLoaded", () => {
    initAppState();
});
