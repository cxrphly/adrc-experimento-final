#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.clean import cleanup
import time, csv, re, os
from datetime import datetime

cleanup()
setLogLevel('error')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)

NGINX_CONF = f'{BASE}/nginx-hls.conf'
OUTPUT = f'{BASE}/poc_qoe_resultados.csv'
SERVER_IP = '10.0.0.1'
CLIENT_IP = '10.0.0.2'
MASTER_URL = f'http://{SERVER_IP}:8080/video/master.m3u8'

QUALIDADES = {'low.m3u8': 1200, 'mid.m3u8': 4000, 'high.m3u8': 8000}
SEG_DURACAO = 2.0
STALL_THRESHOLD = 3.0
UPGRADE_FACTOR = 1.3
DOWNGRADE_FACTOR = 0.8
BOOTSTRAP_QUALITY = 'low.m3u8'

CENARIOS = [
    {'id': 'baseline', 'perda': 0, 'delay': 0, 'jitter': 0, 'warmup': 10},
    {'id': 'delay_leve', 'perda': 0, 'delay': 50, 'jitter': 5, 'warmup': 20},
    {'id': 'delay_severo', 'perda': 0, 'delay': 500, 'jitter': 20, 'warmup': 30},
    {'id': 'perda_leve', 'perda': 1, 'delay': 0, 'jitter': 0, 'warmup': 15},
    {'id': 'perda_severa', 'perda': 15, 'delay': 0, 'jitter': 0, 'warmup': 20},
    {'id': 'combinado', 'perda': 5, 'delay': 200, 'jitter': 10, 'warmup': 30},
]

REPETICOES = 5
COLETA_SEG = 60
COOLDOWN_SEG = 30
MAX_SEGMENTS = 60

PING_COUNT_NORMAL = 10
PING_COUNT_HIGH = 5
PING_INTERVAL = '0.2'

class ABR:
    def __init__(self, max_segments):
        self.throughput_history = []
        self.current_quality = BOOTSTRAP_QUALITY
        self.bitrate_history = []
        self.switch_count = 0
        self.up_switches = 0
        self.down_switches = 0
        self.segment_index = 0
        self.max_segments = max_segments

    def update_throughput(self, speed_kbps):
        self.throughput_history.append(speed_kbps)
        if len(self.throughput_history) > 5:
            self.throughput_history.pop(0)

    def choose_quality(self):
        if not self.throughput_history:
            return self.current_quality
        avg_tp = sum(self.throughput_history) / len(self.throughput_history)
        cur_bitrate = QUALIDADES[self.current_quality]
        new_quality = self.current_quality

        if avg_tp > cur_bitrate * UPGRADE_FACTOR:
            if self.current_quality == 'low.m3u8':
                new_quality = 'mid.m3u8'
            elif self.current_quality == 'mid.m3u8':
                new_quality = 'high.m3u8'
        elif avg_tp < cur_bitrate * DOWNGRADE_FACTOR:
            if self.current_quality == 'high.m3u8':
                new_quality = 'mid.m3u8'
            elif self.current_quality == 'mid.m3u8':
                new_quality = 'low.m3u8'

        if new_quality != self.current_quality:
            self.switch_count += 1
            if QUALIDADES[new_quality] > QUALIDADES[self.current_quality]:
                self.up_switches += 1
            else:
                self.down_switches += 1
        self.current_quality = new_quality
        return self.current_quality

    def get_bitrate(self):
        return QUALIDADES.get(self.current_quality, 300)

    def record_current_bitrate(self):
        if len(self.throughput_history) >= 5:
            self.bitrate_history.append(self.get_bitrate())

    def get_next_segment(self):
        seg_name = self.current_quality.replace('.m3u8', '')
        seg = f'{seg_name}{self.segment_index}.ts'
        self.segment_index = (self.segment_index + 1) % self.max_segments
        return seg

def parse_rtt(s):
    m = re.search(r'rtt.*?=\s*[\d.]+/([\d.]+)', s)
    return float(m.group(1)) if m else 999.0

def parse_jitter(s):
    m = re.search(r'rtt.*?=\s*[\d.]+/[\d.]+/[\d.]+/([\d.]+)', s)
    return float(m.group(1)) if m else 0.0

def parse_loss(s):
    m = re.search(r'(\d+(?:\.\d+)?)% packet loss', s)
    return float(m.group(1)) if m else 100.0

def aplicar_netem(cli, perda, delay, jitter):
    intf = cli.intfNames()[0]
    cli.cmd(f'tc qdisc del dev {intf} root 2>/dev/null')
    if perda == 0 and delay == 0 and jitter == 0:
        return
    partes = []
    if delay > 0 or jitter > 0:
        if jitter > 0:
            partes.append(f'delay {delay}ms {jitter}ms distribution normal')
        else:
            partes.append(f'delay {delay}ms')
    if perda > 0:
        partes.append(f'loss {perda}%')
    cli.cmd(f'tc qdisc add dev {intf} root netem {" ".join(partes)}')

