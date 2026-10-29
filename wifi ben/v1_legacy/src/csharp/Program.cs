using System;
using System.IO;
using System.Text;
using System.Net;
using System.Threading;
using System.Diagnostics;
using System.Collections.Generic;
using System.Security.Principal;
using System.Windows.Forms;
using System.Drawing;
using System.Web.Script.Serialization;

namespace WiFiShopManager
{
    public class VoucherItem
    {
        public string code { get; set; }
        public string username { get; set; }
        public int duration_minutes { get; set; }
        public double price { get; set; }
        public string status { get; set; } // PENDING, ACTIVE, EXPIRED, REVOKED
        public string created_at { get; set; }
        public string expires_at { get; set; }
        public string client_ip { get; set; }
        public string client_mac { get; set; }
        public string notes { get; set; }
    }

    public class AppSettings
    {
        public string shop_name { get; set; }
        public string hotspot_ssid { get; set; }
        public string hotspot_password { get; set; }
        public int default_duration_minutes { get; set; }
        public int portal_port { get; set; }

        public AppSettings()
        {
            shop_name = "WiFi Shop Manager";
            hotspot_ssid = "Shop-Customer-WiFi";
            hotspot_password = "ShopWiFiPassword123";
            default_duration_minutes = 60;
            portal_port = 8080;
        }
    }

    public class AppState
    {
        private static readonly object _lock = new object();
        public static AppSettings Settings = new AppSettings();
        public static List<VoucherItem> Vouchers = new List<VoucherItem>();
        public static bool HotspotActive = false;
        public static string DetectedAdapter = "غير متصل";
        public static string BaseDirectory = AppDomain.CurrentDomain.BaseDirectory;

        private static string SettingsFilePath { get { return Path.Combine(BaseDirectory, "config.json"); } }
        private static string VouchersFilePath { get { return Path.Combine(BaseDirectory, "vouchers.json"); } }
        private static JavaScriptSerializer _json = new JavaScriptSerializer();

        public static void Load()
        {
            lock (_lock)
            {
                try
                {
                    if (File.Exists(SettingsFilePath))
                    {
                        string json = File.ReadAllText(SettingsFilePath, Encoding.UTF8);
                        Settings = _json.Deserialize<AppSettings>(json) ?? new AppSettings();
                    }
                }
                catch { }

                try
                {
                    if (File.Exists(VouchersFilePath))
                    {
                        string json = File.ReadAllText(VouchersFilePath, Encoding.UTF8);
                        Vouchers = _json.Deserialize<List<VoucherItem>>(json) ?? new List<VoucherItem>();
                    }
                }
                catch { }
            }
        }

        public static void Save()
        {
            lock (_lock)
            {
                try
                {
                    File.WriteAllText(SettingsFilePath, _json.Serialize(Settings), Encoding.UTF8);
                    File.WriteAllText(VouchersFilePath, _json.Serialize(Vouchers), Encoding.UTF8);
                }
                catch { }
            }
        }

        public static void CheckExpirations()
        {
            lock (_lock)
            {
                DateTime now = DateTime.Now;
                bool changed = false;
                foreach (var v in Vouchers)
                {
                    if (v.status == "ACTIVE" && !string.IsNullOrEmpty(v.expires_at))
                    {
                        DateTime exp;
                        if (DateTime.TryParse(v.expires_at, out exp))
                        {
                            if (now >= exp)
                            {
                                v.status = "EXPIRED";
                                changed = true;
                            }
                        }
                    }
                }
                if (changed) Save();
            }
        }

        public static VoucherItem CreateVoucher(int duration, double price, string notes)
        {
            lock (_lock)
            {
                string code = GenerateCode();
                var item = new VoucherItem
                {
                    code = code,
                    username = "GUEST-" + code,
                    duration_minutes = duration,
                    price = price,
                    status = "PENDING",
                    created_at = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
                    expires_at = null,
                    client_ip = null,
                    client_mac = null,
                    notes = notes
                };
                Vouchers.Insert(0, item);
                Save();
                return item;
            }
        }

        public static bool RevokeVoucher(string code)
        {
            lock (_lock)
            {
                var v = Vouchers.Find(x => x.code.Equals(code, StringComparison.OrdinalIgnoreCase));
                if (v != null)
                {
                    v.status = "REVOKED";
                    Save();
                    return true;
                }
                return false;
            }
        }

