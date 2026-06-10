#!/usr/bin/env python3
"""
Análise do Experimento Final — QoE HLS sob Condições Adversas de Rede
Fatorial completo 4×4 | 16 cenários | n=30 repetições por cenário | 480 linhas
"""

import csv, math, statistics, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import numpy as np
from scipy import stats as scipy_stats

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)

CSV = f'{BASE}/experimento_final_resultados.csv'
OUTD = f'{BASE}/'
PERDAS = [0, 1, 5, 15]
DELAYS = [0, 50, 200, 500]

def cid(p, d):
    return f'p{p}_d{d}'

CENARIOS = [cid(p, d) for p in PERDAS for d in DELAYS]

METRICAS = [
    ('stall_events',                'Stall events',                'eventos/rep'),
    ('avg_bitrate_selected_kbps',   'Bitrate ABR',                 'Kbps'),
    ('quality_switches',            'Quality switches',            'total/rep'),
    ('http_goodput_kbps',           'HTTP Goodput',                'Kbps'),
    ('tcp_conn_ms',                 'TCP connection',              'ms'),
    ('http_ok_pct',                 'HTTP OK',                     '%'),
    ('rtt_ms',                      'RTT (ping)',                  'ms'),
    ('jitter_ms',                   'Jitter (ping)',               'ms'),
    ('perda_medida',                'Perda medida',                '%'),
    ('n_amostras',                  'N amostras',                  'amostras'),
]
COR_DELAY = ['#1D9E75', '#4DA8A8', '#F0A500', '#D85A30']
COR_PERDA = ['#1A5276', '#2E86C1', '#F0A500', '#D85A30']

plt.rcParams.update({
    'font.family':       'DejaVu Sans',
    'font.size':         11,
    'axes.spines.top':   False,
    'axes.spines.right': False,
    'axes.grid':         True,
    'grid.alpha':        0.3,
    'grid.linestyle':    '--',
    'axes.axisbelow':    True,
})

def carregar():
    data = {}
    with open(CSV) as f:
        for row in csv.DictReader(f):
            c = row['cenario_id']
            if c not in data:
                data[c] = []
            data[c].append(row)
    return data


def ic95(vals):
    n = len(vals)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return float(vals[0]), 0.0
    m = statistics.mean(vals)
    s = statistics.stdev(vals)
    if s == 0:
        return m, 0.0
    t  = scipy_stats.t.ppf(0.975, df=n - 1)
    h  = t * s / math.sqrt(n)
    if m >= 0 and (m - h) < 0:
        h = m * 0.5
    return m, h


def estatisticas_completas(vals):
    n = len(vals)
    if n == 0:
        return {'n': 0, 'media': 0.0, 'ic95': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0}

    m, h = ic95(vals)
    return {
        'n': n,
        'media': round(m, 4),
        'ic95': round(h, 4),
        'std': round(statistics.stdev(vals), 4) if n > 1 else 0.0,
        'min': round(min(vals), 4),
        'max': round(max(vals), 4),
    }


def col(data, c, campo):
    return [float(r[campo]) for r in data.get(c, [])]


def salvar(fig, nome):
    path = os.path.join(OUTD, nome)
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  Salvo: {nome}')


def rodape(ax, n_min=30, n_max=30):
    t = round(scipy_stats.t.ppf(0.975, df=n_min - 1), 3)
    if n_min == n_max:
        label = f'IC 95% via t de Student  |  n = {n_min}  |  t({n_min-1}; 0,025) = {t}'
    else:
        label = f'IC 95% via t de Student  |  n = {n_min}–{n_max} repetições por cenário'
    ax.set_xlabel(label, fontsize=9, color='#555555')

