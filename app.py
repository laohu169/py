#!/usr/bin/env python3
import os, re, sys, json, time, random, socket, shutil
import subprocess, threading, urllib.request
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# =========================================================
# 配置参数
# =========================================================
CONFIG = {
    'FIXED_UUID':        '807e9841-7abb-4013-91a4-3894d9e41928',
    'ARGO_TOKEN':        'eyJhIjoiY2YxMDY1YTFhZDk1YjIxNzUxNGY3MzRjNzgyYzlkMDkiLCJ0IjoiYmNiNGYxMjUtM2E3Ni00MjVlLWJiODctMDNkOGQwMmIxOGE2IiwicyI6Ik4ySTJNR0V3WTJRdE9XTTNZUzAwTmpkbExUZzVNREV0WVdVME0yVmtZbU5rTURRNSJ9',
    'ARGO_DOMAIN_FIXED': 'wasmer.cnm.ccwu.cc',
    'ARGO_PORT':         33306,
    'SINGLE_PORT_UDP':   'tuic',

    'TUIC_PORT_FIXED':   0,
    'HY2_PORT_FIXED':    0,
    'HTTP_PORT_FIXED':   0,

    'NEZHA_SERVER':      'nzmb.id.ccwu.cc:443',
    'NEZHA_KEY':         'gUxNJhaKJgceIgeapZG4956rmKFgmQgP',
    'CF_DOMAINS': [
        'cf.090227.xyz', 'cf.877774.xyz', 'cf.130519.xyz',
        'cf.008500.xyz', 'store.ubi.com', 'saas.sin.fan',
    ],
}

# =========================================================
# 工具函数
# =========================================================
def log(tag, msg): print(f'[{tag}] {msg}', flush=True)

def http_get(url, timeout=5):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.88'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode().strip()
    except Exception:
        return ''

def http_head(url, timeout=2):
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:
        return False

def is_port_free(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.3):
            return False
    except Exception:
        return True

def resolve_port(fixed):
    if fixed:
        if is_port_free(fixed):
            log('端口', f'使用固定端口: {fixed}'); return fixed
        log('警告', f'固定端口 {fixed} 已被占用，自动寻找...')
    return find_free_port()

def find_free_port():
    env_port = os.environ.get('SERVER_PORT', '') or os.environ.get('PORT', '')
    candidates = [int(p) for p in re.split(r'[,\s]+', env_port) if p.strip().isdigit()]
    for p in candidates:
        if is_port_free(p): log('成功', f'使用平台端口: {p}'); return p
        log('跳过', f'端口 {p} 已被占用')
    for _ in range(50):
        p = random.randint(20000, 39999)
        if is_port_free(p): log('成功', f'使用随机端口: {p}'); return p
    raise RuntimeError('未找到可用端口')

def download_file(url, dest):
    dest = Path(dest)
    if dest.exists() and os.access(dest, os.X_OK):
        log('下载', f'{dest} 已存在，跳过'); return
    log('下载', f'{dest} 开始...')
    def _get(u, redirect=0):
        if redirect > 5: raise Exception('重定向次数过多')
        req = urllib.request.Request(u, headers={'User-Agent': 'curl/7.88'})
        with urllib.request.urlopen(req, timeout=60) as r:
            if r.status in (301, 302, 307, 308):
                return _get(r.headers['Location'], redirect + 1)
            with open(dest, 'wb') as f:
                shutil.copyfileobj(r, f)
    _get(url)
    dest.chmod(0o755)
    log('下载', f'{dest} 完成')

# =========================================================
# 可写目录
# =========================================================
def get_file_path():
    for d in [Path.home()/'.sb-nj',
              Path(os.environ.get('XDG_CACHE_HOME','/tmp'))/'sb-nj',
              Path('/tmp/sb-nj')]:
        try: d.mkdir(parents=True, exist_ok=True); return d
        except Exception: continue
    raise RuntimeError('无法找到可写目录')

# =========================================================
# UUID
# =========================================================
def get_uuid(file_path):
    if CONFIG['FIXED_UUID']:
        log('UUID', f"使用固定 UUID: {CONFIG['FIXED_UUID']}"); return CONFIG['FIXED_UUID']
    f = file_path / 'uuid.txt'
    if f.exists():
        u = f.read_text().strip(); log('UUID', f'读取持久化 UUID: {u}'); return u
    with open('/proc/sys/kernel/random/uuid') as fp: u = fp.read().strip()
    f.write_text(u); log('UUID', f'生成新 UUID: {u}'); return u

