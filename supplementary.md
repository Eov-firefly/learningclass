# Supplementary material: Budget-viable commitment

**Authors:** Ya Bai, GuoZhen Bian, Cheng Chang, ZhengGuang Cui, HaiLong Qin, ZhiHui Huang, Yue Wang

China Telecom Cloud Network Operating System R&D Center, Beijing, China

**Correspondence:** biangz@chinatelecom.cn

## Historical motivation and implementation controls

The historical stopping study used Qwen2.5-7B-Instruct-1M and Mistral-7B-Instruct-v0.3 on GSM8K and ARC-Challenge (Yang et al. 2025; Mistral AI 2024; Cobbe et al. 2021; Clark et al. 2018). Its frozen contract required the final line-start `####` answer to have a newline or EOS certificate and no later non-whitespace content. It did not validate an arbitrary surrounding document. Uniform ran to EOS or a 512-token cap; Complete returned the earliest certified terminal answer line. This is historical motivation, not a test of BVC.

**Table S1. Historical Uniform-to-Complete paired validity repairs. Each model/task cell contains 600 questions.**

| Model | Task | $n$ | Repairs | Correct | Wrong | Losses |
| --- | --- | --- | --- | --- | --- | --- |
| Mistral | ARC-C | 600 | 47 | 19 | 28 | 0 |
| Mistral | GSM8K | 600 | 129 | 81 | 48 | 0 |
| Qwen | ARC-C | 600 | 0 | 0 | 0 | 0 |
| Qwen | GSM8K | 600 | 28 | 14 | 14 | 0 |

Across 2,400 model–question pairs, 204 outputs changed from invalid to valid: 114 were correct and 90 were not. No validity loss was observed. Last-marked-answer rescoring gave zero Complete-minus-Uniform accuracy difference in all four cells; the closure-balanced heuristic produced a negative difference for Qwen/GSM8K. The old ten-table supplement remains in the repository and is retained rather than replaced by the newer task results.

The newly supplied historical raw archive contains 25,200 records: 480 pilot, 6,000 development, 14,400 main and 4,320 timing. The later three-GPU archive has 400 pilot and 10,800 formal timing records plus 480 warmups. The offline audit reproduces strict main scoring and all five archived follow-up scoring contracts. The historical parser is frozen separately because its column-start marker and numeric syntax differ from the later prototype. Historical hardware/measurement boundaries are not pooled with the new studies.

The wrapper adapter binds a complete recognized candidate and attempts only supported closing suffixes. Its reserve is 16 tokens within the 128-token wrapper cap. Candidate recognition precedes a no-candidate reserve deadline at the same step; EOS before acceptance abstains. Unsupported states abstain rather than searching for a later candidate. BVC certifies 27/32 Qwen and 30/32 Mistral wrapper requests with no legal token pruned. Format-only controls compare deterministic and model-guided completion of the same bound answer, matching acceptance and value preservation when feasible and abstaining below the minimum.

## Follow-up trajectories and full results

**Table S2. Original matched-prefix BVC/Grammar grid, $n=96$ in every row. The original cap24 option-text correct-commit endpoint remains the primary family. Other policies and costs are retained in the released all-baseline CSV.**

| Model | Encoding | Cap | BVC cert. | G cert. | BVC correct | G correct |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen | Label | 8 | 96 | 96 | 85 | 85 |
| Qwen | Label | 24 | 96 | 96 | 85 | 85 |
| Qwen | Label | 64 | 96 | 96 | 85 | 85 |
| Qwen | Option text | 8 | 84 | 69 | 54 | 54 |
| Qwen | Option text | 24 | 96 | 96 | 76 | 76 |
| Qwen | Option text | 64 | 96 | 96 | 76 | 76 |
| Mistral | Label | 8 | 96 | 96 | 66 | 66 |
| Mistral | Label | 24 | 96 | 96 | 66 | 66 |
| Mistral | Label | 64 | 96 | 96 | 66 | 66 |
| Mistral | Option text | 8 | 65 | 53 | 41 | 39 |
| Mistral | Option text | 24 | 96 | 96 | 66 | 66 |
| Mistral | Option text | 64 | 96 | 96 | 66 | 66 |