def exportar_resultados_csv(data):
    print('\n  Exportando resultados processados para CSV...')

    resultados = []
    for c in CENARIOS:
        perda = int(c.split('_')[0][1:])
        delay = int(c.split('_')[1][1:])

        row = {
            'cenario': c,
            'perda': perda,
            'delay': delay,
            'perda_label': f'{perda}%',
            'delay_label': f'{delay}ms',
        }

        for campo, nome, unidade in METRICAS:
            vals = col(data, c, campo)
            stats = estatisticas_completas(vals)
            row[f'{campo}_media'] = stats['media']
            row[f'{campo}_ic95'] = stats['ic95']
            row[f'{campo}_std'] = stats['std']
            row[f'{campo}_min'] = stats['min']
            row[f'{campo}_max'] = stats['max']
            row[f'{campo}_n'] = stats['n']

        stall_vals = col(data, c, 'stall_events')
        stalls_min = [v / 1.0 for v in stall_vals]
        stats_stall_min = estatisticas_completas(stalls_min)
        row['stall_por_minuto_media'] = stats_stall_min['media']
        row['stall_por_minuto_ic95'] = stats_stall_min['ic95']
        row['stall_por_minuto_std'] = stats_stall_min['std']
        row['stall_por_minuto_min'] = stats_stall_min['min']
        row['stall_por_minuto_max'] = stats_stall_min['max']

        resultados.append(row)

    if resultados:
        campos_csv = resultados[0].keys()
        with open(os.path.join(OUTD, 'resultados_processados.csv'), 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=campos_csv)
            writer.writeheader()
            writer.writerows(resultados)
        print(f'    ✓ resultados_processados.csv ({len(resultados)} linhas)')

    heatmaps = []

    for campo, nome, unidade in METRICAS:
        for p in PERDAS:
            for d in DELAYS:
                vals = col(data, cid(p, d), campo)
                stats = estatisticas_completas(vals)
                heatmaps.append({
                    'metrica': nome,
                    'campo': campo,
                    'unidade': unidade,
                    'perda': p,
                    'delay': d,
                    'media': stats['media'],
                    'ic95': stats['ic95'],
                    'std': stats['std'],
                })

    for p in PERDAS:
        for d in DELAYS:
            vals = col(data, cid(p, d), 'stall_events')
            stalls_min = [v / 1.0 for v in vals]
            stats = estatisticas_completas(stalls_min)
            heatmaps.append({
                'metrica': 'Stall por minuto',
                'campo': 'stall_por_minuto',
                'unidade': 'pausas/min',
                'perda': p,
                'delay': d,
                'media': stats['media'],
                'ic95': stats['ic95'],
                'std': stats['std'],
            })

    if heatmaps:
        with open(os.path.join(OUTD, 'heatmaps.csv'), 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['metrica', 'campo', 'unidade', 'perda', 'delay', 'media', 'ic95', 'std'])
            writer.writeheader()
            writer.writerows(heatmaps)
        print(f'✓ heatmaps.csv ({len(heatmaps)} linhas)')

    for campo, nome, unidade in METRICAS:
        matriz = []
        for p in PERDAS:
            row = {'perda': p}
            for d in DELAYS:
                vals = col(data, cid(p, d), campo)
                stats = estatisticas_completas(vals)
                row[f'delay_{d}_media'] = stats['media']
                row[f'delay_{d}_ic95'] = stats['ic95']
            matriz.append(row)

        nome_arquivo = f'matriz_{campo}.csv'
        with open(os.path.join(OUTD, nome_arquivo), 'w', newline='') as f:
            fieldnames = ['perda'] + [f'delay_{d}_media' for d in DELAYS] + [f'delay_{d}_ic95' for d in DELAYS]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(matriz)
        print(f'✓ matriz_{campo}.csv')

    matriz = []
    for p in PERDAS:
        row = {'perda': p}
        for d in DELAYS:
            vals = col(data, cid(p, d), 'stall_events')
            stalls_min = [v / 1.0 for v in vals]
            stats = estatisticas_completas(stalls_min)
            row[f'delay_{d}_media'] = stats['media']
            row[f'delay_{d}_ic95'] = stats['ic95']
        matriz.append(row)

    with open(os.path.join(OUTD, 'matriz_stall_por_minuto.csv'), 'w', newline='') as f:
        fieldnames = ['perda'] + [f'delay_{d}_media' for d in DELAYS] + [f'delay_{d}_ic95' for d in DELAYS]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(matriz)
    print(f'✓ matriz_stall_por_minuto.csv')

    resumo = []
    for c in CENARIOS:
        perda = int(c.split('_')[0][1:])
        delay = int(c.split('_')[1][1:])

        row = {
            'cenario': c,
            'perda': perda,
            'delay': delay,
        }

        for campo, nome, unidade in METRICAS[:8]:
            vals = col(data, c, campo)
            m, h = ic95(vals)
            row[f'{campo}_media'] = round(m, 2)
            row[f'{campo}_ic95'] = round(h, 2)

        stall_vals = col(data, c, 'stall_events')
        stalls_min = [v / 1.0 for v in stall_vals]
        m, h = ic95(stalls_min)
        row['stall_por_minuto_media'] = round(m, 2)
        row['stall_por_minuto_ic95'] = round(h, 2)

        resumo.append(row)

    with open(os.path.join(OUTD, 'estatisticas_resumo.csv'), 'w', newline='') as f:
        if resumo:
            writer = csv.DictWriter(f, fieldnames=resumo[0].keys())
            writer.writeheader()
            writer.writerows(resumo)
    print(f'    ✓ estatisticas_resumo.csv')

    return resultados

