"""Amendment 5: derive, from the verifier sources at the checked-out head, which rejection names can be
printed only by code that runs AFTER the test shape-heads (cp_verify.cpp:525-526) in a
`cp_verify -plan request ... -arrays` call. Reads files only, runs nothing.

A refusal site is a call refuse("<literal>" ...), refuse(<prefix> + ...), refuse(G_ + "<literal>"),
or tblHeld(k, hh, "<literal>"). A name (or a prefix for names built at run time) is AFTER only if
every one of its sites is in an AFTER region:
  cp_verify.cpp lines 527..839  (rest of layout(), which shape-heads is in)
  cp_verify.cpp lines 1192..1206 (polLayout() after its call of layout() at :1191)
  cp_verify.cpp lines 1345..2558 (runStage() after its call of polLayout() at :1344, to its end)
  vf_attention_shape.h, vf_attention_check.h, vf_lookup_argument.h, vf_layers_check.inc,
  vf_layers_plan.inc, vf_output_head_check.inc, vf_output_head_plan.inc, vf_smallness_test.h,
  vf_smallness_test_members.inc, vf_segments.inc (only reached from those regions: forestShape()
  :812, AttentionSubProof::plan() :1991, the *.inc files included at :2104-2105, :2190-2191, :2196).
Conservative on purpose: a function defined before :526 but called only later (tensorsAgree :98,
called at :2003) still disqualifies its name, so such a name is not counted.
Every other site (cp_verify.cpp outside those ranges, any other file) disqualifies the name.
Names beginning internal- are left out (the walk counts them as unchecked). Also listed: names
with a site in the region that runs BEFORE shape-heads, for the record.
Usage: derive_counted_names.py CHECKOUT OUT.json"""
import json, pathlib, re, sys

C = pathlib.Path(sys.argv[1])
S = C / "verifier/src"
AFTER_FILES = {"vf_attention_shape.h", "vf_attention_check.h", "vf_lookup_argument.h", "vf_layers_check.inc",
               "vf_layers_plan.inc", "vf_output_head_check.inc", "vf_output_head_plan.inc", "vf_smallness_test.h",
               "vf_smallness_test_members.inc", "vf_segments.inc"}
CP_AFTER = [(527, 839), (1192, 1206), (1345, 2558)]
site_re = [
    (re.compile(r'\brefuse\(\s*(?:G_\s*\+\s*|prefix\s*\+\s*)?"([^"]+)"\s*(\+)?'), 1),
    (re.compile(r'\brefuse\(\s*string\("([^"]+)"\)\s*(\+)?'), 1),
    (re.compile(r'\btblHeld\(\s*\d+\s*,\s*\w+\s*,\s*"([^"]+)"\s*\)'), 1),
]
sites = {}  # key: (name, is_prefix) -> list of (file, line)
for p in sorted(S.iterdir()):
    if p.suffix not in (".h", ".cpp", ".inc"):
        continue
    for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
        code = line.split("//")[0]
        for rx, _ in site_re:
            for m in rx.finditer(code):
                name = m.group(1)
                pref = bool(m.lastindex and m.lastindex >= 2 and m.group(2)) or name.endswith("-")
                sites.setdefault((name, pref), []).append((p.name, i))


def after(f, i):
    if f == "cp_verify.cpp":
        return any(a <= i <= b for a, b in CP_AFTER)
    return f in AFTER_FILES


def before(f, i):
    return f == "cp_verify.cpp" and (i <= 526 or 840 <= i <= 1191 or 1207 <= i <= 1344 or i > 2558)


# a name's every site, including sites of a prefix that the name starts with, and of the exact name
out = {"after_exact": {}, "after_prefix": {}, "not_after": {}, "rule": __doc__.split("Usage")[0].strip()}
keys = sorted(sites)
for (name, pref) in keys:
    if name.startswith("internal-"):
        continue
    every = list(sites[(name, pref)])
    # any other site whose name could print the same text: an exact name starting with this prefix,
    # or a prefix that this name starts with
    for (n2, p2) in keys:
        if (n2, p2) == (name, pref):
            continue
        if (pref and n2.startswith(name)) or (p2 and name.startswith(n2)):
            every += sites[(n2, p2)]
    rec = ["%s:%d" % s for s in sites[(name, pref)]]
    if all(after(f, i) for f, i in every):
        out["after_prefix" if pref else "after_exact"][name] = rec
    else:
        out["not_after"][name + ("*" if pref else "")] = ["%s:%d%s" % (f, i, " (before)" if before(f, i) else "") for f, i in every]
pathlib.Path(sys.argv[2]).write_text(json.dumps(out, indent=1, sort_keys=True))
print("after, exact:", len(out["after_exact"]), "after, prefixes:", len(out["after_prefix"]), "not after:", len(out["not_after"]))
print("prefixes:", sorted(out["after_prefix"]))
print("exact:", sorted(out["after_exact"]))
print("not after:", sorted(out["not_after"]))