Each boundary condition reuses all 64 questions per model. The fixed8 condition is a global cap; exact-minimum and wide conditions use each case/model’s minimum and maximum canonical suffix lengths. They are structural controls, not three independent tasks or a continuous budget-response curve.

**Table S3. Native Grammar successes preserved by BVC. Counts contain repeated questions across conditions.**

| Model | Condition | G cert. | Same tokens | Added cert. | Added correct | Lost |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen | Fixed 8 | 44 | 44 | 13 | 0 | 0 |
| Qwen | Minimum | 24 | 24 | 40 | 2 | 0 |
| Qwen | Maximum | 64 | 64 | 0 | 0 | 0 |
| Mistral | Fixed 8 | 37 | 37 | 8 | 1 | 0 |
| Mistral | Minimum | 26 | 26 | 38 | 1 | 0 |
| Mistral | Maximum | 64 | 64 | 0 | 0 | 0 |

All 259 follow-up already-certified trajectories are retained; the original 96-question experiment retains 1,082 across its 12 model/encoding/cap cells. The stored returned IDs in the later fixed8 subset match the original for BVC, Grammar, XGrammar and Shortest for every model/question. These are consistency checks, not independent observations.

**Table S4. All follow-up native endpoints and token accounting, $n=64$ per row. Generated and inserted tokens are separate.**

| Model | Budget | Policy | Cert. | Correct | Wrong | Fwd | Gen. | Ins. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen | Fixed 8 | BVC | 57 | 35 | 22 | 310 | 310 | 0 |
| Qwen | Fixed 8 | Grammar | 44 | 35 | 9 | 378 | 378 | 0 |
| Qwen | Fixed 8 | Sequence score | 57 | 34 | 23 | 57 | 0 | 308 |
| Qwen | Fixed 8 | XGrammar | 39 | 31 | 8 | 417 | 417 | 0 |
| Qwen | Fixed 8 | Shortest | 57 | 9 | 48 | 0 | 0 | 273 |
| Qwen | Minimum | BVC | 64 | 19 | 45 | 341 | 341 | 0 |
| Qwen | Minimum | Grammar | 24 | 17 | 7 | 341 | 341 | 0 |
| Qwen | Minimum | Sequence score | 64 | 19 | 45 | 64 | 0 | 341 |
| Qwen | Minimum | XGrammar | 0 | 0 | 0 | 341 | 341 | 0 |
| Qwen | Minimum | Shortest | 64 | 9 | 55 | 0 | 0 | 341 |
| Qwen | Maximum | BVC | 64 | 52 | 12 | 424 | 424 | 0 |
| Qwen | Maximum | Grammar | 64 | 52 | 12 | 424 | 424 | 0 |
| Qwen | Maximum | Sequence score | 64 | 50 | 14 | 64 | 0 | 421 |
| Qwen | Maximum | XGrammar | 31 | 25 | 6 | 455 | 455 | 0 |
| Qwen | Maximum | Shortest | 64 | 9 | 55 | 0 | 0 | 341 |
| Mistral | Fixed 8 | BVC | 45 | 28 | 17 | 273 | 273 | 0 |
| Mistral | Fixed 8 | Grammar | 37 | 27 | 10 | 427 | 427 | 0 |
| Mistral | Fixed 8 | Sequence score | 45 | 27 | 18 | 45 | 0 | 274 |
| Mistral | Fixed 8 | XGrammar | 37 | 27 | 10 | 427 | 427 | 0 |
| Mistral | Fixed 8 | Shortest | 45 | 11 | 34 | 0 | 0 | 243 |
| Mistral | Minimum | BVC | 64 | 18 | 46 | 435 | 435 | 0 |
| Mistral | Minimum | Grammar | 26 | 17 | 9 | 435 | 435 | 0 |
| Mistral | Minimum | Sequence score | 64 | 17 | 47 | 64 | 0 | 435 |
| Mistral | Minimum | XGrammar | 26 | 17 | 9 | 435 | 435 | 0 |
| Mistral | Minimum | Shortest | 64 | 12 | 52 | 0 | 0 | 435 |
| Mistral | Maximum | BVC | 64 | 43 | 21 | 514 | 514 | 0 |
| Mistral | Maximum | Grammar | 64 | 43 | 21 | 514 | 514 | 0 |
| Mistral | Maximum | Sequence score | 64 | 43 | 21 | 64 | 0 | 512 |
| Mistral | Maximum | XGrammar | 63 | 43 | 20 | 514 | 514 | 0 |
| Mistral | Maximum | Shortest | 64 | 12 | 52 | 0 | 0 | 435 |

