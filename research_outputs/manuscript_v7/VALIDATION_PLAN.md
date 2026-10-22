# Supplementary validation plan — proposed, not executed

This plan was developed during the v7 revision. It is not part of the frozen protocol for the existing experiment. Results from its application must be labeled as retrospective analyses or new experiments, as appropriate. No outcome is assumed below.

## 1. Contract robustness and paired mechanisms

Re-score the same returned outputs under the original terminal contract, the existing diagnostic extractor and explicitly specified document-structure checks. Keep the original endpoint unchanged. Specify extraction precedence, allowed choices, newline and EOS handling, wrappers, repeated markers and invalid outcomes before examining aggregate differences for each added contract. Report validity, correctness, paired wins/losses and uncertainty for all model–task cells rather than selecting favorable cells.

Audit every discordant correctness pair. Classify post-answer wrapper closure, explanatory continuation, repeated markers, answer revision, cap-related incompleteness and unresolved cases. Release inspectable examples with both returned texts and scoring decisions. Examine early wrong answers that are corrected later as a direct challenge to universal correctness preservation. Human semantic assessment must be reported separately from automated contract validity.

## 2. Trajectory and gate verification

Validate exact token prefixes, Complete–Shadow identity and the stopping-time ordering on per-call records. Answer agreement is insufficient. Explicitly record EOS and generated-versus-returned token conventions. Where paths diverge, report the divergence and do not attribute that subset using the shared-trajectory argument.

For conjunction, inspect the completion indicator, minimum-step gate, entropy stability gate and final decision at each step. Count completion opportunities, gate occupancy, overlap and blocking reasons. Distinguish a policy event at EOS from an event that terminates strictly earlier. If entropy traces were not saved, decoded text alone cannot reconstruct them; diagnostic re-execution must be identified as new work.

Run targeted single-factor ablations for thresholds, minimum steps, stability windows, candidate-prefix handling and decision indexing. Preserve the original Legacy results under their original identifier. A revised implementation is a new policy, not a replacement of frozen evidence. A latched design must specify whether it returns current text or a buffered prefix and account for all computation already spent.

## 3. Practical controls and runtime robustness

Compare against an actual usable boundary-stop implementation. If Complete is already equivalent to that implementation, acknowledge equivalence rather than creating a nominally different baseline. A boundary-observation arm that does not stop can help distinguish detection cost from saved generation. Retain an entropy-observation contrast with exact output matching.

Repeat isolated timing in independently initialized sessions, preserving order, warmup, synchronization and runtime metadata. Choose further sample sizes from a declared meaningful effect and observed variance components rather than claiming that the existing number of repetitions guarantees adequate power. Report session-specific contrasts as well as pooled uncertainty appropriate to the sampling design. Profiling runs should be separate from primary timing if instrumentation changes execution cost.

## 4. Semantic assessment and broader claims

For the existing proposed human audit, preserve independent blinded ratings, sampling strata, inclusion probabilities and pre-adjudication records. A disagreement-enriched sample does not support an unweighted population estimate. Broader multi-budget, model, backend or concurrency experiments are warranted only for correspondingly broader claims.

## 5. Reproducible evidence

Provide the runner, parsers, environment versions, frozen protocol and execution receipts, question manifests, raw outputs, failed/retried-call records and analysis scripts. Reconstruct all five existing tables before adding new summaries. Verify new multiple-comparison families or label exploratory intervals explicitly. Keep private audit keys and credentials outside the release. File hashes verify artifact consistency, not experimental validity.
