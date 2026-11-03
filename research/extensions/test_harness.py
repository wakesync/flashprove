# SPDX-License-Identifier: Apache-2.0
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
import harness as h

class ManifestTests(unittest.TestCase):
    def test_baseline(self):
        self.assertEqual(h.validate(h.load(Path(__file__).with_name('baseline-v1.json'))), h.validate(h.profile()))

    def test_fail_closed(self):
        mutations = {'schema':'v2', 'architecture':'GLM-5.3-Flash', 'adapter':'../../evil.py', 'proof_policy':'clipped-gap', 'protocol':'new', 'state':'unverified-prefix', 'tee':'attestation-replaces-proof', 'upstream_commit':'0'*40, 'tokenizer':{'kind':'text'}, 'operators':h.OPERATORS+['top8','KDA','mHC'], 'model':{'commitment_id':'0'*64}}
        for key,value in mutations.items():
            with self.subTest(key=key):
                m=h.profile(); m[key]=value
                with self.assertRaises(h.Unsupported): h.validate(m)
        for architecture in ['DeepSeek-V4.1-Flash','Llama-4-Maverick','toy-kda']:
            m=h.profile(); m['architecture']=architecture
            with self.assertRaises(h.Unsupported): h.validate(m)
        for field in h.profile():
            m=h.profile(); del m[field]
            with self.assertRaises(h.Unsupported): h.validate(m)
        m=h.profile(); m['unknown']=True
        with self.assertRaises(h.Unsupported): h.validate(m)
        for value in [True,64.0,128]:
            m=h.profile(); m['shape']['T']=value
            with self.assertRaises(h.Unsupported): h.validate(m)
        m=h.profile(); m['arithmetic']['rounding']='ties-even'
        with self.assertRaises(h.Unsupported): h.validate(m)

    def test_duplicate_nan(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'m.json'
            for text in ['{"schema":1,"schema":2}','{"x":NaN}']:
                p.write_text(text)
                with self.assertRaises(h.Unsupported): h.load(p)

    def test_preflight_no_launch(self):
        f=h.ROOT/'examples/accepted-proof'
        with tempfile.TemporaryDirectory() as t, patch.object(h.subprocess,'run') as run:
            for name in h.CONFIG_HASHES:
                (Path(t)/name).write_bytes((f/'config'/name).read_bytes())
            (Path(t)/'KL.bin').write_bytes(b'wrong')
            with self.assertRaises(h.Unsupported): h.verify(h.profile(),t,'','','',60,64,199)
            for r,e,y in [(60,65,199),(64,60,199),(60,64,512),(True,64,199)]:
                with self.assertRaises(h.Unsupported): h.verify(h.profile(),f/'config','','','',r,e,y)
            run.assert_not_called()

class VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (h.ROOT/'bin/cp_verify').is_file(): raise RuntimeError('build verifier/build.sh first; no silent skip')

    def check(self,response=None,start=60,next_token=199):
        f=h.ROOT/'examples/accepted-proof'
        result = h.verify(h.profile(),f/'config',f/'ivk',response or f/'example.proof',f/'example.req',start,64,next_token)
        print(f'\nCASE {self.id()} exit={result.returncode}', flush=True)
        print(result.stdout, end='', flush=True)
        print(result.stderr, end='', flush=True)
        return result

    def test_honest(self):
        r=self.check()
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('result: outcome=verified ',r.stdout)
        self.assertIn('r=60 e=64',r.stdout)

    def test_wrong_coverage(self): self.assertNotEqual(self.check(start=59).returncode,0)
    def test_wrong_next_token(self): self.assertNotEqual(self.check(next_token=198).returncode,0)

    def test_corrupt_proof(self):
        f=h.ROOT/'examples/accepted-proof'
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'example.proof'
            data=bytearray((f/'example.proof').read_bytes()); data[-20]^=1
            p.write_bytes(data); p.with_suffix('.y').write_bytes((f/'example.y').read_bytes())
            r=self.check(response=p)
            self.assertEqual(r.returncode,1,r.stdout+r.stderr)
            self.assertNotIn('outcome=verified',r.stdout)

if __name__=='__main__': unittest.main(verbosity=2)