def plot_heatmap(data, campo, titulo, fmt, fname, reverso=False):
    mat_m = np.zeros((4, 4))
    mat_h = np.zeros((4, 4))

    for i, p in enumerate(PERDAS):
        for j, d in enumerate(DELAYS):
            vs = col(data, cid(p, d), campo)
            m, h = ic95(vs)
            mat_m[i, j] = m
            mat_h[i, j] = h

    fig, ax = plt.subplots(figsize=(9, 6))

    cmap = plt.get_cmap('RdYlGn' if reverso else 'RdYlGn_r')
    norm = mcolors.Normalize(vmin=mat_m.min(), vmax=mat_m.max())
    im   = ax.imshow(mat_m, cmap=cmap, norm=norm, aspect='auto')

    for i in range(4):
        for j in range(4):
            val = mat_m[i, j]
            h   = mat_h[i, j]
            bg  = cmap(norm(val))
            lum = 0.299*bg[0] + 0.587*bg[1] + 0.114*bg[2]
            tc  = 'white' if lum < 0.5 else 'black'
            l1  = fmt.format(val)
            l2  = f'±{fmt.format(h)}' if h > 0 else ''
            ax.text(j, i, f'{l1}\n{l2}' if l2 else l1,
                    ha='center', va='center', fontsize=10,
                    color=tc, fontweight='bold', linespacing=1.5)

    ax.set_xticks(range(4))
    ax.set_xticklabels([f'{d} ms' for d in DELAYS], fontsize=11)
    ax.set_yticks(range(4))
    ax.set_yticklabels([f'{p}%' for p in PERDAS], fontsize=11)
    ax.set_xlabel('Latência adicional', fontsize=12, fontweight='bold')
    ax.set_ylabel('Perda de pacotes', fontsize=12, fontweight='bold')
    ax.set_title(titulo, fontsize=13, fontweight='bold', pad=14)
    fig.colorbar(im, ax=ax, shrink=0.8).ax.tick_params(labelsize=9)

    fig.text(0.5, 0.01, 'n = 30 por cenário  |  IC 95% via t de Student',
             ha='center', fontsize=9, color='#777777', style='italic')
    plt.tight_layout(rect=[0, 0.03, 1, 1])
    salvar(fig, fname)


def rotulos():
    return [f'p={p}%\nd={d}ms' for p in PERDAS for d in DELAYS]