# =========================================================
# 架构
# =========================================================
def get_arch():
    import platform
    return 'arm64' if platform.machine() == 'aarch64' else 'amd64'

# =========================================================
# CF 优选
# =========================================================
def select_cf_domain():
    log('CF优选', '测试中...')
    available = [d for d in CONFIG['CF_DOMAINS'] if http_head(f'https://{d}')]
    chosen = random.choice(available) if available else CONFIG['CF_DOMAINS'][0]
    log('CF优选', chosen); return chosen

# =========================================================
# 公网 IP
# =========================================================
def get_public_ip():
    log('网络', '获取公网 IP...')
    for url in ['https://ipv4.ip.sb','https://api.ipify.org',
                'https://ipv4.icanhazip.com','https://v4.ident.me','https://ip4.seeip.org']:
        raw = http_get(url, timeout=5)
        m = re.match(r'^(\d{1,3}(?:\.\d{1,3}){3})$', raw)
        if m: log('网络', f'公网 IP: {m.group(1)}'); return m.group(1)
    raise RuntimeError('无法获取公网 IP')

# =========================================================
# ISP
# =========================================================
def get_isp():
    try:
        raw  = http_get('https://speed.cloudflare.com/meta', timeout=2)
        org  = (re.search(r'"asOrganization":"([^"]+)"', raw) or [None,''])[1]
        city = (re.search(r'"city":"([^"]+)"', raw) or [None,''])[1]
        if org and city: return f'{org}-{city}'
    except Exception: pass
    return 'Node'

# =========================================================
# 证书
# =========================================================
def generate_cert(file_path):
    log('证书', '生成中...')
    kp = file_path / 'private.key'
    cp = file_path / 'cert.pem'
    kp.unlink(missing_ok=True)
    cp.unlink(missing_ok=True)
    try:
        subprocess.run([
            'openssl','req','-x509','-newkey','rsa:2048','-nodes','-sha256',
            '-keyout',str(kp),'-out',str(cp),'-days','3650','-subj','/CN=www.bing.com',
        ], check=True, capture_output=True)
    except Exception:
        kp.write_text(
            '-----BEGIN EC PRIVATE KEY-----\n'
            'MHcCAQEEIM4792SEtPqIt1ywqTd/0bYidBqpYV/+siNnfBYsdUYsoAoGCCqGSM49\n'
            'AwEHoUQDQgAE1kHafPj07rJG+HboH2ekAI4r+e6TL38GWASAnngZreoQDF16ARa/\n'
            'TsyLyFoPkhTxSbehH/OBEjHtSZGaDhMqQ==\n'
            '-----END EC PRIVATE KEY-----\n')
        cp.write_text(
            '-----BEGIN CERTIFICATE-----\n'
            'MIIBejCCASGgAwIBAgIUFWeQL3556PNJLp/veCFxGNj9crkwCgYIKoZIzj0EAwIw\n'
            'EzERMA8GA1UEAwwIYmluZy5jb20wHhcNMjUwMTAxMDEwMTAwWhcNMzUwMTAxMDEw\n'
            'MTAwWjATMREwDwYDVQQDDAhiaW5nLmNvbTBZMBMGByqGSM49AgEGCCqGSM49AwEH\n'
            'A0IABNZB2nz49O6yRvh26B9npACOK/nuky9/BlgEgJ54Ga3qEAxdegEWv07Mi8ha\n'
            'D5IU8Um3oR/zgRIx7UmRmg4TKkOjUzBRMB0GA1UdDgQWBBTV1cFID7UISE7PLTBR\n'
            'BfGbgrkMNzAfBgNVHSMEGDAWgBTV1cFID7UISE7PLTBRBfGbgrkMNzAPBgNVHRMB\n'
            'Af8EBTADAQH/MAoGCCqGSM49BAMCA0cAMEQCIARDAJvg0vd/ytrQVvEcSm6XTlB+\n'
            'eQ6OFb9LbLYL9Zi+AiB+foMbi4y/0YUQlTtz7as9S8/lciBF5VCUoVIKS+vX2g==\n'
            '-----END CERTIFICATE-----\n')
    log('证书', '已就绪')