The accompanying CSV files also retain compiler time, failed-request cost, candidate suffix tokens and candidate-scoring input tokens. Candidate scoring uses one batch of feasible candidates, not one autoregressive forward per emitted token. The recorded call counts therefore do not establish proportional compute savings across these strategies.

**Table S5. Exploratory accepted-answer stability against certified Grammar outputs. Retention is same certified answer/G certified; regression and correction use offline gold only after inference.**

| Model | Budget | Policy | Retention | Lost correct | Corrected wrong |
| --- | --- | --- | --- | --- | --- |
| Qwen | Fixed 8 | BVC | 44/44 | 0 | 0 |
| Qwen | Fixed 8 | Sequence score | 41/44 | 2 | 1 |
| Qwen | Fixed 8 | Shortest | 9/44 | 29 | 3 |
| Qwen | Fixed 8 | XGrammar | 39/44 | 4 | 0 |
| Qwen | Minimum | BVC | 24/24 | 0 | 0 |
| Qwen | Minimum | Sequence score | 24/24 | 0 | 0 |
| Qwen | Minimum | Shortest | 10/24 | 11 | 0 |
| Qwen | Minimum | XGrammar | 0/24 | 17 | 0 |
| Qwen | Maximum | BVC | 64/64 | 0 | 0 |
| Qwen | Maximum | Sequence score | 58/64 | 4 | 2 |
| Qwen | Maximum | Shortest | 10/64 | 46 | 3 |
| Qwen | Maximum | XGrammar | 31/64 | 27 | 0 |
| Mistral | Fixed 8 | BVC | 37/37 | 0 | 0 |
| Mistral | Fixed 8 | Sequence score | 35/37 | 1 | 0 |
| Mistral | Fixed 8 | Shortest | 14/37 | 17 | 1 |
| Mistral | Fixed 8 | XGrammar | 37/37 | 0 | 0 |
| Mistral | Minimum | BVC | 26/26 | 0 | 0 |
| Mistral | Minimum | Sequence score | 24/26 | 1 | 0 |
| Mistral | Minimum | Shortest | 17/26 | 6 | 0 |
| Mistral | Minimum | XGrammar | 26/26 | 0 | 0 |
| Mistral | Maximum | BVC | 64/64 | 0 | 0 |
| Mistral | Maximum | Sequence score | 59/64 | 2 | 2 |
| Mistral | Maximum | Shortest | 17/64 | 32 | 1 |
| Mistral | Maximum | XGrammar | 63/64 | 0 | 0 |

The diagnostic preserves the original endpoint and raw statuses. BVC’s trajectory theorem implies complete retention under its assumptions; other policies optimize different objectives or use different tokenizations and termination. The comparison therefore measures accepted-answer stability, not overall algorithm superiority. Some alternative changes improve correctness. All repeated-question dependence and exploratory qualifications still apply.

## Reference and terminal diagnostics

At fixed8, all 13 additional Qwen and seven of eight additional Mistral native completions have over-budget canonical reference paths. The per-request table `rescued_cases.csv` gives IDs, paired request IDs, reference lengths, budgets, dead-entry steps and final outputs. Gold is used only by offline scoring. The main manuscript retains all-request endpoints rather than substituting a favorable reference-reachable subset.

**Table S6. All native versus weaker text-only endpoints. Outcome cells give count/correct count; the final column is text-valid but not committed.**