def remover_netem(cli):
    intf = cli.intfNames()[0]
    cli.cmd(f'tc qdisc del dev {intf} root 2>/dev/null')

def baixar_segmento_abr(cli, abr):
    qualidade = abr.choose_quality()
    abr.record_current_bitrate()
    segmento = abr.get_next_segment()
    url = f'http://{SERVER_IP}:8080/video/{segmento}'

    curl = cli.cmd(
        f'curl -s -o /dev/null '
        f'-w "%{{time_connect}},%{{time_total}},%{{speed_download}},%{{http_code}}" '
        f'--connect-timeout 5 --max-time 20 {url}'
    ).strip()

    try:
        tc, tt, spd, code = curl.split(',')
        tc_ms = float(tc) * 1000
        tt_s = float(tt)
        spd_kbps = float(spd) * 8 / 1000
        code = code.strip()
    except Exception:
        return 9999.0, 9999.0, 0.0, '000', qualidade, abr.get_bitrate()

    if code == '200' and spd_kbps > 0:
        abr.update_throughput(spd_kbps)
    return tc_ms, tt_s, spd_kbps, code, qualidade, abr.get_bitrate()

def medir(cli, duracao, max_segments, ping_count):
    stall_events = 0
    lats, jitters, perdas = [], [], []
    goodputs, t_conns = [], []
    http_ok = http_tot = 0
    abr = ABR(max_segments)

    fim = time.time() + duracao
    while time.time() < fim:
        t0 = time.time()
        ping = cli.cmd(f'ping -c {ping_count} -i {PING_INTERVAL} -W 2 {SERVER_IP} 2>/dev/null')
        lats.append(parse_rtt(ping))
        jitters.append(parse_jitter(ping))
        perdas.append(parse_loss(ping))
        tc_ms, tt_s, spd_kbps, code, qual, bitrate = baixar_segmento_abr(cli, abr)
        http_tot += 1

        if code == '200':
            http_ok += 1
            goodputs.append(spd_kbps)
            t_conns.append(tc_ms)
            if tt_s > STALL_THRESHOLD:
                stall_events += 1
        else:
            stall_events += 1
            goodputs.append(0.0)
        elapsed = time.time() - t0
        time.sleep(max(0, 2.5 - elapsed))

    def avg(lst):
        return round(sum(lst) / len(lst), 2) if lst else 0.0

    def std(lst):
        if len(lst) < 2:
            return 0.0
        m = sum(lst) / len(lst)
        return round((sum((x - m) ** 2 for x in lst) / (len(lst) - 1)) ** 0.5, 2)

    return {
        'stall_events': stall_events,
        'avg_bitrate_selected_kbps': round(avg(abr.bitrate_history), 2),
        'quality_switches': abr.switch_count,
        'up_switches': abr.up_switches,
        'down_switches': abr.down_switches,
        'http_goodput_kbps': avg(goodputs),
        'goodput_min_kbps': round(min(goodputs), 2) if goodputs else 0.0,
        'goodput_max_kbps': round(max(goodputs), 2) if goodputs else 0.0,
        'goodput_std_kbps': std(goodputs),
        'tcp_conn_ms': avg(t_conns),
        'tcp_conn_min_ms': round(min(t_conns), 2) if t_conns else 0.0,
        'tcp_conn_max_ms': round(max(t_conns), 2) if t_conns else 0.0,
        'tcp_conn_std_ms': std(t_conns),
        'http_ok_pct': round(100 * http_ok / http_tot, 1) if http_tot else 0.0,
        'rtt_ms': avg(lats),
        'jitter_ms': avg(jitters),
        'perda_medida': avg(perdas),
        'n_amostras': http_tot,
    }