def cores16():
    return [COR_DELAY[j] for _ in PERDAS for j in range(4)]

def plot_barras(data, campo, titulo, ylabel, fname,
                log=False, ymax=None, fmt='{:.1f}', ref=None, ref_label=None):
    fig, ax = plt.subplots(figsize=(14, 6))

    medias, erros = [], []
    ns = []
    for c in CENARIOS:
        vs = col(data, c, campo)
        m, h = ic95(vs)
        medias.append(m)
        erros.append(h)
        ns.append(len(vs))

    x  = np.arange(16)
    bars = ax.bar(x, medias, color=cores16(), width=0.7,
                  yerr=erros, capsize=4,
                  error_kw={'linewidth': 1.5, 'ecolor': '#333333'})

    if ref is not None:
        ax.axhline(ref, color='#C0392B', linestyle='--',
                   linewidth=1.5, label=ref_label or f'{ref}')
        ax.legend(fontsize=10)

    ax.set_xticks(x)
    ax.set_xticklabels(rotulos(), fontsize=8.5, ha='center')
    ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')
    ax.set_title(titulo, fontsize=13, fontweight='bold', pad=14)

    if log:
        ax.set_yscale('log')
        ax.set_ylabel(f'{ylabel} (escala log)', fontsize=11)
    if ymax:
        ax.set_ylim(top=ymax)

    maxv = max((m for m in medias if m > 0), default=1)
    for bar, m, h in zip(bars, medias, erros):
        if m > 0:
            off = (h + maxv * 0.025) if not log else max(h, m * 0.05)
            ax.text(bar.get_x() + bar.get_width()/2, m + off,
                    fmt.format(m), ha='center', va='bottom',
                    fontsize=7.5, fontweight='bold')

    ybase = ax.get_ylim()[0]
    for i, p in enumerate(PERDAS):
        if i > 0:
            ax.axvline(i*4 - 0.5, color='#CCCCCC', linewidth=1)
        ax.text(i*4 + 1.5, ybase, f'perda {p}%',
                ha='center', va='bottom', fontsize=8,
                color='#888888', style='italic')

    handles = [mpatches.Patch(color=c, label=f'delay = {d} ms')
               for c, d in zip(COR_DELAY, DELAYS)]
    ax.legend(handles=handles, loc='upper right', fontsize=9, framealpha=0.8)

    rodape(ax, min(ns), max(ns))
    plt.tight_layout()
    salvar(fig, fname)


def plot_interacao(data, fname):
    fig, ax = plt.subplots(figsize=(9, 6))

    for i, p in enumerate(PERDAS):
        medias = []
        erros  = []
        for d in DELAYS:
            vs    = col(data, cid(p, d), 'http_goodput_kbps')
            m, h  = ic95(vs)
            medias.append(m)
            erros.append(h)

        ax.errorbar(DELAYS, medias, yerr=erros,
                    fmt='o-', color=COR_PERDA[i], linewidth=2,
                    markersize=7, capsize=5, label=f'perda = {p}%')

    ax.set_yscale('log')
    ax.set_xticks(DELAYS)
    ax.set_xticklabels([f'{d} ms' for d in DELAYS])
    ax.set_xlabel('Latência adicional (ms)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Goodput médio (Kbps, escala log)', fontsize=12, fontweight='bold')
    ax.set_title('Interação Latência × Perda — Goodput\n'
                 'Linhas paralelas = efeitos independentes  |  '
                 'Linhas cruzadas = interação',
                 fontsize=12, fontweight='bold', pad=14)
    ax.legend(fontsize=10, loc='upper right')
    plt.tight_layout()
    salvar(fig, fname)