# =========================================================
# Reality 密钥
# =========================================================
def get_reality_keys(file_path, sb_file):
    f = file_path / 'key.txt'
    if f.exists():
        c = f.read_text()
        priv = (re.search(r'PrivateKey:\s*(\S+)', c) or [None,None])[1]
        pub  = (re.search(r'PublicKey:\s*(\S+)',  c) or [None,None])[1]
        if priv and pub: return {'private_key': priv, 'public_key': pub}
    out = subprocess.check_output([str(sb_file), 'generate', 'reality-keypair']).decode()
    f.write_text(out)
    return {
        'private_key': re.search(r'PrivateKey:\s*(\S+)', out)[1],
        'public_key':  re.search(r'PublicKey:\s*(\S+)',  out)[1],
    }

# =========================================================
# sing-box 配置
# =========================================================
def build_singbox_config(file_path, uuid, tuic_port, hy2_port,
                         reality_port, argo_port, keys):
    cert = str(file_path / 'cert.pem')
    key  = str(file_path / 'private.key')
    inbounds = []
    if tuic_port:
        inbounds.append({
            'type':'tuic','tag':'tuic-in','listen':'::','listen_port':tuic_port,
            'users':[{'uuid':uuid,'password':'admin'}],'congestion_control':'bbr',
            'tls':{'enabled':True,'alpn':['h3'],'certificate_path':cert,'key_path':key},
        })
    if hy2_port:
        inbounds.append({
            'type':'hysteria2','tag':'hy2-in','listen':'::','listen_port':hy2_port,
            'users':[{'password':uuid}],
            'tls':{'enabled':True,'alpn':['h3'],'certificate_path':cert,'key_path':key},
        })
    if reality_port and keys:
        inbounds.append({
            'type':'vless','tag':'vless-reality-in','listen':'::','listen_port':reality_port,
            'users':[{'uuid':uuid,'flow':'xtls-rprx-vision'}],
            'tls':{'enabled':True,'server_name':'www.nazhumi.com','reality':{
                'enabled':True,'handshake':{'server':'www.nazhumi.com','server_port':443},
                'private_key':keys['private_key'],'short_id':['']}},
        })
    inbounds.append({
        'type':'vless','tag':'vless-argo-in',
        'listen':'127.0.0.1','listen_port':argo_port,
        'users':[{'uuid':uuid}],
        'transport':{'type':'ws','path':f'/{uuid}-vless'},
    })
    return json.dumps({
        'log':{'level':'warn'},'inbounds':inbounds,
        'outbounds':[{'type':'direct','tag':'direct'}],
    }, indent=2)

# =========================================================
# 生成订阅
# =========================================================
def generate_sub(file_path, uuid, public_ip, best_cf, argo_domain,
                 tuic_port, hy2_port, reality_port, keys, isp):
    lines = []
    if tuic_port:
        lines.append(f'tuic://{uuid}:admin@{public_ip}:{tuic_port}?sni=www.bing.com&alpn=h3&congestion_control=bbr&allowInsecure=1#TUIC-{isp}')
    if hy2_port:
        lines.append(f'hysteria2://{uuid}@{public_ip}:{hy2_port}/?sni=www.bing.com&insecure=1#Hysteria2-{isp}')
    if reality_port and keys:
        lines.append(f"vless://{uuid}@{public_ip}:{reality_port}?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.nazhumi.com&fp=chrome&pbk={keys['public_key']}&type=tcp#Reality-{isp}")
    if argo_domain:
        lines.append(f'vless://{uuid}@{best_cf}:443?encryption=none&security=tls&sni={argo_domain}&type=ws&host={argo_domain}&path=%2F{uuid}-vless#Argo-{isp}')
    content = '\n'.join(lines)
    (file_path / 'mvvm.txt').write_text(content)
    log('订阅内容', '\n' + content)

