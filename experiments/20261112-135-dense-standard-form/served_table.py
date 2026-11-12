#!/usr/bin/env python3
"""Before/after table of the served-form planning cases (#135).

usage: served_table.py <log on main> <log on head> [<log> ...]

Each log is the output of verifier/tests/served_form_test.py. For every case the script takes what the
planning call gave (the text between the case's description and "; expected:"), and prints a Markdown
table: case, main, head, same or not. The first log is main, the second head; further logs (repeat
runs) must give, case by case, the same as one of the first two of the same binary, given in the order
main, head, main, head... Exit 0 if exactly the registered case (routed-experts.dense) differs between
main and head and every repeat agrees with its binary's first log; 1 otherwise.
"""

import re
import sys

CASE = re.compile(r"^([a-z-]+\.[A-Za-z0-9-]+): (.*): (status \d+, .*?); expected: (.*): (as expected|not as expected)$")
REGISTERED = {"routed-experts.dense"}


def read(path):
    got = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = CASE.match(line.rstrip("\n"))
            if m:
                got[m.group(1)] = m.group(3)
    return got


def main():
    logs = sys.argv[1:]
    if len(logs) < 2:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    runs = [read(p) for p in logs]
    first = {0: runs[0], 1: runs[1]}
    bad = 0
    for i, r in enumerate(runs[2:], 2):
        if r != first[i % 2]:
            bad += 1
            print("run %d (%s) differs from the first run of its binary" % (i, "main" if i % 2 == 0 else "head"))
    names = list(runs[0])
    if set(names) != set(runs[1]):
        bad += 1
        print("the two logs list different cases")
    differ = set()
    print("| case | main | head | |")
    print("|---|---|---|---|")
    for n in names:
        a, b = runs[0].get(n), runs[1].get(n)
        same = a == b
        if not same:
            differ.add(n)
        print("| `%s` | %s | %s | %s |" % (n, a, b, "same" if same else "**changed**"))
    if differ != REGISTERED:
        bad += 1
    print()
    print("served_table.py: %d cases; changed: %s; registered to change: %s; repeat runs: %d; %s"
          % (len(names), ", ".join(sorted(differ)) or "none", ", ".join(sorted(REGISTERED)), len(runs) - 2, "as registered" if not bad else "NOT as registered"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
