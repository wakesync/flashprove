"""Conditional 'multiple of plain inference' from two inputs on this branch, both named:
  (1) the merged cost model's GPU-seconds per 1,000 window tokens (experiments/20261112-7-cost-model/model-output.json,
      model.gpu_s_per_1k), extrapolated, not measured;
  (2) this experiment's route-level fitted slopes (runs/summary.json), measured, unreplicated, through the route.
Writes runs/conditional_multiple.json. Deterministic. No network.
"""
import json, pathlib
HERE = pathlib.Path(__file__).parent
cm = json.loads((HERE / '../20261112-7-cost-model/model-output.json').read_text())['model']['gpu_s_per_1k']
s = json.loads((HERE / 'runs/summary.json').read_text())
assert s['prefill']['PASS'] and s['decode']['PASS']
plain = {'prefill_s_per_1k': 1000 * s['prefill']['fit']['slope_s_per_token'],
         'decode_s_per_1k': 1000 * s['decode']['fit']['slope_s_per_token']}
out = {'inputs': {'cost_model_gpu_s_per_1k': cm, 'plain_route_s_per_1k': plain,
                  'note': 'plain = fitted slope only (per-request intercept excluded); route wall seconds, batch 1, not GPU-seconds'},
       'multiple': {}}
for T, rates in cm.items():
    for name, gpu_s in rates.items():
        out['multiple']['T%s_%s' % (T, name)] = {
            'vs_prefill_only_window': gpu_s / plain['prefill_s_per_1k'],
            'vs_decode_only_window': gpu_s / plain['decode_s_per_1k']}
(HERE / 'runs/conditional_multiple.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out, indent=2))