| Model | Budget | Policy | Native | Text-only | Uncommitted |
| --- | --- | --- | --- | --- | --- |
| Qwen | Fixed 8 | BVC | 57/35 | 57/35 | 0 |
| Qwen | Fixed 8 | Grammar | 44/35 | 44/35 | 0 |
| Qwen | Fixed 8 | XGrammar | 39/31 | 44/35 | 5 |
| Qwen | Minimum | BVC | 64/19 | 64/19 | 0 |
| Qwen | Minimum | Grammar | 24/17 | 24/17 | 0 |
| Qwen | Minimum | XGrammar | 0/0 | 24/17 | 24 |
| Qwen | Maximum | BVC | 64/52 | 64/52 | 0 |
| Qwen | Maximum | Grammar | 64/52 | 64/52 | 0 |
| Qwen | Maximum | XGrammar | 31/25 | 64/52 | 33 |
| Mistral | Fixed 8 | BVC | 45/28 | 45/28 | 0 |
| Mistral | Fixed 8 | Grammar | 37/27 | 43/30 | 6 |
| Mistral | Fixed 8 | XGrammar | 37/27 | 42/30 | 5 |
| Mistral | Minimum | BVC | 64/18 | 64/18 | 0 |
| Mistral | Minimum | Grammar | 26/17 | 42/28 | 16 |
| Mistral | Minimum | XGrammar | 26/17 | 42/28 | 16 |
| Mistral | Maximum | BVC | 64/43 | 64/43 | 0 |
| Mistral | Maximum | Grammar | 64/43 | 64/43 | 0 |
| Mistral | Maximum | XGrammar | 63/43 | 64/43 | 1 |

There are 106 consumer-valid but uncommitted records across all follow-up policies and repeated budget conditions. This is endpoint sensitivity, not raw corruption or new executed returns. A grammar trajectory can be canonically non-completable but already satisfy the weaker text predicate. Correctness or utility guarantees against a weaker early-return comparator do not follow from native-trajectory preservation.

## Wave-stratified descriptive timing

The original timing phase uses two sequential waves, with one Qwen and one Mistral worker per wave on distinct A800 GPUs after a resident-model barrier. Each model/wave/policy cell has 24 requests on eight questions, each repeated three times. Model/GPU identity and question shards are coupled. The two waves do not identify a wave random effect. The follow-up single-GPU measurements include correctness instrumentation; historical three-GPU measurements use a different regime.

**Table S7. Original supplied-prefix mean request time in milliseconds, by wave and policy. Means are descriptive and are not complete upstream-generation costs.**

| Wave | Model | Policy | Requests | Mean ms |
| --- | --- | --- | --- | --- |
| 0 | Mistral | BVC | 24 | 150.33 |
| 0 | Mistral | Grammar | 24 | 150.40 |
| 0 | Mistral | Sequence score | 24 | 62.70 |
| 0 | Mistral | Uniform | 24 | 149.59 |
| 0 | Mistral | XGrammar | 24 | 153.03 |
| 0 | Qwen | BVC | 24 | 120.05 |
| 0 | Qwen | Grammar | 24 | 119.99 |
| 0 | Qwen | Sequence score | 24 | 60.77 |
| 0 | Qwen | Uniform | 24 | 167.60 |
| 0 | Qwen | XGrammar | 24 | 147.45 |
| 1 | Mistral | BVC | 24 | 220.49 |
| 1 | Mistral | Grammar | 24 | 221.53 |
| 1 | Mistral | Sequence score | 24 | 62.67 |
| 1 | Mistral | Uniform | 24 | 241.28 |
| 1 | Mistral | XGrammar | 24 | 222.42 |
| 1 | Qwen | BVC | 24 | 164.49 |
| 1 | Qwen | Grammar | 24 | 163.66 |
| 1 | Qwen | Sequence score | 24 | 62.21 |
| 1 | Qwen | Uniform | 24 | 239.53 |
| 1 | Qwen | XGrammar | 24 | 189.51 |

