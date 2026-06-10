#!/usr/bin/env python3
import subprocess, os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)

HLS_DIR = f'{BASE}/hls/video'
NGINX_CONF = f'{BASE}/nginx-hls.conf'

BITRATES = {
    'low': {'video': 1200, 'maxrate': 1500, 'bufsize': 3000, 'audio': 96, 'res': '854x480', 'bw': 1200},
    'mid': {'video': 4000, 'maxrate': 5000, 'bufsize': 10000, 'audio': 128, 'res': '1280x720', 'bw': 4000},
    'high': {'video': 8000, 'maxrate': 10000, 'bufsize': 20000, 'audio': 192, 'res': '1920x1080', 'bw': 8000}
}

COMMON_HLS = (
    '-c:v libx264 -preset veryfast -profile:v main -level 4.0 '
    '-pix_fmt yuv420p -flags +cgop -g 60 -keyint_min 60 '
    '-sc_threshold 0 -r 30 -hls_time 2 -hls_list_size 0 '
    '-hls_playlist_type vod '
)

def run(cmd, desc, check=True):
    print(f'\n[*] {desc}')
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0 and check:
        print(f'    ERRO: {result.stderr.strip()[:200]}')
        return False
    print('    OK')
    return True

def instalar_dependencias():
    print('\n' + '='*60)
    print('FASE 1 — Instalando dependencias')
    print('='*60)
    run('sudo apt update -qq', 'apt update')
    run('sudo apt install -y mininet hping3 nginx ffmpeg curl net-tools iproute2 python3-pip',
        'Instalar pacotes do sistema')
    run('pip3 install pandas scipy matplotlib numpy --break-system-packages',
        'Instalar bibliotecas Python')
    run('sudo systemctl enable --now openvswitch-switch', 'Habilitar Open vSwitch')

def preparar_diretorios():
    print('\n' + '='*60)
    print('FASE 2 — Preparando diretorios')
    print('='*60)
    os.makedirs(HLS_DIR, exist_ok=True)
    os.makedirs(f'{BASE}/scripts', exist_ok=True)
    print(f'    OK — {HLS_DIR}')

def gerar_hls():
    print('\n' + '='*60)
    print('FASE 3 — Gerando video sintetico e segmentos HLS')
    print('='*60)

    print(f'\n    Configuracoes de qualidade:')
    print(f'    low  (480p)   : {BITRATES["low"]["video"]} Kbps video + {BITRATES["low"]["audio"]} Kbps audio')
    print(f'    mid  (720p)   : {BITRATES["mid"]["video"]} Kbps video + {BITRATES["mid"]["audio"]} Kbps audio')
    print(f'    high (1080p)  : {BITRATES["high"]["video"]} Kbps video + {BITRATES["high"]["audio"]} Kbps audio')

    print('\n    Limpando segmentos antigos...')
    for f in os.listdir(HLS_DIR):
        if f.endswith('.ts') or f.endswith('.m3u8'):
            os.remove(os.path.join(HLS_DIR, f))

    print('\n    Gerando video sintetico (Mandelbrot)...')
    run(
        f'ffmpeg -f lavfi -i "mandelbrot=size=1920x1080:rate=30" '
        f'-f lavfi -i "sine=frequency=440:sample_rate=44100" '
        f'-pix_fmt yuv420p -t 120 -c:v libx264 -c:a aac -y "{BASE}/source.mp4" -loglevel error',
        'Gerar video sintetico (120s)'
    )
    video_src = f'{BASE}/source.mp4'

    print('\n    Gerando 3 qualidades HLS...')

    ok_low = run(
        f'ffmpeg -i "{video_src}" -map 0:v -map 0:a '
        f'-b:v {BITRATES["low"]["video"]}k -maxrate {BITRATES["low"]["maxrate"]}k '
        f'-bufsize {BITRATES["low"]["bufsize"]}k -vf "scale={BITRATES["low"]["res"]}" '
        f'{COMMON_HLS} -c:a aac -b:a {BITRATES["low"]["audio"]}k '
        f'-hls_segment_filename "{HLS_DIR}/low%d.ts" "{HLS_DIR}/low.m3u8" -y -loglevel error',
        f'Gerar low ({BITRATES["low"]["video"]} Kbps / {BITRATES["low"]["res"]})'
    )

    ok_mid = run(
        f'ffmpeg -i "{video_src}" -map 0:v -map 0:a '
        f'-b:v {BITRATES["mid"]["video"]}k -maxrate {BITRATES["mid"]["maxrate"]}k '
        f'-bufsize {BITRATES["mid"]["bufsize"]}k -vf "scale={BITRATES["mid"]["res"]}" '
        f'{COMMON_HLS} -c:a aac -b:a {BITRATES["mid"]["audio"]}k '
        f'-hls_segment_filename "{HLS_DIR}/mid%d.ts" "{HLS_DIR}/mid.m3u8" -y -loglevel error',
        f'Gerar mid ({BITRATES["mid"]["video"]} Kbps / {BITRATES["mid"]["res"]})'
    )

    ok_high = run(
        f'ffmpeg -i "{video_src}" -map 0:v -map 0:a '
        f'-b:v {BITRATES["high"]["video"]}k -maxrate {BITRATES["high"]["maxrate"]}k '
        f'-bufsize {BITRATES["high"]["bufsize"]}k -vf "scale={BITRATES["high"]["res"]}" '
        f'{COMMON_HLS} -c:a aac -b:a {BITRATES["high"]["audio"]}k '
        f'-hls_segment_filename "{HLS_DIR}/high%d.ts" "{HLS_DIR}/high.m3u8" -y -loglevel error',
        f'Gerar high ({BITRATES["high"]["video"]} Kbps / {BITRATES["high"]["res"]})'
    )

    with open(f'{HLS_DIR}/master.m3u8', 'w') as f:
        f.write('#EXTM3U\n')
        f.write(f'#EXT-X-STREAM-INF:BANDWIDTH={BITRATES["low"]["bw"]*1000},RESOLUTION={BITRATES["low"]["res"]}\n')
        f.write('low.m3u8\n')
        f.write(f'#EXT-X-STREAM-INF:BANDWIDTH={BITRATES["mid"]["bw"]*1000},RESOLUTION={BITRATES["mid"]["res"]}\n')
        f.write('mid.m3u8\n')
        f.write(f'#EXT-X-STREAM-INF:BANDWIDTH={BITRATES["high"]["bw"]*1000},RESOLUTION={BITRATES["high"]["res"]}\n')
        f.write('high.m3u8\n')

    ts_count = len([f for f in os.listdir(HLS_DIR) if f.endswith('.ts')])
    print(f'\n    HLS gerado: {ts_count} segmentos em {HLS_DIR}')
    return ok_low and ok_mid and ok_high

