#!/usr/bin/env python3
"""Build a diagnostic verifier using a read-only trace overlay, not a replacement verifier.

Only prints chain states and draws on a COPY of the first-round Chain. The production
sources on disk are untouched. Always compare outcomes with verifier/build.sh's binary.
Never use this diagnostic executable to handle private requests: it logs transcript state.
"""
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'bin' / 'fs-trace'
HEADER = ROOT / 'blocks/chain/rounds.h'


def main():
    original = HEADER.read_text()
    text = original
    patches = [
        ('    chain_.reset(new Chain(q));', '''    chain_.reset(new Chain(q));
    fs_label_ = q.label;
    fs_trace("start", "start", chain_->value());'''),
        ('    message_.clear();\n    roots_ = answers_ = 0;', '''    if (ok() && (closes_ == 0 || entry.name == "REPLY")) {
      fs_trace(closes_ == 0 ? "first" : "reply", entry.name.c_str(), chain_->value());
      if (closes_ == 0 && entry.draw_E) {
        Chain copy = *chain_;
        const E e = entry.draw_nonzero == entry.draw_E ? copy.draw_E_nonzero() : copy.draw_E();
        printf("FS_TRACE challenge label=%llu round=%s e=%llu,%llu,%llu\\n",
               (unsigned long long)fs_label_, entry.name.c_str(),
               (unsigned long long)e.c[0].v, (unsigned long long)e.c[1].v,
               (unsigned long long)e.c[2].v);
      }
    }
    message_.clear();
    roots_ = answers_ = 0;'''),
        ('  explicit Rounds(const Planned &plan)', '''  u64 fs_label_ = 0;
  void fs_trace(const char *phase, const char *round, const Digest &digest) const {
    u8 bytes[DIGEST_BYTES];
    digest_to_bytes(digest, bytes);
    printf("FS_TRACE %s label=%llu round=%s digest=", phase, (unsigned long long)fs_label_, round);
    for (u8 b : bytes) printf("%02x", (unsigned)b);
    printf("\\n");
  }
  explicit Rounds(const Planned &plan)'''),
    ]
    for old, new in patches:
        if text.count(old) != 1:
            raise RuntimeError('trace insertion point changed; review instrumentation')
        text = text.replace(old, new)
    overlay = OUT / 'include' / 'chain' / 'rounds.h'
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.write_text(text)
    # A distinct diagnostic digest, not the production build's identifier.
    digest = hashlib.sha256(text.encode()).hexdigest()
    flags = ['g++', '-O2', '-fno-ipa-modref', '-std=c++17', '-pthread',
             '-D_GLIBCXX_ASSERTIONS', '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=3',
             '-fstack-protector-strong', '-fstack-clash-protection',
             '-ftrivial-auto-var-init=zero', '-fPIE', '-pie',
             '-Wl,-z,relro,-z,now,-z,noexecstack', '-fcf-protection=full',
             '-DBLK_FIELD=2', '-DBLK_COUNT_HASH_CALLS=1', '-DSERVING_BUILD=1',
             '-DDIGEST_WORDS=8', f'-DVF_SOURCE_DIGEST="{digest}"',
             '-I' + str(OUT / 'include'), '-I' + str(ROOT / 'verifier/src'),
             '-I' + str(ROOT / 'blocks'), '-I' + str(ROOT / 'prover'),
             str(ROOT / 'verifier/src/cp_verify.cpp'), '-o', str(OUT / 'cp_verify_trace')]
    subprocess.run(flags, check=True)
    print('diagnostic verifier built; original rounds.h sha256=' + hashlib.sha256(original.encode()).hexdigest())


if __name__ == '__main__':
    main()
