#!/usr/bin/env python3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(SCRIPT_DIR)

CSV = f'{BASE}/poc_qoe_resultados.csv'
OUTD = f'{BASE}/'

TEMPO_COLETA_SEG = 60
TEMPO_COLETA_MIN = 1

CENARIOS = ['baseline', 'delay_leve', 'delay_severo', 'perda_leve', 'perda_severa', 'combinado']
ROTULOS = ['Baseline', 'Delay 50ms', 'Delay 500ms', 'Perda 1%', 'Perda 15%', 'Combinado']
CORES = ['#1D9E75', '#4DA8A8', '#1A5276', '#F0A500', '#D85A30', '#7D3C98']

def ic95(serie):
    s = pd.Series(serie).dropna()
    n = len(s)
    if n < 2:
        return s.mean() if len(s) > 0 else 0, 0.0
    m = s.mean()
    sem = stats.sem(s)
    if sem == 0:
        return m, 0.0
    t_crit = stats.t.ppf(0.975, df=n-1)
    h = sem * t_crit
    if m - h < 0 and m >= 0:
        h = m * 0.5
    return m, h

def preparar_dados():
    df = pd.read_csv(CSV)
    df['stall_por_minuto'] = df['stall_events'] / TEMPO_COLETA_MIN
    return df

def plot_barras(df, coluna, titulo, ylabel, fname, log=False, ymax=None):
    fig, ax = plt.subplots(figsize=(10, 6))
    medias, erros = [], []
    for cid in CENARIOS:
        sub = df[df['cenario_id'] == cid]
        m, h = ic95(sub[coluna]) if len(sub) > 0 else (0, 0)
        medias.append(m); erros.append(h)

    x = np.arange(len(CENARIOS))
    bars = ax.bar(x, medias, color=CORES, width=0.6, yerr=erros, capsize=5)
    ax.set_xticks(x)
    ax.set_xticklabels(ROTULOS, fontsize=10, rotation=15, ha='right')
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(titulo, fontsize=13, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)
    if log:
        ax.set_yscale('log')
    if ymax:
        ax.set_ylim(top=ymax)

    for bar, m in zip(bars, medias):
        if m > 0:
            ax.text(bar.get_x() + bar.get_width()/2, m + max(medias)*0.02,
                   f'{m:.1f}', ha='center', va='bottom', fontsize=9)

    n_reps = df.groupby('cenario_id').size().max()
    ax.set_xlabel(f'n = {n_reps} repeticoes | IC 95% via t de Student', fontsize=9)
    plt.tight_layout()
    plt.savefig(f'{OUTD}{fname}', dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  Salvo: {fname}')

def main():
    print('\n' + '='*60)
    print('ANALISE DA PROVA DE CONCEITO - QoE HLS')
    print('6 cenarios | 5 repeticoes | IC 95% via t de Student')
    print('='*60)

    df = preparar_dados()
    print(f'\nDados carregados: {len(df)} amostras')
    print(f'Repeticoes por cenario: {df.groupby("cenario_id").size().iloc[0]}')

    print('\nGERANDO GRAFICOS...\n')

    plot_barras(df, 'stall_por_minuto', 'Stall events por minuto', 'Stalls/min', 'poc_g1_stalls.png', ymax=8)
    plot_barras(df, 'avg_bitrate_selected_kbps', 'Bitrate ABR', 'Kbps', 'poc_g2_bitrate_abr.png')
    plot_barras(df, 'quality_switches', 'Quality switches', 'Switches', 'poc_g3_switches.png')
    plot_barras(df, 'http_goodput_kbps', 'HTTP Goodput', 'Kbps', 'poc_g4_goodput.png', log=True)
    plot_barras(df, 'tcp_conn_ms', 'Latencia TCP', 'ms', 'poc_g5_tcp_latencia.png')
    plot_barras(df, 'rtt_ms', 'RTT medido - Validacao', 'ms', 'poc_g6_rtt.png')
    plot_barras(df, 'perda_medida', 'Perda medida - Validacao', '%', 'poc_g7_perda.png', ymax=20)

    print('\n' + '='*60)
    print('RESULTADOS NUMERICOS')
    print('='*60)

    for cid in CENARIOS:
        sub = df[df['cenario_id'] == cid]
        if len(sub) == 0:
            continue
        print(f'\n{cid}')
        print('-' * 40)
        m, h = ic95(sub['stall_por_minuto'])
        print(f'  Stalls:      {m:.2f} +- {h:.2f} pausas/min')
        m, h = ic95(sub['avg_bitrate_selected_kbps'])
        print(f'  Bitrate ABR: {m:.0f} +- {h:.0f} Kbps')
        m, h = ic95(sub['http_goodput_kbps'])
        print(f'  Goodput:     {m:.0f} +- {h:.0f} Kbps')
        m, h = ic95(sub['tcp_conn_ms'])
        print(f'  TCP conn:    {m:.0f} +- {h:.0f} ms')
        m, h = ic95(sub['rtt_ms'])
        print(f'  RTT:         {m:.0f} +- {h:.0f} ms')

    print(f'\nGRAFICOS SALVOS EM: {OUTD}')
    print('='*60)

if __name__ == '__main__':
    main()
