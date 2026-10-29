using System;
using System.IO;
using System.Text;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Diagnostics;
using System.Collections.Generic;
using System.Windows.Forms;
using System.Drawing;
using System.Web.Script.Serialization;

namespace WiFiShopManagerV2
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
        public bool auto_generate_next { get; set; }

        public AppSettings()
        {
            shop_name = "WiFi Shop Manager";
            hotspot_ssid = "benhazem";
            hotspot_password = "12345678";
            default_duration_minutes = 60;
            portal_port = 8080;
            auto_generate_next = true;
        }
    }

    public static class WindowsHotspotManager
    {
        private static string FindScriptPath()
        {
            string[] candidates = new string[] {
                Path.Combine(AppState.BaseDirectory, "hotspot_ctrl.ps1"),
                Path.Combine(AppState.BaseDirectory, "v2_server", "hotspot_ctrl.ps1"),
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "hotspot_ctrl.ps1"),
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", "hotspot_ctrl.ps1")
            };
            foreach (string p in candidates)
            {
                try { if (File.Exists(p)) return Path.GetFullPath(p); } catch { }
            }
            return "hotspot_ctrl.ps1";
        }

        public static Dictionary<string, object> Execute(string action, string ssid = "", string password = "")
        {
            try
            {
                string script = FindScriptPath();
                string args = string.Format("-NoProfile -ExecutionPolicy Bypass -File \"{0}\" -Action {1}", script, action);
                if (!string.IsNullOrEmpty(ssid)) args += string.Format(" -SSID \"{0}\"", ssid.Replace("\"", "\\\""));
                if (!string.IsNullOrEmpty(password)) args += string.Format(" -Password \"{0}\"", password.Replace("\"", "\\\""));

                ProcessStartInfo psi = new ProcessStartInfo("powershell.exe", args)
                {
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    StandardOutputEncoding = Encoding.UTF8
                };

                using (Process p = Process.Start(psi))
                {
                    string output = p.StandardOutput.ReadToEnd();
                    p.WaitForExit(15000);
                    JavaScriptSerializer js = new JavaScriptSerializer();
                    if (!string.IsNullOrEmpty(output))
                    {
                        var res = js.Deserialize<Dictionary<string, object>>(output.Trim());
                        if (res != null) return res;
                    }
                }
            }
            catch { }
            return new Dictionary<string, object>();
        }

        public static void SyncFromWindows()
        {
            try
            {
                var res = Execute("get");
                if (res != null && res.ContainsKey("success") && Convert.ToBoolean(res["success"]))
                {
                    if (res.ContainsKey("active")) AppState.HotspotActive = Convert.ToBoolean(res["active"]);
                    if (res.ContainsKey("ssid") && res["ssid"] != null && !string.IsNullOrEmpty(res["ssid"].ToString()))
                        AppState.Settings.hotspot_ssid = res["ssid"].ToString();
                    if (res.ContainsKey("password") && res["password"] != null && !string.IsNullOrEmpty(res["password"].ToString()))
                        AppState.Settings.hotspot_password = res["password"].ToString();
                    AppState.Save();
                }
            }
            catch { }
        }
    }

    public class AppState
    {
        private static readonly object _lock = new object();
        public static AppSettings Settings = new AppSettings();
        public static List<VoucherItem> Vouchers = new List<VoucherItem>();
        public static string ServerIP = "192.168.137.1";
        public static bool HotspotActive = false;
        public static string BaseDirectory = AppDomain.CurrentDomain.BaseDirectory;

        private static string SettingsFilePath { get { return Path.Combine(BaseDirectory, "config_v2.json"); } }
        private static string VouchersFilePath { get { return Path.Combine(BaseDirectory, "vouchers_v2.json"); } }
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

                DetectServerIP();
                ThreadPool.QueueUserWorkItem((s) => WindowsHotspotManager.SyncFromWindows());
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

        public static void DetectServerIP()
        {
            try
            {
                string host = Dns.GetHostName();
                IPAddress[] ips = Dns.GetHostAddresses(host);
                bool foundHotspot = false;
                string fallback = "127.0.0.1";

                foreach (var ip in ips)
                {
                    if (ip.AddressFamily == System.Net.Sockets.AddressFamily.InterNetwork)
                    {
                        string str = ip.ToString();
                        if (str.StartsWith("192.168.137."))
                        {
                            ServerIP = str;
                            foundHotspot = true;
                            break;
                        }
                        if (!str.StartsWith("127.")) fallback = str;
                    }
                }

                if (!foundHotspot) ServerIP = fallback;
                HotspotActive = foundHotspot;
            }
            catch
            {
                ServerIP = "192.168.137.1";
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

        public static string CleanCode(string code)
        {
            if (string.IsNullOrEmpty(code)) return "";
            string c = code.Trim().ToUpperInvariant();
            if (c.StartsWith("WIFI-")) c = c.Substring(5);
            if (c.StartsWith("WIFI")) c = c.Substring(4);
            return c.Replace("-", "").Replace(" ", "");
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

        public static VoucherItem GetCurrentReadyVoucher(int duration = 0)
        {
            lock (_lock)
            {
                int dur = duration > 0 ? duration : Settings.default_duration_minutes;
                var pending = Vouchers.Find(x => x.status == "PENDING");
                if (pending != null)
                {
                    if (duration > 0 && pending.duration_minutes != duration)
                    {
                        pending.duration_minutes = duration;
                        Save();
                    }
                    return pending;
                }
                return CreateVoucher(dur, 0.0, "كود جاهز للتسليم للزبون");
            }
        }

        public static VoucherItem GenerateNextReadyVoucher(int duration = 0, double price = 0.0)
        {
            lock (_lock)
            {
                int dur = duration > 0 ? duration : Settings.default_duration_minutes;
                return CreateVoucher(dur, price, "كود جاهز للتسليم للزبون");
            }
        }

        public static List<VoucherItem> BatchCreateVouchers(int count, int duration, double price)
        {
            var list = new List<VoucherItem>();
            lock (_lock)
            {
                for (int i = 0; i < count; i++)
                {
                    list.Add(CreateVoucher(duration, price, "توليد دفعات"));
                }
            }
            return list;
        }

        public static VoucherItem RedeemVoucher(string inputCode, string clientIp, out string errorMsg)
        {
            errorMsg = "";
            lock (_lock)
            {
                string target = CleanCode(inputCode);
                if (string.IsNullOrEmpty(target))
                {
                    errorMsg = "يرجى إدخال الرقم السري أو مسح الباركود ⚠️";
                    return null;
                }

                VoucherItem match = null;
                foreach (var v in Vouchers)
                {
                    if (CleanCode(v.code) == target)
                    {
                        match = v;
                        break;
                    }
                }

                if (match == null)
                {
                    errorMsg = "الرقم السري غير صحيح! يرجى التحقق من الرقم أو طلب كود جديد ❌";
                    return null;
                }

                if (match.status == "EXPIRED")
                {
                    errorMsg = "عذراً، هذا الكود انتهت مدة صلاحيته ⏱️";
                    return null;
                }

                if (match.status == "REVOKED")
                {
                    errorMsg = "تم إيقاف هذا الكود من طرف الإدارة ❌";
                    return null;
                }

                if (match.status == "ACTIVE")
                {
                    if (!string.IsNullOrEmpty(match.client_ip) && match.client_ip == clientIp)
                    {
                        return match; // Already active on this device, resume
                    }
                    errorMsg = "عذراً، هذا الكود مستعمل بالفعل من جهاز آخر 🔒 (الكود يُستعمل مرة واحدة فقط)";
                    return null;
                }

                // Activate PENDING voucher
                DateTime now = DateTime.Now;
                DateTime exp = now.AddMinutes(match.duration_minutes);
                match.status = "ACTIVE";
                match.created_at = now.ToString("yyyy-MM-ddTHH:mm:ss");
                match.expires_at = exp.ToString("yyyy-MM-ddTHH:mm:ss");
                match.client_ip = !string.IsNullOrEmpty(clientIp) ? clientIp : "192.168.137.2";
                match.client_mac = "هاتف متصل";
                Save();

                // If auto_generate_next is enabled, automatically prepare the next fresh voucher
                if (Settings.auto_generate_next)
                {
                    ThreadPool.QueueUserWorkItem((s) => {
                        lock (_lock)
                        {
                            var pending = Vouchers.Find(x => x.status == "PENDING");
                            if (pending == null)
                            {
                                CreateVoucher(Settings.default_duration_minutes, 0.0, "كود جاهز للتسليم للزبون");
                            }
                        }
                    });
                }

                return match;
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

        private static readonly Random _rand = new Random();

        private static string GenerateCode()
        {
            lock (_lock)
            {
                for (int attempt = 0; attempt < 1000; attempt++)
                {
                    string code = _rand.Next(100000, 999999).ToString();
                    if (!Vouchers.Exists(v => v.code == code))
                    {
                        return code;
                    }
                }
                return _rand.Next(100000, 999999).ToString();
            }
        }
    }

    public class LocalHttpServer
    {
        private TcpListener _listener;
        private Thread _workerThread;
        private bool _running = false;
        private JavaScriptSerializer _json = new JavaScriptSerializer();

        public void Start(int port)
        {
            try
            {
                _listener = new TcpListener(IPAddress.Any, port);
                _listener.Start();
                _running = true;
                _workerThread = new Thread(ListenLoop);
                _workerThread.IsBackground = true;
                _workerThread.Start();
            }
            catch { }
        }

        public void Stop()
        {
            _running = false;
            try { if (_listener != null) _listener.Stop(); } catch { }
        }

        private void ListenLoop()
        {
            while (_running)
            {
                try
                {
                    TcpClient client = _listener.AcceptTcpClient();
                    ThreadPool.QueueUserWorkItem(ProcessClient, client);
                }
                catch
                {
                    if (!_running) break;
                }
            }
        }

        private void ProcessClient(object state)
        {
            using (TcpClient client = (TcpClient)state)
            {
                try
                {
                    client.ReceiveTimeout = 6000;
                    client.SendTimeout = 6000;
                    NetworkStream stream = client.GetStream();

                    byte[] buffer = new byte[8192];
                    MemoryStream ms = new MemoryStream();
                    int read;
                    int headerEnd = -1;

                    while ((read = stream.Read(buffer, 0, buffer.Length)) > 0)
                    {
                        ms.Write(buffer, 0, read);
                        byte[] all = ms.ToArray();
                        headerEnd = FindHeaderEnd(all);
                        if (headerEnd != -1) break;
                        if (ms.Length > 65536) break;
                    }

                    if (headerEnd == -1) return;

                    byte[] raw = ms.ToArray();
                    string headerText = Encoding.UTF8.GetString(raw, 0, headerEnd);
                    string[] lines = headerText.Split(new string[] { "\r\n" }, StringSplitOptions.None);
                    if (lines.Length == 0) return;

                    string[] firstLine = lines[0].Split(' ');
                    if (firstLine.Length < 2) return;

                    string method = firstLine[0].ToUpperInvariant();
                    string rawUrl = firstLine[1];
                    string path = rawUrl;
                    int qIdx = path.IndexOf('?');
                    if (qIdx != -1) path = path.Substring(0, qIdx);
                    path = path.ToLowerInvariant();

                    Dictionary<string, string> headers = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                    for (int i = 1; i < lines.Length; i++)
                    {
                        int c = lines[i].IndexOf(':');
                        if (c > 0)
                        {
                            headers[lines[i].Substring(0, c).Trim()] = lines[i].Substring(c + 1).Trim();
                        }
                    }

                    if (method == "OPTIONS")
                    {
                        SendEmpty(stream, 200);
                        return;
                    }

                    int contentLength = 0;
                    if (headers.ContainsKey("Content-Length"))
                        int.TryParse(headers["Content-Length"], out contentLength);

                    int bodyStart = headerEnd + 4;
                    int alreadyRead = raw.Length - bodyStart;
                    MemoryStream bodyMs = new MemoryStream();
                    if (alreadyRead > 0)
                    {
                        bodyMs.Write(raw, bodyStart, alreadyRead);
                    }

                    while (bodyMs.Length < contentLength)
                    {
                        int toRead = Math.Min(buffer.Length, contentLength - (int)bodyMs.Length);
                        read = stream.Read(buffer, 0, toRead);
                        if (read <= 0) break;
                        bodyMs.Write(buffer, 0, read);
                    }

                    string body = Encoding.UTF8.GetString(bodyMs.ToArray());
                    string clientIp = "192.168.137.2";
                    try
                    {
                        var ipEnd = client.Client.RemoteEndPoint as IPEndPoint;
                        if (ipEnd != null) clientIp = ipEnd.Address.ToString();
                    }
                    catch { }

                    AppState.CheckExpirations();
                    AppState.DetectServerIP();

                    // 1. GET /api/status
                    if (method == "GET" && path == "/api/status")
                    {
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
                            { "hotspot_active", AppState.HotspotActive },
                            { "server_ip", AppState.ServerIP },
                            { "portal_url", string.Format("http://{0}:{1}/", AppState.ServerIP, AppState.Settings.portal_port) },
                            { "ssid", AppState.Settings.hotspot_ssid },
                            { "password", AppState.Settings.hotspot_password },
                            { "shop_name", AppState.Settings.shop_name },
                            { "wall_duration", AppState.Settings.default_duration_minutes },
                            { "auto_generate_next", AppState.Settings.auto_generate_next },
                            { "current_ready_voucher", AppState.GetCurrentReadyVoucher() },
                            { "status_message", AppState.HotspotActive ? "نقطة اتصال ويندوز (Mobile Hotspot) مفعلة وجاهزة بنجاح ✅" : "يرجى تشغيل Mobile Hotspot من إعدادات ويندوز ⚠️" },
                            { "stats", new Dictionary<string, object>
                                {
                                    { "active_sessions", activeCount },
                                    { "total_vouchers", AppState.Vouchers.Count },
                                    { "expired_vouchers", expiredCount },
                                    { "revenue", rev }
                                }
                            }
                        };
                        SendJson(stream, data);
                        return;
                    }

                    // 2. GET /api/vouchers
                    if (method == "GET" && path == "/api/vouchers")
                    {
                        SendJson(stream, AppState.Vouchers);
                        return;
                    }

                    // 3. GET /api/clients
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
                        SendJson(stream, clients);
                        return;
                    }

                    // 4. POST /api/vouchers/create
                    if (method == "POST" && path == "/api/vouchers/create")
                    {
                        var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                        int duration = dict.ContainsKey("duration") ? Convert.ToInt32(dict["duration"]) : AppState.Settings.default_duration_minutes;
                        double price = dict.ContainsKey("price") ? Convert.ToDouble(dict["price"]) : 0.0;
                        string notes = dict.ContainsKey("notes") ? dict["notes"].ToString() : "";

                        var item = AppState.CreateVoucher(duration, price, notes);
                        SendJson(stream, new Dictionary<string, object> { { "success", true }, { "voucher", item } });
                        return;
                    }

                    // 5. POST /api/vouchers/revoke
                    if (method == "POST" && path == "/api/vouchers/revoke")
                    {
                        var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                        string code = dict.ContainsKey("code") ? dict["code"].ToString() : "";
                        bool ok = AppState.RevokeVoucher(code);
                        SendJson(stream, new Dictionary<string, object> { { "success", ok } });
                        return;
                    }

                    // 5c. GET or POST /api/vouchers/current-ready
                    if (path == "/api/vouchers/current-ready")
                    {
                        int dur = AppState.Settings.default_duration_minutes;
                        if (method == "POST" && !string.IsNullOrEmpty(body))
                        {
                            var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                            if (dict.ContainsKey("duration")) dur = Convert.ToInt32(dict["duration"]);
                        }
                        var ready = AppState.GetCurrentReadyVoucher(dur);
                        SendJson(stream, new Dictionary<string, object> { { "success", true }, { "voucher", ready } });
                        return;
                    }

                    // 5d. POST /api/vouchers/next-ready
                    if (method == "POST" && path == "/api/vouchers/next-ready")
                    {
                        var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                        int dur = dict.ContainsKey("duration") ? Convert.ToInt32(dict["duration"]) : AppState.Settings.default_duration_minutes;
                        double pr = dict.ContainsKey("price") ? Convert.ToDouble(dict["price"]) : 0.0;
                        var fresh = AppState.GenerateNextReadyVoucher(dur, pr);
                        SendJson(stream, new Dictionary<string, object> { { "success", true }, { "voucher", fresh }, { "message", "تم توليد رقم سري جديد بنجاح! ✨" } });
                        return;
                    }

                    // 5e. POST /api/vouchers/batch-create
                    if (method == "POST" && path == "/api/vouchers/batch-create")
                    {
                        var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                        int count = dict.ContainsKey("count") ? Convert.ToInt32(dict["count"]) : 5;
                        int dur = dict.ContainsKey("duration") ? Convert.ToInt32(dict["duration"]) : AppState.Settings.default_duration_minutes;
                        double pr = dict.ContainsKey("price") ? Convert.ToDouble(dict["price"]) : 0.0;
                        var batch = AppState.BatchCreateVouchers(count, dur, pr);
                        SendJson(stream, new Dictionary<string, object> { { "success", true }, { "vouchers", batch }, { "count", batch.Count } });
                        return;
                    }

                    // 5f. POST /api/portal/login
                    if (method == "POST" && (path == "/api/portal/login" || path == "/api/vouchers/redeem"))
                    {
                        var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                        string code = dict.ContainsKey("code") ? dict["code"].ToString() : "";
                        string err;
                        var activated = AppState.RedeemVoucher(code, clientIp, out err);
                        if (activated != null)
                        {
                            int rem = activated.duration_minutes;
                            DateTime exp;
                            if (DateTime.TryParse(activated.expires_at, out exp))
                            {
                                rem = (int)Math.Max(1, (exp - DateTime.Now).TotalMinutes);
                            }
                            SendJson(stream, new Dictionary<string, object> {
                                { "success", true },
                                { "voucher", activated },
                                { "remaining_minutes", rem },
                                { "shop_name", AppState.Settings.shop_name },
                                { "message", "تم تفعيل الإنترنت بنجاح! استمتع بالاتصال ✅" }
                            });
                        }
                        else
                        {
                            SendJson(stream, new Dictionary<string, object> {
                                { "success", false },
                                { "message", err }
                            });
                        }
                        return;
                    }

                    // 5b. POST /api/hotspot/toggle
                    if (method == "POST" && path == "/api/hotspot/toggle")
                    {
                        string act = AppState.HotspotActive ? "stop" : "start";
                        var res = WindowsHotspotManager.Execute(act);
                        if (res != null && res.ContainsKey("active"))
                        {
                            AppState.HotspotActive = Convert.ToBoolean(res["active"]);
                        }
                        else
                        {
                            AppState.HotspotActive = !AppState.HotspotActive;
                        }
                        SendJson(stream, new Dictionary<string, object> {
                            { "success", true },
                            { "active", AppState.HotspotActive },
                            { "ssid", AppState.Settings.hotspot_ssid },
                            { "password", AppState.Settings.hotspot_password }
                        });
                        return;
                    }

                    // 6. POST /api/settings/update
                    if (method == "POST" && path == "/api/settings/update")
                    {
                        var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                        bool changedHotspot = false;
                        if (dict.ContainsKey("ssid"))
                        {
                            string s = dict["ssid"].ToString().Trim();
                            if (!string.IsNullOrEmpty(s)) { AppState.Settings.hotspot_ssid = s; changedHotspot = true; }
                        }
                        if (dict.ContainsKey("password"))
                        {
                            string p = dict["password"].ToString().Trim();
                            if (p.Length >= 8) { AppState.Settings.hotspot_password = p; changedHotspot = true; }
                        }
                        if (dict.ContainsKey("shop_name")) AppState.Settings.shop_name = dict["shop_name"].ToString().Trim();
                        if (dict.ContainsKey("auto_generate_next")) AppState.Settings.auto_generate_next = Convert.ToBoolean(dict["auto_generate_next"]);

                        AppState.Save();

                        if (changedHotspot)
                        {
                            ThreadPool.QueueUserWorkItem((s) => {
                                WindowsHotspotManager.Execute("set", AppState.Settings.hotspot_ssid, AppState.Settings.hotspot_password);
                            });
                        }

                        SendJson(stream, new Dictionary<string, object> {
                            { "success", true },
                            { "ssid", AppState.Settings.hotspot_ssid },
                            { "password", AppState.Settings.hotspot_password },
                            { "shop_name", AppState.Settings.shop_name },
                            { "auto_generate_next", AppState.Settings.auto_generate_next },
                            { "message", "تم تطبيق وتحديث إعدادات نقطة الاتصال في ويندوز فوراً!" }
                        });
                        return;
                    }

                    // 6b. POST /api/hotspot/generate-password
                    if (method == "POST" && path == "/api/hotspot/generate-password")
                    {
                        Random rand = new Random();
                        string newPass = rand.Next(10000000, 99999999).ToString();
                        AppState.Settings.hotspot_password = newPass;
                        AppState.Save();

                        ThreadPool.QueueUserWorkItem((s) => {
                            WindowsHotspotManager.Execute("set", AppState.Settings.hotspot_ssid, newPass);
                        });

                        SendJson(stream, new Dictionary<string, object> {
                            { "success", true },
                            { "password", newPass },
                            { "ssid", AppState.Settings.hotspot_ssid },
                            { "message", "تم توليد كلمة سر جديدة وتطبيقها في ويندوز فوراً!" }
                        });
                        return;
                    }

                    // 7. POST /api/settings/wall-duration
                    if (method == "POST" && path == "/api/settings/wall-duration")
                    {
                        var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                        if (dict.ContainsKey("duration"))
                        {
                            AppState.Settings.default_duration_minutes = Convert.ToInt32(dict["duration"]);
                            AppState.Save();
                        }
                        SendJson(stream, new Dictionary<string, object> {
                            { "success", true },
                            { "duration", AppState.Settings.default_duration_minutes },
                            { "message", string.Format("تم ضبط مدة كود الحائط إلى {0} دقيقة", AppState.Settings.default_duration_minutes) }
                        });
                        return;
                    }

                    // 8. POST /api/sessions/extend
                    if (method == "POST" && path == "/api/sessions/extend")
                    {
                        var dict = _json.Deserialize<Dictionary<string, object>>(body) ?? new Dictionary<string, object>();
                        string code = dict.ContainsKey("code") ? dict["code"].ToString() : "";
                        int mins = dict.ContainsKey("minutes") ? Convert.ToInt32(dict["minutes"]) : 30;

                        int remMins;
                        bool ok = AppState.ExtendSession(code, mins, out remMins);
                        SendJson(stream, new Dictionary<string, object> {
                            { "success", ok },
                            { "message", ok ? string.Format("تمت إضافة {0} دقيقة بنجاح للزبون ({1})!", mins, code) : "تعذر العثور على القسيمة" },
                            { "data", new Dictionary<string, object> { { "remaining_minutes", remMins }, { "added_minutes", mins } } }
                        });
                        return;
                    }

                    // 9. POST /request-access
                    if (method == "POST" && path == "/request-access")
                    {
                        var guest = AppState.GenerateOnDemandGuest(clientIp, AppState.Settings.default_duration_minutes);
                        SendJson(stream, new Dictionary<string, object> { { "success", true }, { "voucher", guest } });
                        return;
                    }

                    // 10. Static Web Assets
                    string localFile = "";
                    string contentType = "text/html; charset=utf-8";

                    string webDir = Path.Combine(AppState.BaseDirectory, "v2_server", "web");
                    if (!Directory.Exists(webDir)) webDir = Path.Combine(AppState.BaseDirectory, "web");
                    if (!Directory.Exists(webDir)) webDir = AppState.BaseDirectory;

                    if (path == "/" || path == "/dashboard" || path == "/admin" || path == "/index.html")
                    {
                        localFile = Path.Combine(webDir, "index.html");
                    }
                    else if (path == "/portal" || path == "/portal.html" || path == "/login")
                    {
                        localFile = Path.Combine(webDir, "portal.html");
                        if (!File.Exists(localFile)) localFile = Path.Combine(webDir, "index.html");
                    }
                    else if (path == "/index.css" || path.EndsWith(".css"))
                    {
                        localFile = Path.Combine(webDir, path.TrimStart('/'));
                        contentType = "text/css; charset=utf-8";
                    }
                    else if (path == "/index.js" || path.EndsWith(".js"))
                    {
                        localFile = Path.Combine(webDir, path.TrimStart('/'));
                        contentType = "application/javascript; charset=utf-8";
                    }
                    else if (path.EndsWith(".png"))
                    {
                        localFile = Path.Combine(webDir, path.TrimStart('/'));
                        contentType = "image/png";
                    }
                    else if (path.EndsWith(".jpg") || path.EndsWith(".jpeg"))
                    {
                        localFile = Path.Combine(webDir, path.TrimStart('/'));
                        contentType = "image/jpeg";
                    }
                    else if (path.EndsWith(".svg"))
                    {
                        localFile = Path.Combine(webDir, path.TrimStart('/'));
                        contentType = "image/svg+xml";
                    }
                    else
                    {
                        string cand = Path.Combine(webDir, path.TrimStart('/'));
                        if (File.Exists(cand)) localFile = cand;
                    }

                    if (!string.IsNullOrEmpty(localFile) && File.Exists(localFile))
                    {
                        byte[] bytes = File.ReadAllBytes(localFile);
                        SendBytes(stream, 200, contentType, bytes);
                        return;
                    }

                    SendBytes(stream, 404, "text/plain; charset=utf-8", Encoding.UTF8.GetBytes("404 Not Found"));
                }
                catch (Exception ex)
                {
                    try
                    {
                        SendBytes(client.GetStream(), 500, "text/plain; charset=utf-8", Encoding.UTF8.GetBytes("500 Server Error: " + ex.Message));
                    }
                    catch { }
                }
            }
        }

        private static int FindHeaderEnd(byte[] data)
        {
            for (int i = 0; i <= data.Length - 4; i++)
            {
                if (data[i] == 13 && data[i + 1] == 10 && data[i + 2] == 13 && data[i + 3] == 10)
                    return i;
            }
            return -1;
        }

        private void SendEmpty(NetworkStream stream, int statusCode)
        {
            string resp = string.Format("HTTP/1.1 {0} OK\r\nAccess-Control-Allow-Origin: *\r\nAccess-Control-Allow-Methods: GET, POST, OPTIONS\r\nAccess-Control-Allow-Headers: Content-Type\r\nContent-Length: 0\r\nConnection: close\r\n\r\n", statusCode);
            byte[] bytes = Encoding.UTF8.GetBytes(resp);
            stream.Write(bytes, 0, bytes.Length);
        }

        private void SendJson(NetworkStream stream, object data)
        {
            byte[] body = Encoding.UTF8.GetBytes(_json.Serialize(data));
            string header = string.Format("HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nAccess-Control-Allow-Origin: *\r\nAccess-Control-Allow-Methods: GET, POST, OPTIONS\r\nAccess-Control-Allow-Headers: Content-Type\r\nContent-Length: {0}\r\nConnection: close\r\n\r\n", body.Length);
            byte[] headBytes = Encoding.UTF8.GetBytes(header);
            stream.Write(headBytes, 0, headBytes.Length);
            stream.Write(body, 0, body.Length);
        }

        private void SendBytes(NetworkStream stream, int statusCode, string contentType, byte[] body)
        {
            string statusStr = statusCode == 200 ? "OK" : (statusCode == 404 ? "Not Found" : "Error");
            string header = string.Format("HTTP/1.1 {0} {1}\r\nContent-Type: {2}\r\nAccess-Control-Allow-Origin: *\r\nAccess-Control-Allow-Methods: GET, POST, OPTIONS\r\nAccess-Control-Allow-Headers: Content-Type\r\nContent-Length: {3}\r\nConnection: close\r\n\r\n", statusCode, statusStr, contentType, body.Length);
            byte[] headBytes = Encoding.UTF8.GetBytes(header);
            stream.Write(headBytes, 0, headBytes.Length);
            stream.Write(body, 0, body.Length);
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
            this.Text = "WiFi Shop Manager v2 - مدير واي فاي المحل التجاري";
            this.Size = new Size(500, 420);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.FormBorderStyle = FormBorderStyle.FixedSingle;
            this.MaximizeBox = false;
            this.BackColor = Color.FromArgb(15, 23, 42);
            this.ForeColor = Color.White;
            this.RightToLeft = RightToLeft.Yes;
            this.RightToLeftLayout = true;

            // Header Title
            Label lblTitle = new Label();
            lblTitle.Text = "📶 WiFi Shop Manager v2";
            lblTitle.Font = new Font("Segoe UI", 16, FontStyle.Bold);
            lblTitle.ForeColor = Color.FromArgb(96, 165, 250);
            lblTitle.Location = new Point(20, 20);
            lblTitle.AutoSize = true;
            this.Controls.Add(lblTitle);

            Label lblSubtitle = new Label();
            lblSubtitle.Text = "إصدار خفيف بدون صلاحيات مسؤول (Zero Admin / UAC Required)";
            lblSubtitle.Font = new Font("Segoe UI", 9);
            lblSubtitle.ForeColor = Color.FromArgb(52, 211, 153);
            lblSubtitle.Location = new Point(20, 56);
            lblSubtitle.AutoSize = true;
            this.Controls.Add(lblSubtitle);

            // Status Frame
            Panel pnlStatus = new Panel();
            pnlStatus.Location = new Point(20, 90);
            pnlStatus.Size = new Size(445, 165);
            pnlStatus.BackColor = Color.FromArgb(30, 41, 59);
            this.Controls.Add(pnlStatus);

            Label lblServer = new Label();
            lblServer.Text = "● خادم الويب المحلي: نشط على المنفذ " + AppState.Settings.portal_port;
            lblServer.ForeColor = Color.FromArgb(52, 211, 153);
            lblServer.Font = new Font("Segoe UI", 9, FontStyle.Bold);
            lblServer.Location = new Point(15, 12);
            lblServer.AutoSize = true;
            pnlStatus.Controls.Add(lblServer);

            Label lblIP = new Label();
            lblIP.Text = "● عنوان اتصال هواتف الزبائن: http://" + AppState.ServerIP + ":8080/";
            lblIP.ForeColor = Color.FromArgb(96, 165, 250);
            lblIP.Font = new Font("Segoe UI", 9);
            lblIP.Location = new Point(15, 38);
            lblIP.AutoSize = true;
            pnlStatus.Controls.Add(lblIP);

            Label lblHotspot = new Label();
            lblHotspot.Text = AppState.HotspotActive ? "● نقطة اتصال ويندوز (Mobile Hotspot): مفعلة بنجاح ✅" : "● نقطة اتصال ويندوز: متوقفة ⚠️";
            lblHotspot.ForeColor = AppState.HotspotActive ? Color.FromArgb(52, 211, 153) : Color.FromArgb(245, 158, 11);
            lblHotspot.Font = new Font("Segoe UI", 9);
            lblHotspot.Location = new Point(15, 64);
            lblHotspot.AutoSize = true;
            pnlStatus.Controls.Add(lblHotspot);

            Label lblSSID = new Label();
            lblSSID.Text = "● اسم شبكة الواي فاي (SSID): " + AppState.Settings.hotspot_ssid;
            lblSSID.ForeColor = Color.FromArgb(147, 197, 253);
            lblSSID.Font = new Font("Segoe UI", 9, FontStyle.Bold);
            lblSSID.Location = new Point(15, 92);
            lblSSID.AutoSize = true;
            pnlStatus.Controls.Add(lblSSID);

            Label lblPass = new Label();
            lblPass.Text = "● كلمة سر شبكة الواي فاي: " + AppState.Settings.hotspot_password;
            lblPass.ForeColor = Color.FromArgb(52, 211, 153);
            lblPass.Font = new Font("Segoe UI", 9, FontStyle.Bold);
            lblPass.Location = new Point(15, 120);
            lblPass.AutoSize = true;
            pnlStatus.Controls.Add(lblPass);

            // Open Dashboard Button
            Button btnOpen = new Button();
            btnOpen.Text = "🌐 فتح لوحة التحكم الرئيسية (Dashboard)";
            btnOpen.Location = new Point(20, 270);
            btnOpen.Size = new Size(445, 42);
            btnOpen.BackColor = Color.FromArgb(37, 99, 235);
            btnOpen.ForeColor = Color.White;
            btnOpen.FlatStyle = FlatStyle.Flat;
            btnOpen.Font = new Font("Segoe UI", 10, FontStyle.Bold);
            btnOpen.Click += (s, e) => OpenDashboardInBrowser();
            this.Controls.Add(btnOpen);

            // Open Windows Hotspot Settings
            Button btnHotspot = new Button();
            btnHotspot.Text = "⚙️ ضبط نقطة الاتصال في ويندوز";
            btnHotspot.Location = new Point(20, 325);
            btnHotspot.Size = new Size(215, 32);
            btnHotspot.BackColor = Color.FromArgb(51, 65, 85);
            btnHotspot.ForeColor = Color.White;
            btnHotspot.FlatStyle = FlatStyle.Flat;
            btnHotspot.Font = new Font("Segoe UI", 8, FontStyle.Bold);
            btnHotspot.Click += (s, e) =>
            {
                try { Process.Start("ms-settings:network-mobilehotspot"); } catch { }
            };
            this.Controls.Add(btnHotspot);

            // Minimize to Tray Button
            Button btnMin = new Button();
            btnMin.Text = "📥 تصغير في الخلفية (Tray)";
            btnMin.Location = new Point(250, 325);
            btnMin.Size = new Size(215, 32);
            btnMin.BackColor = Color.FromArgb(51, 65, 85);
            btnMin.ForeColor = Color.White;
            btnMin.FlatStyle = FlatStyle.Flat;
            btnMin.Font = new Font("Segoe UI", 8);
            btnMin.Click += (s, e) =>
            {
                this.Hide();
                if (_trayIcon != null)
                {
                    _trayIcon.ShowBalloonTip(3000, "WiFi Shop Manager v2", "البرنامج يعمل في الخلفية لخدمة الزبائن.", ToolTipIcon.Info);
                }
            };
            this.Controls.Add(btnMin);

            // Setup Tray Icon
            _trayMenu = new ContextMenuStrip();
            _trayMenu.Items.Add("🌐 فتح لوحة التحكم", null, (s, e) => { this.Show(); this.WindowState = FormWindowState.Normal; OpenDashboardInBrowser(); });
            _trayMenu.Items.Add("⚙️ إعدادات بث ويندوز", null, (s, e) => { try { Process.Start("ms-settings:network-mobilehotspot"); } catch { } });
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add("❌ خروج وإغلاق البرنامج", null, (s, e) => {
                _server.Stop();
                if (_trayIcon != null) _trayIcon.Visible = false;
                Environment.Exit(0);
            });

            _trayIcon = new NotifyIcon();
            _trayIcon.Text = "WiFi Shop Manager v2";
            _trayIcon.ContextMenuStrip = _trayMenu;
            _trayIcon.Icon = SystemIcons.Application;
            _trayIcon.Visible = true;
            _trayIcon.DoubleClick += (s, e) => { this.Show(); this.WindowState = FormWindowState.Normal; OpenDashboardInBrowser(); };

            // Background Monitor Timer
            _monitorTimer = new System.Windows.Forms.Timer();
            _monitorTimer.Interval = 4000;
            _monitorTimer.Tick += (s, e) =>
            {
                AppState.CheckExpirations();
                AppState.DetectServerIP();
                lblIP.Text = "● عنوان اتصال هواتف الزبائن: http://" + AppState.ServerIP + ":8080/";
                lblHotspot.Text = AppState.HotspotActive ? "● نقطة اتصال ويندوز (Mobile Hotspot): مفعلة بنجاح ✅" : "● نقطة اتصال ويندوز: متوقفة ⚠️";
                lblHotspot.ForeColor = AppState.HotspotActive ? Color.FromArgb(52, 211, 153) : Color.FromArgb(245, 158, 11);
                lblSSID.Text = "● اسم شبكة الواي فاي (SSID): " + AppState.Settings.hotspot_ssid;
                lblPass.Text = "● كلمة سر شبكة الواي فاي: " + AppState.Settings.hotspot_password;
            };
            _monitorTimer.Start();

            this.FormClosing += (s, e) =>
            {
                if (e.CloseReason == CloseReason.UserClosing)
                {
                    e.Cancel = true;
                    this.Hide();
                    _trayIcon.ShowBalloonTip(2000, "WiFi Shop Manager v2", "تم تصغير البرنامج لشريط المهام ليبقى خادم الويب وبث الإنترنت متاحاً للزبائن.", ToolTipIcon.Info);
                }
            };
        }

        private void OpenDashboardInBrowser()
        {
            try
            {
                Process.Start("http://localhost:8080/dashboard");
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
            string logPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "startup.log");
            try
            {
                File.AppendAllText(logPath, string.Format("[{0}] Starting WiFiShopManager_v2 (Args: {1})\r\n", DateTime.Now, string.Join(" ", args ?? new string[0])));
            }
            catch { }

            bool isHeadless = false;
            bool forceStart = false;
            if (args != null)
            {
                foreach (string a in args)
                {
                    if (a.Equals("--headless", StringComparison.OrdinalIgnoreCase) ||
                        a.Equals("--daemon", StringComparison.OrdinalIgnoreCase))
                    {
                        isHeadless = true;
                    }
                    if (a.Equals("--force", StringComparison.OrdinalIgnoreCase))
                    {
                        forceStart = true;
                    }
                }
            }

            if (!isHeadless && !forceStart)
            {
                const string appName = "WiFiShopManager_v2_SingleInstance";
                bool createdNew = true;
                try
                {
                    _mutex = new Mutex(true, appName, out createdNew);
                }
                catch (AbandonedMutexException)
                {
                    createdNew = true;
                }
                catch
                {
                    createdNew = true;
                }

                if (!createdNew)
                {
                    try { File.AppendAllText(logPath, "Another instance detected. Opening dashboard and exiting.\r\n"); } catch { }
                    try { Process.Start("http://localhost:8080/dashboard"); } catch { }
                    return;
                }
            }

            try
            {
                AppState.Load();
                try { File.AppendAllText(logPath, "AppState loaded. Starting LocalHttpServer on port " + AppState.Settings.portal_port + "...\r\n"); } catch { }

                var server = new LocalHttpServer();
                server.Start(AppState.Settings.portal_port);
                try { File.AppendAllText(logPath, "LocalHttpServer started successfully.\r\n"); } catch { }

                if (isHeadless)
                {
                    try { File.AppendAllText(logPath, "Running in headless mode. Entering wait loop.\r\n"); } catch { }
                    Thread.Sleep(Timeout.Infinite);
                    return;
                }

                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);

                try
                {
                    Process.Start("http://localhost:8080/dashboard");
                }
                catch { }

                try
                {
                    Application.Run(new MainWindowForm(server));
                }
                catch (Exception)
                {
                    Thread.Sleep(Timeout.Infinite);
                }
                finally
                {
                    server.Stop();
                }
            }
            catch (Exception ex)
            {
                try
                {
                    string crashPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "crash.txt");
                    File.WriteAllText(crashPath, ex.ToString());
                }
                catch { }
            }
        }
    }
}
