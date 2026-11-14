#!/usr/bin/env python3
"""Run a command under the PREREG's stop rules: log the slot grant time, then kill the child (by pid, SIGTERM then
SIGKILL, its whole process group) if its process-tree RSS exceeds the limit, or at the elapsed budget, or at the hard
stop, whichever comes first. Polls every 2 s. Also refuses to start under the MemAvailable floor.

Usage: watchdog.py <log> <budget_min> <hard_stop_utc> <rss_gb> <memavail_floor_gb> -- <command...>
"""
import calendar, json, os, signal, subprocess, sys, time

def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def memavail_gb():
    for l in open("/proc/meminfo"):
        if l.startswith("MemAvailable:"): return int(l.split()[1]) / 1e6
    return 0.0

def tree_rss_gb(root):
    kids = {}
    for p in os.listdir("/proc"):
        if not p.isdigit(): continue
        try:
            st = open(f"/proc/{p}/stat").read(); ppid = int(st.rsplit(")", 1)[1].split()[1]); kids.setdefault(ppid, []).append(int(p))
        except Exception: pass
    tot, todo = 0, [root]
    while todo:
        p = todo.pop()
        try:
            for l in open(f"/proc/{p}/status"):
                if l.startswith("VmRSS:"): tot += int(l.split()[1])
        except Exception: pass
        todo += kids.get(p, [])
    return tot / 1e6

def main():
    a = sys.argv; i = a.index("--")
    logp, budget, hard, rss_lim, floor = a[1], float(a[2]), a[3], float(a[4]), float(a[5]); cmd = a[i + 1:]
    hard_t = calendar.timegm(time.strptime(hard, "%Y-%m-%dT%H:%M:%SZ"))
    t0 = time.time(); stop_t = min(t0 + budget * 60, hard_t)
    log = lambda o: open(logp, "a").write(json.dumps(o) + "\n")
    ma = memavail_gb()
    log(dict(t=now(), slot_granted=True, memavailable_gb=round(ma, 2), budget_min=budget, hard_stop=hard,
             stop_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stop_t)), rss_limit_gb=rss_lim, cmd=[os.path.basename(c) for c in cmd]))
    if ma < floor: log(dict(t=now(), refused="MemAvailable under floor")); sys.exit(5)
    if time.time() >= stop_t: log(dict(t=now(), refused="past stop time")); sys.exit(5)
    p = subprocess.Popen(cmd, start_new_session=True); peak = 0.0; why = None
    log(dict(t=now(), child_pid=p.pid))
    while p.poll() is None:
        r = tree_rss_gb(p.pid); peak = max(peak, r)
        if r > rss_lim: why = f"rss {r:.2f} GB > {rss_lim}"
        elif time.time() >= stop_t: why = "time stop"
        if why:
            log(dict(t=now(), kill=why, pid=p.pid))
            try: os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            for _ in range(10):
                if p.poll() is not None: break
                time.sleep(1)
            if p.poll() is None:
                try: os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            break
        time.sleep(2)
    rc = p.wait()
    log(dict(t=now(), exit=rc, killed=why, peak_tree_rss_gb=round(peak, 2), elapsed_s=round(time.time() - t0, 1)))
    sys.exit(rc if why is None else 9)

if __name__ == "__main__":
    main()