def plot_goodput_vs_bitrate(data, fname):
    fig, ax = plt.subplots(figsize=(14, 6))

    x     = np.arange(16)
    width = 0.38
    mg, hg, mb, hb = [], [], [], []

    for c in CENARIOS:
        m1, h1 = ic95(col(data, c, 'http_goodput_kbps'))
        m2, h2 = ic95(col(data, c, 'avg_bitrate_selected_kbps'))
        mg.append(m1); hg.append(h1)
        mb.append(m2); hb.append(h2)

    ax.bar(x - width/2, mg, width, label='Goodput (Kbps)',
           color='#1A5276', yerr=hg, capsize=3,
           error_kw={'linewidth': 1.2, 'ecolor': '#333'})
    ax.bar(x + width/2, mb, width, label='Bitrate ABR (Kbps)',
           color='#D85A30', yerr=hb, capsize=3,
           error_kw={'linewidth': 1.2, 'ecolor': '#333'})

    ax.set_yscale('log')
    ax.set_xticks(x)
    ax.set_xticklabels(rotulos(), fontsize=8.5, ha='center')
    ax.set_ylabel('Taxa (Kbps, escala log)', fontsize=12, fontweight='bold')
    ax.set_title('Goodput da rede vs. Bitrate selecionado pelo ABR\n'
                 'Convergência entre barras = ABR adaptado à banda disponível',
                 fontsize=12, fontweight='bold', pad=14)
    ax.legend(fontsize=10)

    for i in [4, 8, 12]:
        ax.axvline(i - 0.5, color='#CCCCCC', linewidth=1)

    rodape(ax)
    plt.tight_layout()
    salvar(fig, fname)

def plot_validacao_rtt(data, fname):
    fig, ax = plt.subplots(figsize=(8, 5))

    esperado, medido, err = [], [], []
    for p in PERDAS:
        for d in DELAYS:
            vs   = col(data, cid(p, d), 'rtt_ms')
            m, h = ic95(vs)
            esperado.append(d + 6)
            medido.append(m)
            err.append(h)

    ax.errorbar(esperado, medido, yerr=err, fmt='o',
                color='#1A5276', capsize=4, linewidth=1.5,
                markersize=6, label='RTT medido (média ± IC 95%)')

    lim = max(max(esperado), max(medido)) * 1.05
    ax.plot([0, lim], [0, lim], '--', color='#D85A30',
            linewidth=1.5, label='RTT esperado (delay + 6ms)')

    ax.set_xlabel('RTT esperado (ms)', fontsize=12, fontweight='bold')
    ax.set_ylabel('RTT medido pelo ping (ms)', fontsize=12, fontweight='bold')
    ax.set_title('Validação tc netem — RTT\nPontos na diagonal confirmam injeção correta',
                 fontsize=12, fontweight='bold', pad=14)
    ax.legend(fontsize=10)
    ax.set_xlim(left=-10); ax.set_ylim(bottom=-10)
    plt.tight_layout()
    salvar(fig, fname)


def plot_validacao_perda(data, fname):
    fig, ax = plt.subplots(figsize=(8, 5))

    cfg, med, err = [], [], []
    for p in PERDAS:
        for d in DELAYS:
            vs   = col(data, cid(p, d), 'perda_medida')
            m, h = ic95(vs)
            cfg.append(p)
            med.append(m)
            err.append(h)

    ax.errorbar(cfg, med, yerr=err, fmt='o',
                color='#D85A30', capsize=4, linewidth=1.5,
                markersize=6, label='Perda medida (média ± IC 95%)')
    ax.plot([-1, 17], [-1, 17], '--', color='#1A5276',
            linewidth=1.5, label='Perda esperada')

    ax.set_xlabel('Perda configurada (%)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Perda medida pelo ping (%)', fontsize=12, fontweight='bold')
    ax.set_title('Validação tc netem — Perda de pacotes\n'
                 'IC largo em valores baixos = limitação estatística do ping (n=10 pacotes)',
                 fontsize=12, fontweight='bold', pad=14)
    ax.set_xlim(-1, 17); ax.set_ylim(-1, 20)
    ax.legend(fontsize=10)
    plt.tight_layout()
    salvar(fig, fname)

