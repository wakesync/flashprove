#!/usr/bin/env python3
"""Plot CPU score decisions, never label these as cryptographic verifier decisions."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
numbers = json.loads((HERE / 'numbers.json').read_text())
fig, axes = plt.subplots(1, 2, figsize=(11, 5.2), sharey=True)
colors = {'strict': '#193e70', 'lenient': '#c95427'}
for ax, sign, title in zip(axes, [-1, 1], ['Negative steering', 'Positive steering']):
    rows = [r for r in numbers['dose_summary'] if r['dose'] * sign >= 0]
    rows.sort(key=lambda r: abs(r['dose']))
    xs = [abs(r['dose']) for r in rows]
    for policy, label in [('strict', 'Exact-match score'), ('lenient', 'Clipped-gap score')]:
        ys = []
        for row in rows:
            samples = [r for r in numbers['dose_rows'] if r['dose'] == row['dose'] and 'score' in r]
            ys.append(100 * sum(not r['score'][policy]['accept'] for r in samples) / len(samples)
                      if samples else float('nan'))
        ax.plot(xs, ys, 'o-' if policy == 'strict' else 's--', label=label,
                color=colors[policy], linewidth=2, markersize=6)
    ax.set_title(title, fontsize=12)
    ax.set_xlabel('Steering magnitude / median stock residual norm')
    ax.set_ylim(-5, 105)
    ax.set_xticks([0, .1, .2, .5, .8, 1.])
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.grid(alpha=.2)
    ax.spines[['top', 'right']].set_visible(False)
axes[0].set_ylabel('Replies rejected by Python score (%)')
axes[1].legend(loc='lower right', frameon=False)
fig.suptitle('Synthetic one-neuron steering: score tolerance, not proof verification', fontsize=14, y=.99)
fig.text(.5, .91, '5 fixed prompt seeds per signed dose | 4-token replies | layer 0, neuron 0',
         ha='center', fontsize=10)
fig.text(.5, .035, 'Fresh commitment IDs: 0. Fresh steered-reply proofs: 0. CPU-only proof study: KILLED.\n'
         'Real cp_verify controls check stored-proof binding only. No real-model inference claim.',
         ha='center', fontsize=9, color='#693c2b')
fig.tight_layout(rect=[0, .12, 1, .87])
fig.savefig(HERE / 'steering-score.png', dpi=180)
print('steering-score.png')
