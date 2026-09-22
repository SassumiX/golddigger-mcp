#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate radar chart images for each buyer"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.patches import Polygon
import os

OUTPUT_DIR = "/workspace/radar_charts"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 关闭中文字体警告
plt.rcParams['font.family'] = 'DejaVu Sans'

BUYERS = [
    {
        'name': 'Afrimat Limited',
        'country': 'South Africa',
        'score': 91,
        'color': '#DC2626',
        'axes': ['Purchase\nPower', 'Company\nScale', 'Demand\nUrgency', 'Repeat\nPotential', 'Region\nMatch', 'Contact\nEase'],
        'values': [95, 90, 88, 90, 88, 85],
    },
    {
        'name': 'White Rock Minerals',
        'country': 'UAE',
        'score': 88,
        'color': '#2563EB',
        'axes': ['Purchase\nPower', 'Company\nScale', 'Demand\nUrgency', 'Repeat\nPotential', 'Region\nMatch', 'Contact\nEase'],
        'values': [80, 82, 85, 88, 92, 78],
    },
    {
        'name': 'Bin Harkil Group',
        'country': 'Saudi Arabia',
        'score': 85,
        'color': '#C9812A',
        'axes': ['Purchase\nPower', 'Company\nScale', 'Demand\nUrgency', 'Repeat\nPotential', 'Region\nMatch', 'Contact\nEase'],
        'values': [82, 85, 90, 78, 95, 72],
    },
]

def draw_radar_chart(buyer, filename):
    n = len(buyer['axes'])
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    values = buyer['values']
    # 闭合
    angles += angles[:1]
    values = values + [values[0]]

    fig, ax = plt.subplots(figsize=(5.5, 5.5), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor('#F9FAFB')
    ax.set_facecolor('#F9FAFB')

    color = buyer['color']

    # 背景网格 - 5层
    for level in [20, 40, 60, 80, 100]:
        ax.plot(angles, [level]*len(angles), color='#E5E7EB', linewidth=0.5, linestyle='--', zorder=0)
    # 最外层实线
    ax.plot(angles, [100]*len(angles), color='#D1D5DB', linewidth=1, zorder=0)

    # 填充区域
    ax.fill(angles, values, color=color, alpha=0.15, zorder=1)
    ax.fill(angles, [v + 5 for v in values], color=color, alpha=0.05, zorder=0)

    # 数据折线
    ax.plot(angles, values, color=color, linewidth=2.5, linestyle='-',
            marker='o', markersize=6, markerfacecolor='white',
            markeredgecolor=color, markeredgewidth=2, zorder=3)

    # 刻度标签
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(buyer['axes'], size=9, color='#374151', fontweight='bold')

    # 径向刻度
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'],
                       size=7, color='#9CA3AF')
    ax.set_ylim(0, 110)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    # 标题区域
    ax.set_title(
        f"{buyer['name']}\n"
        f"{buyer['country']}  ·  Score: {buyer['score']}/100",
        size=13, fontweight='bold', color='#1A1A2E',
        pad=20, y=1.08
    )

    # 外边框
    ax.spines['polar'].set_visible(False)

    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight',
                facecolor='#F9FAFB', edgecolor='none')
    plt.close()
    print(f"  ✅ {filename}")

# 综合对比雷达图 - 3人叠加
def draw_comparison_radar(filename):
    n = 6
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    labels = ['Purchase\nPower', 'Company\nScale', 'Demand\nUrgency',
              'Repeat\nPotential', 'Region\nMatch', 'Contact\nEase']
    angles_full = angles + angles[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor('#F9FAFB')
    ax.set_facecolor('#F9FAFB')

    colors = ['#DC2626', '#2563EB', '#C9812A']
    all_values = [
        [95, 90, 88, 90, 88, 85],  # Afrimat
        [80, 82, 85, 88, 92, 78],   # White Rock
        [82, 85, 90, 78, 95, 72],   # Bin Harkil
    ]
    names = ['Afrimat (91)', 'White Rock (88)', 'Bin Harkil (85)']

    # 背景网格
    for level in [20, 40, 60, 80, 100]:
        ax.plot(angles_full, [level]*len(angles_full), color='#E5E7EB', linewidth=0.5, linestyle='--')
    ax.plot(angles_full, [100]*len(angles_full), color='#D1D5DB', linewidth=1)

    for i, (values, color, name) in enumerate(zip(all_values, colors, names)):
        v = values + [values[0]]
        ax.fill(angles_full, v, color=color, alpha=0.12)
        ax.plot(angles_full, v, color=color, linewidth=2, marker='o',
                markersize=5, markerfacecolor='white', markeredgecolor=color,
                markeredgewidth=1.5, label=name, zorder=3-i)

    ax.set_xticks(angles)
    ax.set_xticklabels(labels, size=8.5, color='#374151', fontweight='bold')
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], size=7, color='#9CA3AF')
    ax.set_ylim(0, 110)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.spines['polar'].set_visible(False)

    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1),
              fontsize=9, framealpha=0.8, edgecolor='#E5E7EB')
    ax.set_title('Three-Buyer Comparison Radar\n综合对比雷达图',
                 size=13, fontweight='bold', color='#1A1A2E', pad=20)

    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight', facecolor='#F9FAFB')
    plt.close()
    print(f"  ✅ {filename}")


print("生成雷达图...")
for buyer in BUYERS:
    fname = f"{OUTPUT_DIR}/{buyer['name'].replace(' ', '_').lower()}_radar.png"
    draw_radar_chart(buyer, fname)

draw_comparison_radar(f"{OUTPUT_DIR}/comparison_radar.png")
print("全部完成 ✅")
