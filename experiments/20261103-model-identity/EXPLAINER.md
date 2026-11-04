# Is this reply from stock weights, modified weights, or a steered run?

**This CPU experiment does not answer that with a fresh proof.** It measures reference-model scores and runs separate controls on stored proofs. The missing step is GPU commitment/proof generation. See [the complete results and receipts](RESULTS.md).

There are three different questions:

1. **Which artifact does this ID name?** For public weights, FlashProve supports deterministic `-public-weights` commitments. Publish the exact weights, conversion, configuration and 32-byte public seed file, then another party can recreate the commitment and compare the ID. This connects an ID to a specific artifact, not automatically to an authenticated "official" model. That mechanism is documented in the repository, but this lane did not rerun it. Our three reproducible SHA-256 fingerprints are ordinary artifact checksums, not commitment IDs. Public seeds also remove weight hiding.
2. **Does this reply satisfy the stock model's policy?** Exact match requires the stock integer model's greedy choices. Clipped-gap permits some deviation within an explicit budget. The question is about the output relation, not the name or intent of the system that generated the candidate reply.
3. **What physically ran at the provider?** Neither identical output nor a proof of reference-model compatibility tells you the generation process was unmodified. Runtime steering may leave tokens unchanged. A modified model can happen to produce a stock-compatible reply, and a provider can evaluate stock separately to prove it.

Here we pushed one synthetic neuron in both directions, from 5% to 100% of the layer's median residual norm, over five prompt seeds. Among 60 nonzero-dose cases, 56 replies changed. Both strict and default lenient **Python scores** rejected those 56 and accepted the four unchanged replies. The policies did not separate in this short four-token experiment. It would be wrong to advertise a verifier steering-detection threshold from that chart.

The actual C++ verifier accepted two existing fixture proofs and rejected wrong-ID and changed-token/reused-proof controls. Those show binding checks on those stored artifacts, not acceptance-policy rejection of fresh steered replies.

Next: authorize synthetic GPU proof generation, publish actual variant commitments, and test fresh proofs against each fixed stock policy. Real Qwen3.5-4B experiments remain blocked on DeltaNet architecture support. Nothing here measures real-model refusal or personality changes.
