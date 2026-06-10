#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.link import TCLink
from mininet.log import setLogLevel
import time, os, re, subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)

NGINX_CONF = f'{BASE}/nginx-hls.conf'
HLS_DIR = f'{BASE}/hls/video'
SERVER_IP = '10.0.0.1'
CLIENT_IP = '10.0.0.2'

passou_tudo = True

def ok(msg): print(f'  [OK] {msg}')
def falhou(msg): global passou_tudo; passou_tudo = False; print(f'  [FALHA] {msg}')
def secao(titulo): print(f'\n{"="*55}\n  {titulo}\n{"="*55}')

secao('FASE 0 — Arquivos e dependencias')

if os.path.isdir(HLS_DIR):
    ts = [f for f in os.listdir(HLS_DIR) if f.endswith('.ts')]
    m3 = [f for f in os.listdir(HLS_DIR) if f.endswith('.m3u8')]
    ok(f'HLS gerado: {len(ts)} segmentos .ts, {len(m3)} playlists') if len(ts) > 10 and len(m3) >= 4 else falhou('HLS incompleto')
else:
    falhou('Diretorio HLS nao encontrado')

if os.path.exists(NGINX_CONF):
    r = subprocess.run(f'sudo nginx -c {NGINX_CONF} -t', shell=True, capture_output=True, text=True)
    ok('nginx config valida') if 'syntax is ok' in r.stderr else falhou('nginx config invalida')
else:
    falhou('nginx-hls.conf nao encontrado')

for lib in ['pandas', 'scipy', 'matplotlib', 'numpy']:
    r = subprocess.run(f'python3 -c "import {lib}"', shell=True, capture_output=True)
    ok(f'Python: {lib} disponivel') if r.returncode == 0 else falhou(f'Python: {lib} nao instalado')

secao('FASE 1 — Ambiente Mininet')
setLogLevel('warning')

net = Mininet(link=TCLink, switch=OVSBridge)
srv = net.addHost('server')
cli = net.addHost('client')
s1 = net.addSwitch('s1')
net.addLink(srv, s1, bw=100, delay='2ms')
net.addLink(cli, s1, bw=100, delay='2ms')
net.start()
srv.setIP(f'{SERVER_IP}/24')
cli.setIP(f'{CLIENT_IP}/24')

ping = cli.cmd(f'ping -c 3 -W 1 {SERVER_IP}')
if '0% packet loss' in ping:
    m = re.search(r'rtt.*?=\s*[\d.]+/([\d.]+)', ping)
    rtt = m.group(1) if m else '?'
    ok(f'Ping OK: 0% perda, RTT avg={rtt}ms')
else:
    falhou('Ping falhou')

secao('FASE 2 — Servidor nginx + HLS')
srv.cmd('pkill nginx 2>/dev/null; sleep 1')
srv.cmd(f'nginx -c {NGINX_CONF} &')
time.sleep(2)

code = cli.cmd(f'curl -s -o /dev/null -w "%{{http_code}}" --max-time 5 http://{SERVER_IP}:8080/video/master.m3u8').strip()
ok('master.m3u8 acessivel (HTTP 200)') if code == '200' else falhou(f'master.m3u8 retornou HTTP {code}')

for qual in ['low0.ts', 'mid0.ts', 'high0.ts']:
    code = cli.cmd(f'curl -s -o /dev/null -w "%{{http_code}}" --max-time 10 http://{SERVER_IP}:8080/video/{qual}').strip()
    ok(f'{qual} OK') if code == '200' else falhou(f'{qual} HTTP {code}')

secao('FASE 3 — tc netem')
intf = cli.intfNames()[0]

r = cli.cmd(f'ping -c 5 -i 0.2 -W 1 {SERVER_IP} 2>/dev/null')
m = re.search(r'rtt.*?=\s*[\d.]+/([\d.]+)', r)
rtt_base = float(m.group(1)) if m else 999.0

cli.cmd(f'tc qdisc add dev {intf} root netem delay 100ms')
time.sleep(1)
r = cli.cmd(f'ping -c 5 -i 0.5 -W 2 {SERVER_IP} 2>/dev/null')
m = re.search(r'rtt.*?=\s*[\d.]+/([\d.]+)', r)
rtt_delay = float(m.group(1)) if m else 999.0
cli.cmd(f'tc qdisc del dev {intf} root 2>/dev/null')

delta = rtt_delay - rtt_base
ok(f'tc netem delay: +{delta:.1f}ms (esperado ~100ms)') if delta > 80 else falhou(f'tc netem delay: delta={delta:.1f}ms')

net.stop()
print(f'\n{"="*55}')
if passou_tudo:
    print('[OK] TODOS OS TESTES PASSARAM')
    print('\n  Ambiente pronto. Execute:')
    print(f'  sudo python3 {BASE}/scripts/experimento_final.py')
else:
    print('[FALHA] HA FALHAS — corrija antes de prosseguir')
print(f'{"="*55}\n')