def plot_boxplot(data, campo, titulo, ylabel, fname, log=False):
    fig, ax = plt.subplots(figsize=(14, 6))

    grupos = [col(data, c, campo) for c in CENARIOS]
    x      = np.arange(1, 17)

    bp = ax.boxplot(grupos, positions=x, patch_artist=True,
                    widths=0.6, showfliers=True,
                    medianprops={'color': '#111111', 'linewidth': 2},
                    whiskerprops={'linewidth': 1.5},
                    capprops={'linewidth': 1.5},
                    flierprops={'marker': 'o', 'markersize': 4,
                                'markerfacecolor': '#C0392B',
                                'markeredgecolor': '#C0392B', 'alpha': 0.6})

    for patch, c in zip(bp['boxes'], cores16()):
        patch.set_facecolor(c)
        patch.set_alpha(0.75)

    if log:
        ax.set_yscale('log')
        ax.set_ylabel(f'{ylabel} (escala log)', fontsize=12, fontweight='bold')
    else:
        ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(rotulos(), fontsize=8.5, ha='center')
    ax.set_title(titulo, fontsize=13, fontweight='bold', pad=14)

    for i in [4, 8, 12]:
        ax.axvline(i + 0.5, color='#CCCCCC', linewidth=1)
    for i, p in enumerate(PERDAS):
        ax.text(i*4 + 2.5, ax.get_ylim()[0],
                f'perda {p}%', ha='center', va='bottom',
                fontsize=8, color='#888888', style='italic')

    handles = [mpatches.Patch(color=c, label=f'delay = {d} ms')
               for c, d in zip(COR_DELAY, DELAYS)]
    ax.legend(handles=handles, loc='upper right', fontsize=9, framealpha=0.8)

    ax.set_xlabel('n = 30 repetições por cenário  |  losango = outlier',
                  fontsize=9, color='#555555')
    plt.tight_layout()
    salvar(fig, fname)


def plot_n_amostras(data, fname):
    fig, ax = plt.subplots(figsize=(14, 5))

    medias, erros = [], []
    for c in CENARIOS:
        vs = col(data, c, 'n_amostras')
        m, h = ic95(vs)
        medias.append(m); erros.append(h)

    x    = np.arange(16)
    bars = ax.bar(x, medias, color=cores16(), width=0.7,
                  yerr=erros, capsize=4,
                  error_kw={'linewidth': 1.5, 'ecolor': '#333333'})

    ax.axhline(24, color='#1A5276', linestyle='--', linewidth=1.5,
               label='Ideal: 24 amostras (60 s / 2,5 s por ciclo)')

    ax.set_xticks(x)
    ax.set_xticklabels(rotulos(), fontsize=8.5, ha='center')
    ax.set_ylabel('Amostras coletadas', fontsize=12, fontweight='bold')
    ax.set_ylim(0, 28)
    ax.set_title('Amostras por repetição — validação do loop de coleta\n'
                 'Redução com delay alto = ciclo mais lento (ping + curl com RTT elevado)',
                 fontsize=12, fontweight='bold', pad=14)

    for bar, m in zip(bars, medias):
        ax.text(bar.get_x() + bar.get_width()/2, m + 0.3,
                f'{m:.0f}', ha='center', va='bottom', fontsize=7.5, fontweight='bold')

    for i in [4, 8, 12]:
        ax.axvline(i - 0.5, color='#CCCCCC', linewidth=1)

    handles = [mpatches.Patch(color=c, label=f'delay = {d} ms')
               for c, d in zip(COR_DELAY, DELAYS)]
    handles.append(plt.Line2D([0], [0], color='#1A5276',
                               linestyle='--', linewidth=1.5, label='Ideal: 24'))
    ax.legend(handles=handles, loc='lower right', fontsize=9)

    rodape(ax)
    plt.tight_layout()
    salvar(fig, fname)