All fixed8 follow-up and original matched-prefix baseline fields are released as CSV. No timing superiority over candidate scoring is inferred, and no timing interval is newly claimed for the historical concurrent archive. Failed attempts are retained in accounting.

## Statistical and reproducibility details

The original primary endpoint is all-request correct-commit yield in option-text cap24, assessed separately for two models. Its conservative per-cell 97.5% intervals account for the two-cell family. The follow-up fixed8 family uses feasible-subset certification, again with two model cells; its exploratory, reused-data status remains explicit. Other intervals are descriptive and unadjusted across additional settings.

For $w$ paired wins, $l$ paired losses and $n$ questions, simultaneous exact binomial bounds for win and loss probabilities use tail probability $\alpha/4$ for each bound. Subtracting the loss bounds from the win bounds yields the reported conservative paired $1-\alpha$ interval. This construction has nonzero width under zero observed discordance. It must not be replaced by a degenerate bootstrap interval or interpreted as proof of equivalence. Question pairing is retained, and model/budget repetitions do not increase the number of independent questions.

The raw archive consists of the four dated study folders. Use each raw source once: original aggregate files are byte-identical to their wave copies; existing analysis/scored JSONL files are derived, not extra requests. All 443 files listed in the provided checksum manifest passed verification. Single-study path traces are reconstructed by direct enumeration of frozen paths, independently of stored runtime distance events. This does not independently retokenize absent model files or establish complete coverage of every legal text/tokenization.

Recorded model revisions are Qwen `e28526f7bb80e2a9c8af03b831a9af3812f18fba` and Mistral `c170c708c41dac9275d15a8fff4eca08d52bab71`. Hashes of metadata and weight files agree across recorded manifests; weights themselves are absent from the bundle. Both actual schedulers and matching inference sources are provided. No shutdown, remote-control or infrastructure script is executed by the offline audit.

The public repository is <https://github.com/Eov-firefly/learningclass>. The outer raw bundle SHA-256 is

The single-GPU and two-wave inner ZIP hashes are, respectively,

>

The primary raw bundle is the dated raw ZIP at the repository root; its four folder names and nested paths are listed in the bundle README. The scripts and tables are under `research_outputs/raw_audit_20261102`. Reproduce the audit from the repository root after extracting the archive with

> audit_raw.py –bundle EXTRACTED_BUNDLE –out NEW_OUTPUT

using the script’s full repository path and Python. The audit requires numpy/scipy, not model weights or GPU inference. The historical parser snapshot records its exact origin and hash; it retains the archived column-start marker and numeric grammar. All exact command lines and machine-readable verification records accompany the repository’s audit README.

# References

<div id="refs" class="references csl-bib-body hanging-indent" entry-spacing="0">

<div id="ref-clark2018" class="csl-entry">

Clark, Peter, Isaac Cowhey, Oren Etzioni, Tushar Khot, Ashish Sabharwal, Carissa Schoenick, and Oyvind Tafjord. 2018. “Think You Have Solved Question Answering? Try ARC, the AI2 Reasoning Challenge.” *arXiv Preprint arXiv:1803.05457*. <https://arxiv.org/abs/1803.05457>.

</div>

<div id="ref-cobbe2021" class="csl-entry">

Cobbe, Karl, Vineet Kosaraju, Mohammad Bavarian, Mark Chen, Heewoo Jun, Lukasz Kaiser, Matthias Plappert, et al. 2021. “Training Verifiers to Solve Math Word Problems.” *arXiv Preprint arXiv:2110.14168*. <https://arxiv.org/abs/2110.14168>.

</div>

<div id="ref-mistral2024" class="csl-entry">

Mistral AI. 2024. “<span class="nocase">Mistral-7B-Instruct-v0.3</span> Model Card.” <https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3>.

</div>

<div id="ref-yang2025" class="csl-entry">

Yang, A. et al. 2025. “Qwen2.5-1M Technical Report.” *arXiv Preprint arXiv:2501.15383*. <https://arxiv.org/abs/2501.15383>.

</div>

</div>