        public static bool ExtendSession(string code, int additionalMinutes, out int remainingMins)
        {
            remainingMins = 0;
            lock (_lock)
            {
                var v = Vouchers.Find(x => x.code.Equals(code, StringComparison.OrdinalIgnoreCase));
                if (v == null) return false;

                DateTime now = DateTime.Now;
                DateTime baseTime = now;
                if (!string.IsNullOrEmpty(v.expires_at))
                {
                    DateTime curExp;
                    if (DateTime.TryParse(v.expires_at, out curExp))
                    {
                        if (curExp > now) baseTime = curExp;
                    }
                }

                DateTime newExp = baseTime.AddMinutes(additionalMinutes);
                v.expires_at = newExp.ToString("yyyy-MM-ddTHH:mm:ss");
                v.duration_minutes += additionalMinutes;
                v.status = "ACTIVE";
                Save();

                remainingMins = (int)Math.Max(1, (newExp - now).TotalMinutes);
                return true;
            }
        }

        public static VoucherItem GenerateOnDemandGuest(string clientIp, int duration)
        {
            lock (_lock)
            {
                DateTime now = DateTime.Now;
                DateTime exp = now.AddMinutes(duration);
                string code = GenerateCode();
                string username = "GUEST-" + code;

                var item = new VoucherItem
                {
                    code = code,
                    username = username,
                    duration_minutes = duration,
                    price = 0.0,
                    status = "ACTIVE",
                    created_at = now.ToString("yyyy-MM-ddTHH:mm:ss"),
                    expires_at = exp.ToString("yyyy-MM-ddTHH:mm:ss"),
                    client_ip = clientIp,
                    client_mac = "هاتف الزبون (طلب ذاتي)",
                    notes = "كود ذاتي (Wall QR) - " + username
                };
                Vouchers.Insert(0, item);
                Save();
                return item;
            }
        }

        private static string GenerateCode()
        {
            const string chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ";
            Random rand = new Random();
            char[] code = new char[6];
            for (int i = 0; i < 6; i++)
                code[i] = chars[rand.Next(chars.Length)];
            return "WIFI-" + new string(code);
        }
    }

    public static class HardwareManager
    {
        public static string ScanWifiDongles()
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("netsh", "wlan show interfaces");
                psi.RedirectStandardOutput = true;
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                psi.StandardOutputEncoding = Encoding.Default;