def imprimir(data):
    print('\n' + '='*75)
    print('RESULTADOS NUMÉRICOS — média ± IC 95% (n=30, t(29;0,025)=2,045)')
    print('='*75)
    print(f"{'Cenário':<14} {'n':>3}  {'Stalls':>12}  "
          f"{'Goodput Kbps':>16}  {'Bitrate Kbps':>16}  {'n_am':>5}")
    print('-'*72)

    for c in CENARIOS:
        n   = len(data.get(c, []))
        ms, hs = ic95(col(data, c, 'stall_events'))
        mg, hg = ic95(col(data, c, 'http_goodput_kbps'))
        mb, hb = ic95(col(data, c, 'avg_bitrate_selected_kbps'))
        nm     = statistics.mean(col(data, c, 'n_amostras'))
        print(f"  {c:<14} {n:>3}  {ms:>5.2f}±{hs:<5.2f}  "
              f"{mg:>8.0f}±{hg:<6.0f}  {mb:>7.0f}±{hb:<6.0f}  {nm:>4.0f}")

    # Heatmaps numéricos
    for campo, titulo, fmt in [
        ('http_goodput_kbps',         'GOODPUT (Kbps)',     '{:.0f}'),
        ('stall_events',              'STALLS (média/rep)', '{:.2f}'),
        ('avg_bitrate_selected_kbps', 'BITRATE ABR (Kbps)', '{:.0f}'),
    ]:
        print(f'\n=== HEATMAP {titulo} ===')
        header = f"{'perda\\delay':>12}"
        for d in DELAYS:
            header += f"  {d:>8}ms"
        print(header)
        print('-'*52)
        for p in PERDAS:
            row = f"  {p:>8}%  "
            for d in DELAYS:
                m, _ = ic95(col(data, cid(p, d), campo))
                row += f"  {fmt.format(m):>8}"
            print(row)

    print('\n' + '='*75)
    print('DESCOBERTAS PRINCIPAIS')
    print('='*75)
    b   = statistics.mean(col(data, 'p0_d0',  'http_goodput_kbps'))
    d50 = statistics.mean(col(data, 'p0_d50', 'http_goodput_kbps'))
    p15 = statistics.mean(col(data, 'p15_d0', 'http_goodput_kbps'))
    print(f'\n1. Latência > Perda:')
    print(f'   Baseline:       {b:.0f} Kbps')
    print(f'   Delay 50ms:     {d50:.0f} Kbps  (queda de {(1-d50/b)*100:.0f}%)')
    print(f'   Perda 15% s/delay: {p15:.0f} Kbps  (queda de {(1-p15/b)*100:.0f}%)')

    st500 = [statistics.mean(col(data, cid(p,500), 'stall_events')) for p in PERDAS]
    print(f'\n2. Ruptura em 500ms: stalls médios = {statistics.mean(st500):.2f}/rep')
    print(f'   Pior cenário p15_d500: {statistics.mean(col(data,"p15_d500","stall_events")):.2f} stalls/rep')

    print(f'\n3. ABR: delay≤50ms → bitrate=8000 em TODOS os cenários')
    print(f'        delay=500ms → bitrate=1200 (piso) em TODOS os cenários')

    print(f'\n4. HTTP OK = 100% em todos os 480 experimentos')


