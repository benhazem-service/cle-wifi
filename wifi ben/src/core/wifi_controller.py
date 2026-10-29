"""
Windows Wi-Fi Hotspot, USB Dongle Detector, and Automated ICS (Internet Connection Sharing) Controller.
Completely automates adapter detection, hotspot activation, and ICS routing without manual Windows intervention.
"""
import subprocess
import re
import time
import threading
import platform
from typing import Dict, List, Tuple, Optional

class WiFiController:
    def __init__(self):
        self.is_windows = platform.system().lower() == "windows"
        self._dongle_watcher_thread: Optional[threading.Thread] = None
        self._stop_watcher = False
        self.last_detected_adapter: Optional[str] = None
        self.is_auto_configured = False

    def detect_wifi_adapters(self) -> List[Dict]:
        """
        Detects all genuinely available wireless Wi-Fi adapters (including USB Wi-Fi dongles).
        Filters out Ethernet (802.3), VPN adapters, and returns [] when no Wi-Fi dongle is plugged in.
        """
        if not self.is_windows:
            return []

        # 1. Primary check via netsh wlan show interfaces
        try:
            out_netsh = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )

            # If netsh explicitly reports no wireless interfaces present
            no_interface_patterns = [
                r"aucune interface",
                r"no wireless interface",
                r"not running",
                r"non démarré",
                r"aucun"
            ]
            for pattern in no_interface_patterns:
                if re.search(pattern, out_netsh, re.IGNORECASE):
                    return []

        except Exception:
            return []

        # 2. Query PowerShell strictly for 802.11 Wi-Fi adapters (NOT 802.3 Ethernet!)
        adapters = []
        ps_cmd = """
        Get-NetAdapter | Where-Object { 
            ($_.PhysicalMediaType -match "802.11|Wireless") -or 
            ($_.MediaType -match "Native 802.11")
        } | Select-Object Name, InterfaceDescription, Status, MacAddress, PhysicalMediaType | ConvertTo-Json
        """
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            out = res.stdout.strip()
            if out:
                import json
                try:
                    data = json.loads(out)
                    if isinstance(data, dict):
                        data = [data]
                    for item in data:
                        desc = item.get("InterfaceDescription", "")
                        adapters.append({
                            "name": item.get("Name", "Wi-Fi"),
                            "description": desc,
                            "status": item.get("Status", "Unknown"),
                            "mac": item.get("MacAddress", ""),
                            "is_usb": "usb" in desc.lower()
                        })
                except Exception:
                    pass
        except Exception as e:
            print(f"[WiFiController] Adapter detection error: {e}")

        return adapters

    def get_primary_internet_adapter(self) -> Optional[str]:
        """
        Finds the network interface currently providing internet access (default gateway).
        This is typically Ethernet or a secondary connection that will share internet with guests.
        """
        if not self.is_windows:
            return None

        ps_cmd = """
        (Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Sort-Object RouteMetric | Select-Object -First 1).InterfaceAlias
        """
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            alias = res.stdout.strip()
            return alias if alias else None
        except Exception:
            return None

    def enable_internet_connection_sharing(self, public_name: str = None, private_name: str = None) -> Tuple[bool, str]:
        """
        Programmatically enables Windows ICS (Internet Connection Sharing) via HNetCfg.HNetShare COM API.
        Routes internet from public_name (Ethernet/Internet) to private_name (Wi-Fi Hotspot).
        Zero manual user intervention in Windows Network Connections!
        """
        if not self.is_windows:
            return False, "غير مدعوم خارج ويندوز."

        if not public_name:
            public_name = self.get_primary_internet_adapter()

        ps_script = f"""
        $PublicName = "{public_name or ''}"
        $PrivateName = "{private_name or ''}"

        # Ensure SharedAccess service is running
        Set-Service -Name SharedAccess -StartupType Automatic -ErrorAction SilentlyContinue
        Start-Service -Name SharedAccess -ErrorAction SilentlyContinue

        $m = New-Object -ComObject HNetCfg.HNetShare
        $publicConn = $null
        $privateConn = $null

        # If names are not explicitly provided, find active internet and virtual wireless adapter
        foreach ($c in $m.EnumEveryConnection) {{
            $props = $m.NetConnectionProps.Invoke($c)
            if ($PublicName -and $props.Name -eq $PublicName) {{
                $publicConn = $c
            }}
            if ($PrivateName -and $props.Name -eq $PrivateName) {{
                $privateConn = $c
            }}
            if (-not $privateConn -and ($props.Name -match "Local Area Connection\*|Wi-Fi Direct|Hosted|Hotspot")) {{
                $privateConn = $c
            }}
        }}

        if ($publicConn) {{
            $cfg = $m.INetSharingConfigurationForINetConnection.Invoke($publicConn)
            $cfg.EnableSharing(0) # 0 = ICSSHARINGTYPE_PUBLIC
        }}
        if ($privateConn) {{
            $cfg = $m.INetSharingConfigurationForINetConnection.Invoke($privateConn)
            $cfg.EnableSharing(1) # 1 = ICSSHARINGTYPE_PRIVATE
        }}

        "ICS_SUCCESS"
        """
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if "ICS_SUCCESS" in res.stdout:
                return True, "تم تفعيل مشاركة الإنترنت (ICS) تلقائياً في الخلفية."
            return False, res.stderr or res.stdout
        except Exception as e:
            return False, f"خطأ أثناء تفعيل ICS: {e}"

    def auto_configure_system(self, ssid: str, password: str) -> Tuple[bool, str]:
        """
        Master Auto-Configuration Sequence:
        1. Checks for connected USB Wi-Fi dongle.
        2. Configures and starts Hotspot broadcast.
        3. Configures and applies Windows ICS sharing automatically.
        """
        adapters = self.detect_wifi_adapters()
        if not adapters:
            return False, "لم يتم العثور على أي قطعة واي فاي موصولة. يرجى إدخال قطعة الواي فاي (Clé Wi-Fi) في منفذ USB."

        adapter_name = adapters[0]["name"]
        adapter_desc = adapters[0]["description"]
        self.last_detected_adapter = f"{adapter_name} ({adapter_desc})"

        # 1. Configure and start hotspot
        self.configure_hotspot(ssid=ssid, password=password)
        start_success, start_msg = self.start_hotspot()

        # 2. Automatically configure ICS
        ics_success, ics_msg = self.enable_internet_connection_sharing()

        self.is_auto_configured = start_success
        summary = (
            f"✅ تم التكوين التلقائي بنجاح:\n"
            f"• المحول: {self.last_detected_adapter}\n"
            f"• بث الشبكة: {start_msg}\n"
            f"• مشاركة الإنترنت (ICS): {ics_msg}"
        )
        return start_success, summary

    def check_adapter_support(self) -> Tuple[bool, str]:
        if not self.is_windows:
            return False, "النظام الحالي ليس نظام ويندوز."

        adapters = self.detect_wifi_adapters()
        if adapters:
            return True, f"تم رصد قطعة الواي فاي بنجاح: {adapters[0]['name']}"
        return False, "في انتظار توصيل قطعة الواي فاي (Clé Wi-Fi)..."

    def configure_hotspot(self, ssid: str, password: str) -> Tuple[bool, str]:
        if len(password) < 8:
            return False, "يجب أن تكون كلمة المرور 8 خانات على الأقل."

        try:
            cmd = [
                "netsh", "wlan", "set", "hostednetwork",
                f"mode=allow",
                f"ssid={ssid}",
                f"key={password}"
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            return True, f"تم ضبط الشبكة: {ssid}"
        except Exception as e:
            return False, str(e)

    def start_hotspot(self) -> Tuple[bool, str]:
        try:
            cmd = ["netsh", "wlan", "start", "hostednetwork"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            output = result.stdout or result.stderr
            if "started" in output.lower() or "démarré" in output.lower() or result.returncode == 0:
                return True, "تم تشغيل نقطة بث الواي فاي بنجاح."

            # Windows 10/11 Mobile Hotspot fallback (with integrated WinRT ICS)
            ps_success, ps_msg = self._start_win10_mobile_hotspot()
            if ps_success:
                return True, ps_msg

            return False, output.strip()
        except Exception as e:
            return False, str(e)

    def stop_hotspot(self) -> Tuple[bool, str]:
        try:
            subprocess.run(
                ["netsh", "wlan", "stop", "hostednetwork"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            self._stop_win10_mobile_hotspot()
            return True, "تم إيقاف نقطة بث الواي فاي."
        except Exception as e:
            return False, str(e)

    def get_status(self) -> Dict:
        status = {
            "is_running": False,
            "ssid": "غير معروف",
            "connected_count": 0,
            "adapter_name": self.last_detected_adapter or "غير متصل",
            "is_auto_configured": self.is_auto_configured
        }
        try:
            cmd = ["netsh", "wlan", "show", "hostednetwork"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            out = result.stdout
            if re.search(r"Status\s*:\s*Started", out, re.IGNORECASE) or "démarré" in out.lower():
                status["is_running"] = True

            ssid_match = re.search(r"SSID name\s*:\s*\"?([^\r\n\"]+)\"?", out, re.IGNORECASE)
            if ssid_match:
                status["ssid"] = ssid_match.group(1)

            clients_match = re.search(r"Number of clients\s*:\s*(\d+)", out, re.IGNORECASE)
            if clients_match:
                status["connected_count"] = int(clients_match.group(1))

        except Exception as e:
            print(f"[WiFiController] Status error: {e}")

        return status

    def scan_arp_clients(self) -> List[Dict]:
        clients = []
        try:
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            for line in result.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and parts[2].lower() == "dynamic":
                    ip = parts[0]
                    mac = parts[1].replace("-", ":").upper()
                    if not ip.startswith("224.") and not ip.startswith("239.") and not ip.endswith(".255"):
                        clients.append({"ip": ip, "mac": mac})
        except Exception:
            pass
        return clients

    def start_dongle_auto_watcher(self, ssid: str, password: str, on_status_change=None):
        """
        Background daemon: Continuously monitors USB Wi-Fi dongle plug/unplug events.
        Automatically provisions the hotspot and ICS the moment the dongle is inserted!
        """
        if self._dongle_watcher_thread and self._dongle_watcher_thread.is_alive():
            return

        self._stop_watcher = False

        def watcher_loop():
            was_present = False
            while not self._stop_watcher:
                adapters = self.detect_wifi_adapters()
                is_present = len(adapters) > 0

                if is_present and not was_present:
                    print("[AutoConfig] USB Wi-Fi dongle connected! Automatically configuring hotspot and ICS...")
                    success, msg = self.auto_configure_system(ssid=ssid, password=password)
                    if on_status_change:
                        on_status_change(True, msg)
                    was_present = True

                elif not is_present and was_present:
                    print("[AutoConfig] USB Wi-Fi dongle removed. Pausing hotspot...")
                    self.stop_hotspot()
                    self.is_auto_configured = False
                    if on_status_change:
                        on_status_change(False, "تم فصل قطعة الواي فاي.")
                    was_present = False

                time.sleep(3)

        self._dongle_watcher_thread = threading.Thread(target=watcher_loop, daemon=True)
        self._dongle_watcher_thread.start()

    def _start_win10_mobile_hotspot(self) -> Tuple[bool, str]:
        ps_script = """
        [Windows.System.UserProfile.LockScreen,Windows.System.UserProfile,ContentType=WindowsRuntime] | Out-Null
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
        Function Await($WinRtTask, $ResultType) {
            $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
            $netTask = $asTask.Invoke($null, @($WinRtTask))
            $netTask.Wait(-1) | Out-Null
            $netTask.Result
        }
        $connectionProfile = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()
        if (-not $connectionProfile) {
            "NO_INTERNET_PROFILE"
            exit
        }
        $tetheringManager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile($connectionProfile)
        $result = Await ($tetheringManager.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
        $result.Status
        """
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            if "Success" in res.stdout:
                return True, "تم تشغيل بث ويندوز وتفعيل مشاركة الإنترنت (ICS) تلقائياً."
            return False, res.stderr or res.stdout
        except Exception as e:
            return False, str(e)

    def _stop_win10_mobile_hotspot(self):
        ps_script = """
        $connectionProfile = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()
        if ($connectionProfile) {
            $tetheringManager = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile($connectionProfile)
            $tetheringManager.StopTetheringAsync()
        }
        """
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
        except Exception:
            pass