# =========================================================
# HTTP 订阅服务
# =========================================================
def start_http_server(file_path, uuid, http_port):
    mvvm = file_path / 'mvvm.txt'
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if '/mvvm' in self.path or f'/{uuid}' in self.path:
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                try: self.wfile.write(mvvm.read_bytes())
                except: self.wfile.write(b'error')
            else:
                self.send_response(404); self.end_headers(); self.wfile.write(b'404')
        def log_message(self, *a): pass
    server = HTTPServer(('0.0.0.0', http_port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log('HTTP', f'订阅服务已启动，端口 {http_port}')

# =========================================================
# 子进程
# =========================================================
def start_process(bin_path, args, log_file):
    with open(log_file, 'a') as f:
        return subprocess.Popen(
            [str(bin_path)] + args,
            stdout=f, stderr=f, stdin=subprocess.DEVNULL)

def start_singbox(sb_file, config_file, file_path):
    log('SING-BOX', '启动中...')
    lf = file_path / 'sb.log'
    lf.unlink(missing_ok=True)
    proc = start_process(sb_file, ['run', '-c', str(config_file)], lf)
    time.sleep(2)
    if proc.poll() is not None:
        raise RuntimeError(f"SING-BOX 启动失败:\n{lf.read_text()[-2000:] if lf.exists() else ''}")
    log('SING-BOX', f'已启动 PID: {proc.pid}')
    return proc

# =========================================================
# 哪吒 V1
# =========================================================
def start_nezha(file_path, base_url, uuid):
    if not CONFIG['NEZHA_SERVER'] or not CONFIG['NEZHA_KEY']:
        log('Nezha', '未配置，跳过'); return

    bin_p = file_path / 'nezha-agent'
    cfg   = file_path / 'config.yaml'
    lf    = file_path / 'nezha.log'

    TLS_PORTS = {443, 8443, 2096, 2087, 2083, 2053}
    port = int(CONFIG['NEZHA_SERVER'].split(':')[-1])
    tls  = 'true' if port in TLS_PORTS else 'false'

    # 强制重新下载
    bin_p.unlink(missing_ok=True)
    download_file(f'{base_url}/v1', bin_p)

    # 验证二进制
    try:
        ver = subprocess.check_output(
            [str(bin_p), '--version'], stderr=subprocess.STDOUT, timeout=5
        ).decode().strip()
        log('Nezha', f'binary: {ver}')
    except Exception as e:
        log('Nezha', f'❌ binary 无法执行: {e}'); return

    # 清空旧日志
    lf.unlink(missing_ok=True)

    # ✅ 写入配置（加 uuid 固定机器标识）
    cfg.write_text('\n'.join([
        f"client_secret: {CONFIG['NEZHA_KEY']}",
        f'uuid: {uuid}',
        'debug: true',
        'disable_auto_update: true',
        'disable_command_execute: false',
        'disable_force_update: true',
        'disable_nat: false',
        'disable_send_query: false',
        'gpu: false',
        'insecure_tls: true',
        'ip_report_period: 1800',
        'report_delay: 4',
        f"server: {CONFIG['NEZHA_SERVER']}",
        'skip_connection_count: false',
        'skip_procs_count: false',
        'temperature: false',
        f'tls: {tls}',
        'use_gitee_to_upgrade: false',
        'use_ipv6_country_code: false',
    ]))
    log('Nezha', f"配置写入完成 server={CONFIG['NEZHA_SERVER']} tls={tls} uuid={uuid}")

    proc = start_process(bin_p, ['-c', str(cfg)], lf)
    time.sleep(5)

    if proc.poll() is not None:
        err = lf.read_text() if lf.exists() else '(无日志)'
        log('Nezha', f'❌ 进程已退出 code={proc.returncode}，日志:\n{err}'); return

    latest = lf.read_text()[-1500:] if lf.exists() else ''
    log('Nezha', f'✅ 已启动 PID: {proc.pid}，近期日志:\n{latest}')

# =========================================================
# Argo 隧道
# =========================================================
def start_argo(argo_file, file_path, argo_port):
    lf = file_path / 'argo.log'
    if CONFIG['ARGO_TOKEN']:
        log('Argo', '固定隧道模式')
        log('提醒', f"配置: {CONFIG['ARGO_DOMAIN_FIXED']} → http://localhost:{argo_port}")
        token = CONFIG['ARGO_TOKEN'].replace('\r','').replace('\n','')
        proc = start_process(argo_file, [
            'tunnel','--no-autoupdate','--loglevel','info',
            '--edge-ip-version','4','--protocol','http2','run','--token',token,
        ], lf)
        time.sleep(2)
        if proc.poll() is not None:
            raise RuntimeError(f"Argo 固定隧道启动失败:\n{lf.read_text()[-3000:] if lf.exists() else ''}")
        log('Argo', f'✅ 固定隧道已启动 PID: {proc.pid}')
        return CONFIG['ARGO_DOMAIN_FIXED'], proc

    log('Argo', '临时隧道模式')
    lf.write_text('')
    proc = subprocess.Popen(
        [str(argo_file),'tunnel','--edge-ip-version','4','--protocol','http2',
         '--no-autoupdate','--url',f'http://127.0.0.1:{argo_port}'],
        stdout=open(lf,'a'), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    domain = ''
    for _ in range(45):
        time.sleep(1)
        content = lf.read_text() if lf.exists() else ''
        m = re.search(r'https://([a-zA-Z0-9-]+\.trycloudflare\.com)', content)
        if m: domain = m.group(1); break
    if not domain:
        raise RuntimeError(f"临时隧道域名获取失败:\n{lf.read_text()[-3000:] if lf.exists() else ''}")
    log('Argo', f'✅ 临时域名: {domain}')
    return domain, proc

# =========================================================
# 主函数
# =========================================================
def main():
    file_path = get_file_path()
    arch      = get_arch()
    base_url  = f'https://{arch}.ssss.nyc.mn'
    sb_file   = file_path / 'sb'
    argo_file = file_path / 'cloudflared'

    if CONFIG['ARGO_TOKEN'] and not CONFIG['ARGO_DOMAIN_FIXED']:
        raise ValueError('使用固定隧道时必须填写 ARGO_DOMAIN_FIXED')

    results = {}
    def fetch(k, fn, *a):
        try: results[k] = fn(*a)
        except Exception as e: results[k] = e

    threads = [
        threading.Thread(target=fetch, args=('ip',  get_public_ip)),
        threading.Thread(target=fetch, args=('cf',  select_cf_domain)),
        threading.Thread(target=fetch, args=('isp', get_isp)),
        threading.Thread(target=download_file, args=(f'{base_url}/sb', sb_file)),
        threading.Thread(target=download_file, args=(
            f'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}',
            argo_file)),
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    if isinstance(results.get('ip'), Exception): raise results['ip']
    public_ip = results['ip']
    best_cf   = results.get('cf', CONFIG['CF_DOMAINS'][0])
    isp       = results.get('isp', 'Node')

    argo_port    = resolve_port(CONFIG['ARGO_PORT'])
    tuic_port    = resolve_port(CONFIG['TUIC_PORT_FIXED']) if CONFIG['SINGLE_PORT_UDP'] == 'tuic' else None
    hy2_port     = resolve_port(CONFIG['HY2_PORT_FIXED'])  if CONFIG['SINGLE_PORT_UDP'] == 'hy2'  else None
    http_port    = resolve_port(CONFIG['HTTP_PORT_FIXED'])
    reality_port = None
    keys         = None

    log('端口', f"ARGO={argo_port} TUIC={tuic_port or '无'} HY2={hy2_port or '无'} HTTP={http_port}")

    uuid = get_uuid(file_path)
    generate_cert(file_path)

    if reality_port:
        log('密钥', '检查中...'); keys = get_reality_keys(file_path, sb_file); log('密钥', '已就绪')

    config_file = file_path / 'config.json'
    config_file.write_text(build_singbox_config(
        file_path, uuid, tuic_port, hy2_port, reality_port, argo_port, keys))

    sb_proc = start_singbox(sb_file, config_file, file_path)
    start_nezha(file_path, base_url, uuid)  # ✅ 传入 uuid
    argo_domain, _ = start_argo(argo_file, file_path, argo_port)

    start_http_server(file_path, uuid, http_port)
    generate_sub(file_path, uuid, public_ip, best_cf, argo_domain,
                 tuic_port, hy2_port, reality_port, keys, isp)

    print('\n===================================================')
    print(f'订阅链接: http://{public_ip}:{http_port}/mvvm')
    print(f'Argo 域名: {argo_domain}')
    print('===================================================\n')

    sb_proc.wait()
    log('主进程', f'sing-box 已退出 code={sb_proc.returncode}')

if __name__ == '__main__':
    try: main()
    except Exception as e:
        print(f'[致命错误] {e}', file=sys.stderr)
        sys.exit(1)