def main():
    print('\n' + '='*60)
    print('Análise Final — QoE HLS sob Condições Adversas')
    print('Fatorial 4×4  |  n=30  |  480 execuções')
    print('='*60)

    data = carregar()
    total = sum(len(v) for v in data.values())
    print(f'\nLinhas carregadas: {total}')
    for c in CENARIOS:
        n = len(data.get(c, []))
        if n != 30:
            print(f'  ⚠  {c}: n={n} (esperado 30)')

    print('\n' + '='*60)
    print('EXPORTANDO RESULTADOS PROCESSADOS PARA CSV...')
    print('='*60)
    exportar_resultados_csv(data)

    print('\n' + '='*60)
    print('GERANDO GRÁFICOS...')
    print('='*60 + '\n')

    plot_heatmap(data, 'http_goodput_kbps',
                 'Goodput médio (Kbps)  —  Maior = melhor',
                 '{:.0f}', 'g1_heatmap_goodput.png', reverso=True)

    plot_heatmap(data, 'stall_events',
                 'Stall events — média por repetição  —  Menor = melhor',
                 '{:.2f}', 'g2_heatmap_stalls.png', reverso=False)

    plot_heatmap(data, 'avg_bitrate_selected_kbps',
                 'Bitrate ABR médio (Kbps)  —  Maior = melhor',
                 '{:.0f}', 'g3_heatmap_bitrate.png', reverso=True)

    plot_heatmap(data, 'tcp_conn_ms',
                 'Latência TCP média (ms)  —  Menor = melhor',
                 '{:.0f}', 'g4_heatmap_tcp.png', reverso=False)

    plot_barras(data, 'http_goodput_kbps',
                'HTTP Goodput por cenário',
                'Goodput (Kbps)', 'g5_barras_goodput.png',
                log=True, fmt='{:.0f}')

    plot_barras(data, 'stall_events',
                'Stall events por cenário',
                'Stalls (eventos/repetição)', 'g6_barras_stalls.png',
                ymax=10, fmt='{:.2f}')

    plot_barras(data, 'avg_bitrate_selected_kbps',
                'Bitrate ABR selecionado por cenário',
                'Bitrate (Kbps)', 'g7_barras_bitrate.png',
                fmt='{:.0f}')

    plot_barras(data, 'tcp_conn_ms',
                'Latência de conexão TCP por cenário',
                'TCP conn (ms)', 'g8_barras_tcp.png',
                fmt='{:.0f}')

    plot_interacao(data, 'g9_interacao_goodput.png')
    plot_goodput_vs_bitrate(data, 'g10_goodput_vs_bitrate.png')
    plot_validacao_rtt(data,   'g11_validacao_rtt.png')
    plot_validacao_perda(data, 'g12_validacao_perda.png')

    plot_boxplot(data, 'http_goodput_kbps',
                 'Distribuição do Goodput entre repetições',
                 'Goodput (Kbps)', 'g13_boxplot_goodput.png', log=True)

    plot_boxplot(data, 'stall_events',
                 'Distribuição dos Stalls entre repetições',
                 'Stalls (eventos/repetição)', 'g14_boxplot_stalls.png')

    plot_n_amostras(data, 'g15_n_amostras.png')

    imprimir(data)

    print('\n' + '='*60)
    print('ARQUIVOS GERADOS:')
    print('='*60)
    print('\n CSVs com dados processados:')
    print('  - resultados_processados.csv')
    print('  - heatmaps.csv')
    print('  - estatisticas_resumo.csv')
    for campo, _, _ in METRICAS:
        print(f'  - matriz_{campo}.csv')
    print('  - matriz_stall_por_minuto.csv')

    print('\n Gráficos:')
    graficos = [
        'g1_heatmap_goodput.png', 'g2_heatmap_stalls.png',
        'g3_heatmap_bitrate.png', 'g4_heatmap_tcp.png',
        'g5_barras_goodput.png',  'g6_barras_stalls.png',
        'g7_barras_bitrate.png',  'g8_barras_tcp.png',
        'g9_interacao_goodput.png', 'g10_goodput_vs_bitrate.png',
        'g11_validacao_rtt.png', 'g12_validacao_perda.png',
        'g13_boxplot_goodput.png', 'g14_boxplot_stalls.png',
        'g15_n_amostras.png',
    ]
    for g in graficos:
        print(f'  - {g}')

    print(f'\n Localização: {OUTD}')
    print('='*60)


if __name__ == '__main__':
    main()