def main():
    print('\n' + '=' * 62)
    print('PoC — QoE de Streaming HLS sob Condicoes Adversas de Rede')
    print(f'{len(CENARIOS)} cenarios | {REPETICOES} reps | coleta={COLETA_SEG}s | cooldown={COOLDOWN_SEG}s')
    print('=' * 62)

    net = Mininet(link=TCLink, switch=OVSBridge)
    srv = net.addHost('server')
    cli = net.addHost('client')
    s1 = net.addSwitch('s1')
    net.addLink(srv, s1, bw=100, delay='2ms')
    net.addLink(cli, s1, bw=100, delay='2ms')
    net.start()

    srv.setIP(f'{SERVER_IP}/24')
    cli.setIP(f'{CLIENT_IP}/24')
    srv.cmd('pkill nginx 2>/dev/null; sleep 1')
    srv.cmd(f'nginx -c {NGINX_CONF} &')
    time.sleep(2)

    code = cli.cmd(f'curl -s -o /dev/null -w "%{{http_code}}" --max-time 5 {MASTER_URL}')
    if code != '200':
        print(f'[!] nginx nao respondeu (HTTP {code}) — abortando')
        net.stop()
        return

    for seg in ['low0.ts', 'mid0.ts', 'high0.ts']:
        c = cli.cmd(f'curl -s -o /dev/null -w "%{{http_code}}" --max-time 5 http://{SERVER_IP}:8080/video/{seg}').strip()
        if c != '200':
            print(f'[!] {seg} nao acessivel (HTTP {c}) — rode configurar.py')
            net.stop()
            return

    print(f'[*] nginx OK | bootstrap={BOOTSTRAP_QUALITY} | upgrade={UPGRADE_FACTOR}x | downgrade={DOWNGRADE_FACTOR}x')
    print(f'[*] Bitrates: low=1200 mid=4000 high=8000 Kbps\n')

    campos = [
        'cenario_id', 'perda_cfg', 'delay_cfg', 'jitter_cfg',
        'repeticao', 'timestamp', 'ping_count',
        'stall_events', 'avg_bitrate_selected_kbps',
        'quality_switches', 'up_switches', 'down_switches',
        'http_goodput_kbps', 'goodput_min_kbps', 'goodput_max_kbps', 'goodput_std_kbps',
        'tcp_conn_ms', 'tcp_conn_min_ms', 'tcp_conn_max_ms', 'tcp_conn_std_ms',
        'http_ok_pct', 'rtt_ms', 'jitter_ms', 'perda_medida', 'n_amostras',
    ]

    with open(OUTPUT, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()

        for c in CENARIOS:
            warmup = c.get('warmup', 30)
            ping_count = PING_COUNT_HIGH if c['delay'] >= 200 else PING_COUNT_NORMAL

            print(f'\n{"=" * 62}')
            print(f'Cenario: {c["id"]}')
            print(f'Perda={c["perda"]}% Delay={c["delay"]}ms Jitter={c["jitter"]}ms Warm-up={warmup}s Ping=-c{ping_count}')
            print('=' * 62)

            for rep in range(1, REPETICOES + 1):
                print(f'\n  [Rep {rep}/{REPETICOES}]', end='', flush=True)
                ts_inicio = datetime.now().isoformat()

                aplicar_netem(cli, c['perda'], c['delay'], c['jitter'])
                print(f' warm-up {warmup}s...', end='', flush=True)
                time.sleep(warmup)

                master_ok = cli.cmd(f'curl -s --max-time 3 {MASTER_URL}')
                if not master_ok or '#EXTM3U' not in master_ok:
                    print(f'\n  [!] master.m3u8 indisponivel na rep {rep} — pulando')
                    remover_netem(cli)
                    time.sleep(COOLDOWN_SEG)
                    continue

                print(f' coletando {COLETA_SEG}s...', end='', flush=True)
                m = medir(cli, COLETA_SEG, MAX_SEGMENTS, ping_count)

                remover_netem(cli)
                print(f' cooldown {COOLDOWN_SEG}s...', end='', flush=True)
                time.sleep(COOLDOWN_SEG)

                w.writerow({
                    'cenario_id': c['id'], 'perda_cfg': c['perda'], 'delay_cfg': c['delay'],
                    'jitter_cfg': c['jitter'], 'repeticao': rep, 'timestamp': ts_inicio,
                    'ping_count': ping_count,
                    'stall_events': m['stall_events'],
                    'avg_bitrate_selected_kbps': m['avg_bitrate_selected_kbps'],
                    'quality_switches': m['quality_switches'], 'up_switches': m['up_switches'],
                    'down_switches': m['down_switches'], 'http_goodput_kbps': m['http_goodput_kbps'],
                    'goodput_min_kbps': m['goodput_min_kbps'], 'goodput_max_kbps': m['goodput_max_kbps'],
                    'goodput_std_kbps': m['goodput_std_kbps'], 'tcp_conn_ms': m['tcp_conn_ms'],
                    'tcp_conn_min_ms': m['tcp_conn_min_ms'], 'tcp_conn_max_ms': m['tcp_conn_max_ms'],
                    'tcp_conn_std_ms': m['tcp_conn_std_ms'], 'http_ok_pct': m['http_ok_pct'],
                    'rtt_ms': m['rtt_ms'], 'jitter_ms': m['jitter_ms'],
                    'perda_medida': m['perda_medida'], 'n_amostras': m['n_amostras'],
                })
                f.flush()

                print(f'\n    stalls={m["stall_events"]} abr={m["avg_bitrate_selected_kbps"]:.0f}Kbps '
                      f'sw={m["quality_switches"]} goodput={m["http_goodput_kbps"]:.0f}Kbps '
                      f'tcp={m["tcp_conn_ms"]:.0f}ms http={m["http_ok_pct"]}% n={m["n_amostras"]}')

    net.stop()
    print(f'\n[*] Concluido -> {OUTPUT}')
    print(f'\n[*] Execute analise_poc.py')

if __name__ == '__main__':
    main()
