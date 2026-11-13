#!/usr/bin/env python3
"""Layer-set rule of PREREG Amendment A-1, applied mechanically. No other input than the fixture's timing and the clock.

  projected_s = (672 / 512) * (48 * t_delta + 16 * t_attn)
      t_delta, t_attn: the fixture's 512-token probe times (all arms) of stock layer 0 (DeltaNet) and layer 3 (attention)
  available_s = min(4800 - seconds since the slot grant, seconds to 2026-11-13T00:05:00Z) - 120
  projected_s > available_s  ->  r33 (arms on R33, baseline on all 64 layers), else full.

Refuses (exit 2) unless the fixture reports ok. Appends its inputs and its choice to the progress log, prints the choice.
Usage: decide_set.py <fixture.json> <grant time, UTC, %Y-%m-%dT%H:%M:%SZ> <progress.log>"""
import calendar, json, sys, time

fx = json.load(open(sys.argv[1])); grant = sys.argv[2]; logf = sys.argv[3]
ts = lambda s: calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))
now = time.time(); stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))


def log(msg):
    with open(logf, "a") as f: f.write(msg + "\n")


if not fx.get("ok"):
    log(f"decide_set: fixture NOT ok, registered run not started {stamp}"); sys.exit(2)
t = {r["layer"]: r["probe_512tok_layer_s"] for r in fx["timing"]}
proj = 672 / 512 * (48 * t[0] + 16 * t[3])
avail = min(4800 - (now - ts(grant)), ts("2026-11-13T00:05:00Z") - now) - 120
choice = "full" if proj <= avail else "r33"
log(f"decide_set: layer set {choice}; projected {proj:.0f} s for 64 layers, available {avail:.0f} s; t_delta {t[0]} s, t_attn {t[3]} s "
    f"(512-token fixture probe); fixture ok; grant {grant}; {stamp}")
print(choice)
