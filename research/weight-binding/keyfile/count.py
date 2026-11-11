#!/usr/bin/env python3
"""Count adaptation costs from merged Qwen shapes. No weights or proof run."""
import argparse
import json
import math
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE.parent))
import wb_manifest
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
source=ROOT/'experiments/20261109-8-qwen-real-weights/runs/stream-stock.json'
_,_,tensors=wb_manifest.tensors_from_stream(source)
entries=[math.prod(shape) for dtype,shape,digest in tensors.values()]
bits=[(n-1).bit_length() for n in entries]
padded=[1<<b for b in bits]
effective_path=ROOT/'experiments/20261111-91-conversion-id/runs-fix100/keyfile-count.json'
effective=json.loads(effective_path.read_text())['effective']
result=dict(kind='COUNTED, not measured; not implemented for Qwen',
            source_shapes=str(source.relative_to(ROOT)),effective_source=str(effective_path.relative_to(ROOT)),
            toy=dict(tensors=4,integers=16,linear_claims=4,point_coordinates=8,point_sha256_first_attempts=24,
                     mle_fold_multiplications=12,internal_target_bytes=96,serialized_response_bytes=0,extension_header_bytes=72),
            checkpoint_manifest_1199=dict(source_tensors=len(entries),tensor_digest_bytes=32*len(entries),
                                         merkle_internal_hashes=len(entries)-1,held_checkpoint_id_bytes=32,
                                         description='Hashes cover every source tensor, including visual/MTP/folded norms; these are not all effective table blocks.'),
            hypothetical_one_block_per_source=dict(blocks=len(entries),integers=sum(entries),padded_entries=sum(padded),
                     point_coordinates=sum(bits),point_sha256_first_attempts=3*sum(bits),mle_fold_multiplications=sum(padded)-len(entries),
                     linear_claims=len(entries),internal_target_bytes=24*len(entries),serialized_response_bytes=0),
            qwen_text_design_722=dict(blocks=effective['blocks'],integers=effective['integers'],padded_entries=effective['padded_entries'],
                     point_coordinates=effective['point_coordinates'],point_sha256_first_attempts=3*effective['point_coordinates'],
                     mle_fold_multiplications=effective['fold_mults'],linear_claims=effective['blocks'],
                     internal_target_bytes=24*effective['blocks'],serialized_response_bytes=0),
            caveats=['72-byte envelope holds tag/version and two IDs; expected values are recomputed, so no per-tensor response is serialized by this adapter.',
                     'The native WF/BATT/LIN proof size and verification time for Qwen are NOT counted or extrapolated. New sizing and tensor placement are needed.',
                     'First-attempt point hashes omit rare rejection-sampling retries; no finite exact count of retries is asserted.',
                     'The 1,199-source MLE count is hypothetical, not the Qwen conversion. The design has 722 effective text blocks; 129 text norms fold into matrices, visual/MTP are out of scope.',
                     'Integer conversion, CPU time, peak memory, hiding and soundness are not established by these counts.'])
with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps(result,indent=2))