def configurar_nginx():
    print('\n' + '='*60)
    print('FASE 4 — Configurando nginx')
    print('='*60)

    conf = f"""user root;
worker_processes auto;

events {{
    worker_connections 1024;
}}

http {{
    include /etc/nginx/mime.types;
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    keepalive_requests 1000;
    aio threads;
    access_log /tmp/nginx-hls-access.log;
    error_log /tmp/nginx-hls-error.log;

    server {{
        listen 8080;
        root {BASE}/hls;

        location / {{
            add_header Access-Control-Allow-Origin *;
            add_header Cache-Control no-cache;
            types {{
                application/vnd.apple.mpegurl m3u8;
                video/mp2t ts;
            }}
        }}
    }}
}}
"""
    with open(NGINX_CONF, 'w') as f:
        f.write(conf)

    result = subprocess.run(f'sudo nginx -c {NGINX_CONF} -t', shell=True,
                           capture_output=True, text=True)
    if 'syntax is ok' in result.stderr:
        print('    nginx config valida')
        return True
    print(f'    ERRO: {result.stderr}')
    return False

def verificar_mininet():
    print('\n' + '='*60)
    print('FASE 5 — Verificando Mininet')
    print('='*60)
    result = subprocess.run('sudo mn --test pingall 2>&1 | tail -3', shell=True,
                           capture_output=True, text=True)
    output = result.stdout + result.stderr
    if '0% dropped' in output or '2/2 received' in output:
        print('    Mininet funcionando (0% dropped)')
        return True
    print(f'    AVISO: {output.strip()[:100]}')
    return False

def resumo_final():
    print('\n' + '='*60)
    print('CONFIGURACAO CONCLUIDA')
    print('='*60)

    ts_files = [f for f in os.listdir(HLS_DIR) if f.endswith('.ts')]
    qual_files = [f for f in os.listdir(HLS_DIR) if f.endswith('.m3u8')]

    print(f'\n  Diretorio HLS : {HLS_DIR}')
    print(f'  Playlists     : {len(qual_files)} arquivos .m3u8')
    print(f'  Segmentos     : {len(ts_files)} arquivos .ts')
    print(f'  nginx config  : {NGINX_CONF}')

    print(f'\n  Qualidades HLS configuradas:')
    print(f'     LOW  (480p) : {BITRATES["low"]["video"]} Kbps')
    print(f'     MID  (720p) : {BITRATES["mid"]["video"]} Kbps')
    print(f'     HIGH (1080p): {BITRATES["high"]["video"]} Kbps')

    print(f'\n  Proximos passos:')
    print(f'  1. sudo python3 {BASE}/scripts/validar.py')
    print(f'  2. sudo python3 {BASE}/scripts/experimento_final.py')
    print(f'  3. python3 {BASE}/scripts/analise_final.py')

if __name__ == '__main__':
    print('\n' + '='*60)
    print('CONFIGURADOR DO AMBIENTE — Experimento QoE HLS')
    print('Video sintetico (Mandelbrot) | GOP fixo | Bitrates: 1200/4000/8000 Kbps')
    print('='*60)

    instalar_dependencias()
    preparar_diretorios()
    ok_hls = gerar_hls()
    ok_nginx = configurar_nginx()
    ok_mn = verificar_mininet()
    resumo_final()
    sys.exit(0 if (ok_hls and ok_nginx and ok_mn) else 1)
