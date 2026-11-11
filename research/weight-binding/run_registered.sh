#!/usr/bin/env bash
# The registered H2/H3 run of experiments/20261110-36-weight-binding (PREREG "Runs").
# Run from the top of the tree, through the host's heavy-job gate, pinned to the lane's cores:
#   <gate> research/weight-binding/run_registered.sh
set -eu
E=experiments/20261110-36-weight-binding
R=experiments/20261109-8-qwen-real-weights/runs
mkdir -p "$E/runs"
echo "gate granted (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$E/runs/h2h3.time"
/usr/bin/time -v taskset -c 6-11 python3 research/weight-binding/wb_int.py \
  "$R/stream-stock.json" "$R/stream-abl.json" "$E/runs/h2h3-int.json" \
  model.language_model.layers.17.mlp.down_proj.weight \
  model.language_model.layers.17.linear_attn.out_proj.weight \
  model.language_model.layers.19.self_attn.o_proj.weight \
  model.language_model.layers.34.linear_attn.out_proj.weight \
  model.language_model.layers.50.mlp.down_proj.weight \
  model.language_model.layers.51.self_attn.o_proj.weight \
  model.language_model.layers.16.mlp.down_proj.weight \
  > "$E/runs/h2h3.log" 2> "$E/runs/h2h3.stderr"
echo "finished (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$E/runs/h2h3.time"