                using (Process p = Process.Start(psi))
                {
                    string output = p.StandardOutput.ReadToEnd();
                    p.WaitForExit();

                    if (output.IndexOf("aucune interface", StringComparison.OrdinalIgnoreCase) >= 0 ||
                        output.IndexOf("There is no wireless interface", StringComparison.OrdinalIgnoreCase) >= 0 ||
                        output.IndexOf("لم يتم العثور على أي واجهة", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        AppState.DetectedAdapter = "غير متصل";
                        return "غير متصل";
                    }

                    // Look for Description / Description de l'interface
                    string[] lines = output.Split(new char[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
                    foreach (string line in lines)
                    {
                        string trimmed = line.Trim();
                        if (trimmed.IndexOf("Description", StringComparison.OrdinalIgnoreCase) >= 0)
                        {
                            int colon = trimmed.IndexOf(':');
                            if (colon >= 0 && colon < trimmed.Length - 1)
                            {
                                string name = trimmed.Substring(colon + 1).Trim();
                                if (!name.Contains("802.3") && !name.Contains("Ethernet") && !name.Contains("Virtual"))
                                {
                                    AppState.DetectedAdapter = name;
                                    return name;
                                }
                            }
                        }
                    }
                }
            }
            catch { }

            AppState.DetectedAdapter = "غير متصل";
            return "غير متصل";
        }

        public static bool StartHotspot(string ssid, string key)
        {
            try
            {
                RunNetsh(string.Format("wlan set hostednetwork mode=allow ssid=\"{0}\" key=\"{1}\"", ssid, key));
                string res = RunNetsh("wlan start hostednetwork");
                if (res.IndexOf("démarré", StringComparison.OrdinalIgnoreCase) >= 0 ||
                    res.IndexOf("started", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    AppState.HotspotActive = true;
                    return true;
                }
            }
            catch { }
            AppState.HotspotActive = false;
            return false;
        }

        public static void StopHotspot()
        {
            try
            {
                RunNetsh("wlan stop hostednetwork");
            }
            catch { }
            AppState.HotspotActive = false;
        }

        private static string RunNetsh(string args)
        {
            ProcessStartInfo psi = new ProcessStartInfo("netsh", args);
            psi.RedirectStandardOutput = true;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            using (Process p = Process.Start(psi))
            {
                string outStr = p.StandardOutput.ReadToEnd();
                p.WaitForExit();
                return outStr;
            }
        }
    }

    public class LocalHttpServer
    {
        private HttpListener _listener;
        private Thread _workerThread;
        private bool _running = false;
        private JavaScriptSerializer _json = new JavaScriptSerializer();

        public void Start(int port)
        {
            bool started = false;

            // 1. Try wildcard prefix first (accessible to clients across Wi-Fi if elevated)
            try
            {
                _listener = new HttpListener();
                _listener.Prefixes.Add(string.Format("http://*:{0}/", port));
                _listener.Start();
                started = true;
            }
            catch { }

            // 2. If wildcard requires URL reservation, fallback to standard loopback
            if (!started)
            {
                try
                {
                    if (_listener != null) { try { _listener.Close(); } catch { } }
                    _listener = new HttpListener();
                    _listener.Prefixes.Add(string.Format("http://localhost:{0}/", port));
                    _listener.Prefixes.Add(string.Format("http://127.0.0.1:{0}/", port));
                    _listener.Start();
                    started = true;
                }
                catch (Exception ex)
                {
                    try { File.AppendAllText(Path.Combine(AppState.BaseDirectory, "server_err.txt"), ex.ToString() + "\n"); } catch { }
                }
            }

            if (started)
            {
                _running = true;
                _workerThread = new Thread(ListenLoop);
                _workerThread.IsBackground = true;
                _workerThread.Start();
            }
        }

        public void Stop()
        {
            _running = false;
            try { _listener.Stop(); } catch { }
        }

        private void ListenLoop()
        {
            while (_running)
            {
                try
                {
                    var context = _listener.GetContext();
                    ThreadPool.QueueUserWorkItem(ProcessRequest, context);
                }
                catch
                {
                    if (!_running) break;
                }
            }
        }

        private void ProcessRequest(object state)
        {
            var ctx = (HttpListenerContext)state;
            var req = ctx.Request;
            var resp = ctx.Response;

            // CORS headers
            resp.AddHeader("Access-Control-Allow-Origin", "*");
            resp.AddHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
            resp.AddHeader("Access-Control-Allow-Headers", "Content-Type");

            if (req.HttpMethod == "OPTIONS")
            {
                resp.StatusCode = 200;
                resp.Close();
                return;
            }

            string path = req.Url.AbsolutePath.ToLowerInvariant();
            string method = req.HttpMethod.ToUpperInvariant();

            try
            {
                AppState.CheckExpirations();

                // 1. GET /api/status
                if (method == "GET" && path == "/api/status")
                {
                    string adapter = HardwareManager.ScanWifiDongles();
                    bool hasDongle = adapter != "غير متصل";

                    int activeCount = 0;
                    int expiredCount = 0;
                    double rev = 0;
                    lock (AppState.Vouchers)
                    {
                        foreach (var v in AppState.Vouchers)
                        {
                            if (v.status == "ACTIVE") activeCount++;
                            if (v.status == "EXPIRED") expiredCount++;
                            rev += v.price;
                        }
                    }

                    var data = new Dictionary<string, object>
                    {
                        { "hotspot_active", AppState.HotspotActive && hasDongle },
                        { "ssid", AppState.Settings.hotspot_ssid },
                        { "shop_name", AppState.Settings.shop_name },
                        { "wall_duration", AppState.Settings.default_duration_minutes },
                        { "adapter", adapter },
                        { "adapters_count", hasDongle ? 1 : 0 },
                        { "ics_active", AppState.HotspotActive && hasDongle },
                        { "stats", new Dictionary<string, object>
                            {
                                { "active_sessions", activeCount },
                                { "total_vouchers", AppState.Vouchers.Count },
                                { "expired_vouchers", expiredCount },
                                { "revenue", rev }
                            }
                        }
                    };
                    SendJson(resp, data);
                    return;
                }

                // 2. GET /api/hardware/scan
                if (method == "GET" && path == "/api/hardware/scan")
                {
                    string adapter = HardwareManager.ScanWifiDongles();
                    bool connected = adapter != "غير متصل";
                    var adapters = new List<Dictionary<string, string>>();
                    if (connected)
                    {
                        adapters.Add(new Dictionary<string, string> { { "name", adapter } });
                    }

                    var data = new Dictionary<string, object>
                    {
                        { "connected", connected },
                        { "adapters", adapters },
                        { "message", connected ? ("تم العثور على: " + adapter) : "لم يتم العثور على أي قطعة واي فاي في منافذ USB" }
                    };
                    SendJson(resp, data);
                    return;
                }

                // 3. GET /api/vouchers
                if (method == "GET" && path == "/api/vouchers")
                {
                    SendJson(resp, AppState.Vouchers);
                    return;
                }

                // 4. GET /api/clients
                if (method == "GET" && path == "/api/clients")
                {
                    var clients = new List<Dictionary<string, object>>();
                    lock (AppState.Vouchers)
                    {
                        foreach (var v in AppState.Vouchers)
                        {
                            if (v.status == "ACTIVE")
                            {
                                clients.Add(new Dictionary<string, object>
                                {
                                    { "voucher_code", v.code },
                                    { "client_ip", v.client_ip ?? "192.168.137.2" },
                                    { "client_mac", v.client_mac ?? "جهاز متصل" },
                                    { "expire_time", v.expires_at },
                                    { "duration_minutes", v.duration_minutes },
                                    { "notes", v.notes }
                                });
                            }
                        }
                    }
                    SendJson(resp, clients);
                    return;
                }

                // 5. POST /api/vouchers/create
                if (method == "POST" && path == "/api/vouchers/create")
                {
                    string body = ReadBody(req);
                    var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                    int duration = dict.ContainsKey("duration") ? Convert.ToInt32(dict["duration"]) : AppState.Settings.default_duration_minutes;
                    double price = dict.ContainsKey("price") ? Convert.ToDouble(dict["price"]) : 0.0;
                    string notes = dict.ContainsKey("notes") ? dict["notes"].ToString() : "";

                    var item = AppState.CreateVoucher(duration, price, notes);
                    SendJson(resp, new Dictionary<string, object> { { "success", true }, { "voucher", item } });
                    return;
                }

                // 6. POST /api/vouchers/revoke
                if (method == "POST" && path == "/api/vouchers/revoke")
                {
                    string body = ReadBody(req);
                    var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                    string code = dict.ContainsKey("code") ? dict["code"].ToString() : "";
                    bool ok = AppState.RevokeVoucher(code);
                    SendJson(resp, new Dictionary<string, object> { { "success", ok } });
                    return;
                }

                // 7. POST /api/hotspot/toggle
                if (method == "POST" && path == "/api/hotspot/toggle")
                {
                    if (AppState.HotspotActive)
                    {
                        HardwareManager.StopHotspot();
                        SendJson(resp, new Dictionary<string, object> { { "success", true }, { "active", false } });
                    }
                    else
                    {
                        bool ok = HardwareManager.StartHotspot(AppState.Settings.hotspot_ssid, AppState.Settings.hotspot_password);
                        SendJson(resp, new Dictionary<string, object> { { "success", ok }, { "active", ok } });
                    }
                    return;
                }

                // 8. POST /api/settings/update
                if (method == "POST" && path == "/api/settings/update")
                {
                    string body = ReadBody(req);
                    var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                    if (dict.ContainsKey("ssid")) AppState.Settings.hotspot_ssid = dict["ssid"].ToString().Trim();
                    if (dict.ContainsKey("password")) AppState.Settings.hotspot_password = dict["password"].ToString().Trim();
                    if (dict.ContainsKey("shop_name")) AppState.Settings.shop_name = dict["shop_name"].ToString().Trim();

                    AppState.Save();
                    if (AppState.HotspotActive)
                    {
                        HardwareManager.StartHotspot(AppState.Settings.hotspot_ssid, AppState.Settings.hotspot_password);
                    }
                    SendJson(resp, new Dictionary<string, object> {
                        { "success", true },
                        { "ssid", AppState.Settings.hotspot_ssid },
                        { "shop_name", AppState.Settings.shop_name }
                    });
                    return;
                }

                // 9. POST /api/settings/wall-duration
                if (method == "POST" && path == "/api/settings/wall-duration")
                {
                    string body = ReadBody(req);
                    var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                    if (dict.ContainsKey("duration"))
                    {
                        AppState.Settings.default_duration_minutes = Convert.ToInt32(dict["duration"]);
                        AppState.Save();
                    }
                    SendJson(resp, new Dictionary<string, object> {
                        { "success", true },
                        { "duration", AppState.Settings.default_duration_minutes },
                        { "message", string.Format("تم ضبط مدة كود الحائط إلى {0} دقيقة", AppState.Settings.default_duration_minutes) }
                    });
                    return;
                }

                // 10. POST /api/sessions/extend (اضافة وقت اضافي للزبون يدويا)
                if (method == "POST" && path == "/api/sessions/extend")
                {
                    string body = ReadBody(req);
                    var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                    string code = dict.ContainsKey("code") ? dict["code"].ToString() : "";
                    int mins = dict.ContainsKey("minutes") ? Convert.ToInt32(dict["minutes"]) : 30;

                    int remMins;
                    bool ok = AppState.ExtendSession(code, mins, out remMins);
                    SendJson(resp, new Dictionary<string, object> {
                        { "success", ok },
                        { "message", ok ? string.Format("تمت إضافة {0} دقيقة بنجاح للزبون ({1})!", mins, code) : "تعذر العثور على القسيمة" },
                        { "data", new Dictionary<string, object> { { "remaining_minutes", remMins }, { "added_minutes", mins } } }
                    });
                    return;
                }

                // 11. POST /request-access (مسح كود الحائط الثابت)
                if (method == "POST" && path == "/request-access")
                {
                    string clientIp = req.RemoteEndPoint != null ? req.RemoteEndPoint.Address.ToString() : "192.168.137.45";
                    var guest = AppState.GenerateOnDemandGuest(clientIp, AppState.Settings.default_duration_minutes);
                    SendJson(resp, new Dictionary<string, object> { { "success", true }, { "voucher", guest } });
                    return;
                }

                // 12. Static Files (HTML, CSS, JS)
                string localFile = "";
                string contentType = "text/html; charset=utf-8";

                if (path == "/" || path == "/dashboard" || path == "/admin" || path == "/index.html")
                {
                    localFile = Path.Combine(AppState.BaseDirectory, "index.html");
                }
                else if (path == "/index.css")
                {
                    localFile = Path.Combine(AppState.BaseDirectory, "index.css");
                    contentType = "text/css; charset=utf-8";
                }
                else if (path == "/index.js")
                {
                    localFile = Path.Combine(AppState.BaseDirectory, "index.js");
                    contentType = "application/javascript; charset=utf-8";
                }
                else
                {
                    string cand = Path.Combine(AppState.BaseDirectory, path.TrimStart('/'));
                    if (File.Exists(cand)) localFile = cand;
                }

                if (!string.IsNullOrEmpty(localFile) && File.Exists(localFile))
                {
                    byte[] bytes = File.ReadAllBytes(localFile);
                    resp.ContentType = contentType;
                    resp.ContentLength64 = bytes.Length;
                    resp.OutputStream.Write(bytes, 0, bytes.Length);
                    resp.Close();
                    return;
                }

                // 404 fallback
                resp.StatusCode = 404;
                byte[] notFound = Encoding.UTF8.GetBytes("404 Not Found");
                resp.OutputStream.Write(notFound, 0, notFound.Length);
                resp.Close();
            }
            catch (Exception ex)
            {
                try
                {
                    resp.StatusCode = 500;
                    byte[] err = Encoding.UTF8.GetBytes("500 Server Error: " + ex.Message);
                    resp.OutputStream.Write(err, 0, err.Length);
                    resp.Close();
                }
                catch { }
            }
        }

        private string ReadBody(HttpListenerRequest req)
        {
            if (!req.HasEntityBody) return "";
            using (var reader = new StreamReader(req.InputStream, req.ContentEncoding))
            {
                return reader.ReadToEnd();
            }
        }

        private void SendJson(HttpListenerResponse resp, object data)
        {
            byte[] bytes = Encoding.UTF8.GetBytes(_json.Serialize(data));
            resp.ContentType = "application/json; charset=utf-8";
            resp.ContentLength64 = bytes.Length;
            resp.OutputStream.Write(bytes, 0, bytes.Length);
            resp.Close();
        }
    }

    public class MainWindowForm : Form
    {
        private NotifyIcon _trayIcon;
        private ContextMenuStrip _trayMenu;
        private LocalHttpServer _server;
        private System.Windows.Forms.Timer _monitorTimer;

        public MainWindowForm(LocalHttpServer server)
        {
            _server = server;
            InitializeComponent();
        }

        private void InitializeComponent()
        {
            this.Text = "WiFi Shop Manager - مدير واي فاي المحل التجاري";
            this.Size = new Size(480, 360);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.FormBorderStyle = FormBorderStyle.FixedSingle;
            this.MaximizeBox = false;
            this.BackColor = Color.FromArgb(15, 23, 42);
            this.ForeColor = Color.White;
            this.RightToLeft = RightToLeft.Yes;
            this.RightToLeftLayout = true;

            // Load app icon if exists
            string iconPath = Path.Combine(AppState.BaseDirectory, "src", "assets", "icon.ico");
            if (File.Exists(iconPath))
            {
                try { this.Icon = new Icon(iconPath); } catch { }
            }

            // Header Title
            Label lblTitle = new Label();
            lblTitle.Text = "📶 WiFi Shop Manager";
            lblTitle.Font = new Font("Segoe UI", 16, FontStyle.Bold);
            lblTitle.ForeColor = Color.FromArgb(96, 165, 250);
            lblTitle.Location = new Point(20, 20);
            lblTitle.AutoSize = true;
            this.Controls.Add(lblTitle);

            Label lblSubtitle = new Label();
            lblSubtitle.Text = "برنامج إدارة واي فاي الزبائن وبث الشبكة وتوليد القسائم";
            lblSubtitle.Font = new Font("Segoe UI", 9);
            lblSubtitle.ForeColor = Color.FromArgb(148, 163, 184);
            lblSubtitle.Location = new Point(20, 56);
            lblSubtitle.AutoSize = true;
            this.Controls.Add(lblSubtitle);

            // Status Frame
            Panel pnlStatus = new Panel();
            pnlStatus.Location = new Point(20, 95);
            pnlStatus.Size = new Size(425, 115);
            pnlStatus.BackColor = Color.FromArgb(30, 41, 59);
            this.Controls.Add(pnlStatus);

            Label lblServer = new Label();
            lblServer.Text = "● خادم البوابة والـ REST API: نشط على المنفذ 8080";
            lblServer.ForeColor = Color.FromArgb(52, 211, 153);
            lblServer.Font = new Font("Segoe UI", 9, FontStyle.Bold);
            lblServer.Location = new Point(15, 15);
            lblServer.AutoSize = true;
            pnlStatus.Controls.Add(lblServer);

            Label lblAdapter = new Label();
            lblAdapter.Text = "● قطعة الواي فاي: " + AppState.DetectedAdapter;
            lblAdapter.ForeColor = Color.FromArgb(248, 113, 113);
            lblAdapter.Font = new Font("Segoe UI", 9);
            lblAdapter.Location = new Point(15, 45);
            lblAdapter.AutoSize = true;
            pnlStatus.Controls.Add(lblAdapter);

            Label lblSSID = new Label();
            lblSSID.Text = "● اسم الشبكة للزبائن: " + AppState.Settings.hotspot_ssid;
            lblSSID.ForeColor = Color.FromArgb(203, 213, 225);
            lblSSID.Font = new Font("Segoe UI", 9);
            lblSSID.Location = new Point(15, 75);
            lblSSID.AutoSize = true;
            pnlStatus.Controls.Add(lblSSID);

            // Open Dashboard Button
            Button btnOpen = new Button();
            btnOpen.Text = "🌐 فتح لوحة التحكم الرئيسية (Dashboard)";
            btnOpen.Location = new Point(20, 225);
            btnOpen.Size = new Size(425, 42);
            btnOpen.BackColor = Color.FromArgb(37, 99, 235);
            btnOpen.ForeColor = Color.White;
            btnOpen.FlatStyle = FlatStyle.Flat;
            btnOpen.Font = new Font("Segoe UI", 10, FontStyle.Bold);
            btnOpen.Click += (s, e) => OpenDashboardInBrowser();
            this.Controls.Add(btnOpen);

            // Scan Hardware Button
            Button btnScan = new Button();
            btnScan.Text = "🔍 فحص وتحديث قطعة الواي فاي الآن";
            btnScan.Location = new Point(20, 275);
            btnScan.Size = new Size(205, 32);
            btnScan.BackColor = Color.FromArgb(51, 65, 85);
            btnScan.ForeColor = Color.White;
            btnScan.FlatStyle = FlatStyle.Flat;
            btnScan.Font = new Font("Segoe UI", 8, FontStyle.Bold);
            btnScan.Click += (s, e) =>
            {
                string ad = HardwareManager.ScanWifiDongles();
                lblAdapter.Text = "● قطعة الواي فاي: " + ad;
                lblAdapter.ForeColor = ad != "غير متصل" ? Color.FromArgb(52, 211, 153) : Color.FromArgb(248, 113, 113);
                MessageBox.Show(ad != "غير متصل" ? ("تم العثور على: " + ad) : "لم يتم العثور على قطعة واي فاي موصولة.", "فحص القطعة", MessageBoxButtons.OK, MessageBoxIcon.Information);
            };
            this.Controls.Add(btnScan);

            // Minimize to Tray Button
            Button btnMin = new Button();
            btnMin.Text = "📥 تصغير في الخلفية (Tray)";
            btnMin.Location = new Point(240, 275);
            btnMin.Size = new Size(205, 32);
            btnMin.BackColor = Color.FromArgb(51, 65, 85);
            btnMin.ForeColor = Color.White;
            btnMin.FlatStyle = FlatStyle.Flat;
            btnMin.Font = new Font("Segoe UI", 8);
            btnMin.Click += (s, e) =>
            {
                this.Hide();
                if (_trayIcon != null)
                {
                    _trayIcon.ShowBalloonTip(3000, "WiFi Shop Manager", "البرنامج يعمل الآن في شريط المهام بالخلفية.", ToolTipIcon.Info);
                }
            };
            this.Controls.Add(btnMin);

            // Setup Tray Icon
            _trayMenu = new ContextMenuStrip();
            _trayMenu.Items.Add("🌐 فتح لوحة التحكم", null, (s, e) => { this.Show(); this.WindowState = FormWindowState.Normal; OpenDashboardInBrowser(); });
            _trayMenu.Items.Add("🔍 فحص قطعة الواي فاي", null, (s, e) => HardwareManager.ScanWifiDongles());
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add("❌ خروج وإغلاق البرنامج", null, (s, e) => Application.Exit());

            _trayIcon = new NotifyIcon();
            _trayIcon.Text = "مدير واي فاي المحل التجاري";
            _trayIcon.ContextMenuStrip = _trayMenu;
            if (this.Icon != null) _trayIcon.Icon = this.Icon;
            else _trayIcon.Icon = SystemIcons.Application;
            _trayIcon.Visible = true;
            _trayIcon.DoubleClick += (s, e) => { this.Show(); this.WindowState = FormWindowState.Normal; OpenDashboardInBrowser(); };

            // Background Timer
            _monitorTimer = new System.Windows.Forms.Timer();
            _monitorTimer.Interval = 4000;
            _monitorTimer.Tick += (s, e) =>
            {
                AppState.CheckExpirations();
                string ad = HardwareManager.ScanWifiDongles();
                lblAdapter.Text = "● قطعة الواي فاي: " + ad;
                lblAdapter.ForeColor = ad != "غير متصل" ? Color.FromArgb(52, 211, 153) : Color.FromArgb(248, 113, 113);
            };
            _monitorTimer.Start();

            this.FormClosing += (s, e) =>
            {
                if (e.CloseReason == CloseReason.UserClosing)
                {
                    e.Cancel = true;
                    this.Hide();
                    _trayIcon.ShowBalloonTip(2000, "WiFi Shop Manager", "تم تصغير البرنامج إلى شريط المهام ليبقى البث والإنترنت نشطاً.", ToolTipIcon.Info);
                }
            };
        }

        private void OpenDashboardInBrowser()
        {
            try
            {
                Process.Start("http://127.0.0.1:8080/dashboard");
            }
            catch (Exception ex)
            {
                MessageBox.Show("خطأ في فتح المتصفح: " + ex.Message);
            }
        }

        protected override void OnFormClosed(FormClosedEventArgs e)
        {
            if (_trayIcon != null)
            {
                _trayIcon.Visible = false;
                _trayIcon.Dispose();
            }
            base.OnFormClosed(e);
        }
    }

    static class Program
    {
        private static Mutex _mutex = null;

        [STAThread]
        static void Main(string[] args)
        {
            string logPath = Path.Combine(AppState.BaseDirectory, "startup.log");
            AppDomain.CurrentDomain.UnhandledException += (s, e) => {
                try { File.AppendAllText(Path.Combine(AppState.BaseDirectory, "unhandled.log"), DateTime.Now.ToString() + " [CRASH] " + (e.ExceptionObject != null ? e.ExceptionObject.ToString() : "unknown") + "\n"); } catch { }
            };
            try { File.AppendAllText(logPath, DateTime.Now.ToString() + " [START] Main entered with args: " + (args != null ? string.Join(" ", args) : "") + "\n"); } catch { }

            // 1. Single Instance check
            const string appName = "WiFiShopManager_SingleInstance_App";
            bool createdNew = true;
            try
            {
                _mutex = new Mutex(true, appName, out createdNew);
            }
            catch (Exception ex)
            {
                try { File.AppendAllText(logPath, DateTime.Now.ToString() + " [MUTEX ERR] " + ex.Message + "\n"); } catch { }
            }

            if (!createdNew)
            {
                try { File.AppendAllText(logPath, DateTime.Now.ToString() + " [MUTEX] Already running, activating browser and exiting.\n"); } catch { }
                try { Process.Start("http://127.0.0.1:8080/dashboard"); } catch { }
                return;
            }

            bool isHeadless = false;
            if (args != null)
            {
                foreach (string a in args)
                {
                    if (a.Equals("--headless", StringComparison.OrdinalIgnoreCase) ||
                        a.Equals("--daemon", StringComparison.OrdinalIgnoreCase) ||
                        a.Equals("-d", StringComparison.OrdinalIgnoreCase))
                    {
                        isHeadless = true;
                    }
                }
            }

            // 2. Administrator Elevation check
            bool isAdmin = IsAdministrator();
            try { File.AppendAllText(logPath, DateTime.Now.ToString() + " [INFO] IsAdmin=" + isAdmin + ", IsHeadless=" + isHeadless + "\n"); } catch { }

            // 3. Load App State
            AppState.Load();
            HardwareManager.ScanWifiDongles();

            // 4. Start Built-in HTTP Server
            var server = new LocalHttpServer();
            server.Start(8080);
            try { File.AppendAllText(logPath, DateTime.Now.ToString() + " [INFO] Server started on port 8080\n"); } catch { }

            if (isHeadless)
            {
                Thread.Sleep(Timeout.Infinite);
                return;
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            // 5. Open Dashboard in Default Browser automatically on startup
            try
            {
                Process.Start("http://127.0.0.1:8080/dashboard");
            }
            catch { }

            // 6. Run Windows Forms Application
            try
            {
                Application.Run(new MainWindowForm(server));
            }
            catch (Exception ex)
            {
                try { File.AppendAllText(logPath, DateTime.Now.ToString() + " [GUI FALLBACK] " + ex.Message + "\n"); } catch { }
                Thread.Sleep(Timeout.Infinite);
            }
            finally
            {
                // Clean shutdown
                server.Stop();
            }
        }

        private static bool IsAdministrator()
        {
            try
            {
                WindowsIdentity identity = WindowsIdentity.GetCurrent();
                WindowsPrincipal principal = new WindowsPrincipal(identity);
                return principal.IsInRole(WindowsBuiltInRole.Administrator);
            }
            catch
            {
                return false;
            }
        }
    }
}
