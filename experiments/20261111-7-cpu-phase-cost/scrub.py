#!/usr/bin/env python3
"""Make the runner's log publishable: the runner wrote absolute paths of the clone into each child's
argv. This replaces the clone's absolute root with "." (repository-relative) and changes nothing else.
  scrub.py <raw runs.jsonl> <out runs.jsonl>
The output records the raw file's SHA-256 and the number of replaced occurrences in a first line.
"""
import hashlib, json, pathlib, sys
root = str(pathlib.Path(__file__).resolve().parents[2])
src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
raw = src.read_bytes()
text = raw.decode()
n = text.count(root)
out = text.replace(root, '.')
assert '/home/' not in out
head = json.dumps(dict(event='scrubbed', raw_sha256=hashlib.sha256(raw).hexdigest(), raw_lines=text.count('\n'),
                       replaced=n, rule='absolute clone root replaced by "." in argv; nothing else changed'))
dst.write_text(head + '\n' + out)
print(head)
