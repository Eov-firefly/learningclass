# Terminal-answer contracts and monitoring cost in token-limited LLM inference

Ya Bai, GuoZhen Bian*, Cheng Chang, ZhengGuang Cui, HaiLong Qin, ZhiHui Huang, Yue Wang

China Telecom Cloud Network Operating System R&D Center, Beijing, China

* Correspondence: biangz@chinatelecom.cn

Revision dated 22 October 2026. Research manuscript draft; author metadata, declarations and public archive location require author confirmation before submission.

## Abstract

Output-token allowances do not directly measure the cost of delivering an acceptable answer. We evaluate how answer-boundary stopping and entropy monitoring interact with a prespecified terminal-answer contract in two instruction-tuned language models on GSM8K and ARC-Challenge. A frozen protocol produced 25,200 scored inference calls, including 14,400 main calls and 4,320 calls in a separate, isolated timing experiment. Six policies distinguish a no-monitor baseline, marker-only truncation, a legacy entropy rule, answer-line completion, entropy shadow monitoring, and an entropy/completion conjunction. On 600 held-out questions per task, completion stopping changed contract accuracy by 2.33, 0.00, 13.50 and 3.17 percentage points for Qwen/GSM8K, Qwen/ARC-Challenge, Mistral/GSM8K and Mistral/ARC-Challenge, respectively, while reducing mean output tokens by 0.00%-2.59%. Every additional credited answer arose from preserving the terminal contract rather than correcting an incorrect baseline prediction. A shadow monitor produced exactly the same token sequences as completion stopping but added 16.46-51.18 ms per call (0.38%-1.24%) in isolated measurements. The tested legacy entropy rule saved few tokens while lowering contract accuracy and increasing mean latency. The conjunction usually matched Uniform's EOS-or-cap termination because entropy stability and the transient answer boundary did not coincide. These results identify a measurable interaction between a stopping rule, its parser and its runtime cost. They support boundary-aware implementation checks and output-invariant monitoring controls, rather than claims of general reasoning improvement, physical resource allocation or universal speedup. Independent human semantic assessment remains pending; all quality claims refer to the specified contract.

Keywords: large language models; stopping criteria; inference evaluation; answer extraction; entropy monitoring; reproducibility

## 1. Introduction

Early stopping is useful only if it reduces the cost of delivering an answer that an application can accept. A limit such as 512 output tokens is an allowance, whereas actual generated tokens and elapsed time are observations. A second distinction concerns what counts as an answer. A permissive extractor may recover a correct number from an unfinished response; a structured interface may require an identifiable, complete final answer. Evaluating an efficiency intervention therefore requires a matched baseline, a declared output contract, and measurement of the intervention's own cost.

A consequential case occurs when the model has already emitted an acceptable final line. Continuing generation can add explanatory text, close a formatting wrapper, or introduce another marker. Under a terminal-answer contract, continuation may invalidate a previously acceptable suffix. Conversely, a monitor waiting for an entropy condition may miss the brief boundary at which stopping was possible. This temporal interaction between rule and parser cannot be diagnosed adequately by reporting only an average token reduction or permissive extraction accuracy.

This study began with an implementation audit of JANUS, an earlier token-budget experiment. Its tested code did not implement the proposed joint scheduling mechanism: TCJS and TokOnly used identical generation paths. That audit motivated an explicitly narrower, prospective evaluation. The present work evaluates six implemented policies in two models and two tasks, adds an output-invariant shadow control, and measures latency separately on an isolated GPU. We evaluate single-request generation. These benchmark questions are not tool-using agents, multi-agent workflows or directed acyclic graphs.

The research questions are: (RQ1) how does stopping at an observable answer boundary affect terminal-contract accuracy and actual token consumption; (RQ2) how much time does entropy monitoring add when output is held fixed; and (RQ3) does adding an entropy condition retain completion stopping's behavior? The contribution is a reproducible comparison separating contract preservation, monitoring overhead and stopping effectiveness. Neither truncation error nor the distinction between allowance and consumption is presented as a new principle.

### 1.1. Related work and scope

Budget-aware reasoning compares alternative uses of inference computation. Wang et al. (2024) evaluate reasoning strategies under token budgets, while Han et al. (2025) study token-budget-aware reasoning through budget estimation and prompting. Muennighoff et al. (2025) investigate test-time scaling with trained reasoning models and budget forcing. Our intervention is narrower: a stopping callback in ordinary greedy generation from instruction-tuned models. We do not reproduce those algorithms or claim a competitive state-of-the-art result against them.

Answer extraction is a substantive component of evaluation. Yu et al. (2025) study automated extraction for reliable evaluation in xFinder. Our fixed parsers serve a different purpose: one defines an interface contract, while a permissive parser provides a diagnostic sensitivity analysis. Neither is a semantic oracle. GSM8K (Cobbe et al., 2021) and ARC (Clark et al., 2018) supply two answer types, numeric and multiple-choice, but do not span open-ended reasoning or deployed serving workloads.

## 2. Materials and methods

### 2.1. Frozen design and sampling

The executed specification was `janus-prospective-v5.1-cap512-reduced`, with seed 20261019 and one output allowance, 512 tokens. Input preparation, an independent implementation pilot, development diagnostics, the main evaluation and isolated timing were separate stages. The pilot checked implementation and provenance gates, rather than a significance threshold or minimum improvement. The execution chain, gate receipts and formal analyses completed successfully. The archived protocol's pre-execution wording is preserved as provenance; dated execution receipts and raw records establish the completed work.

GSM8K used `openai/gsm8k`, configuration `main`, revision `740312add88f781978c0658806c59bc2815b9866`. ARC-Challenge used `allenai/ai2_arc`, configuration `ARC-Challenge`, revision `210d026faf9955653af8916fad021475a3f00453`. Development contained 300 training questions per task; the held-out evaluation contained 600 test questions per task. Exact prompt duplicates and development/test overlap were checked. The 582 GSM8K test questions touched by historical JANUS work were excluded before drawing the new cohort from the remaining 737 eligible questions. ARC sampling used 1,172 eligible test questions. Deterministic manifests record the resulting membership.

The pilot used the first 20 development questions per task. Timing used the first 60 main questions per task, with three repetitions per policy. Thus pilot and timing are nested diagnostic subsets, not independent accuracy replications. Both models answered the same cohorts. There are 1,200 distinct main question identities, 600 per task; the 14,400 main calls arise from two models and six policies. Calls and repetitions do not substitute for independent questions in uncertainty estimates.

Table 1. Executed scored-call counts. Main and pilot evaluate six policies; development evaluates Uniform, Complete and three conjunction thresholds. Warmup calls are outside these counts.

| Stage | Questions per task/model | Settings | Repeats | Scored calls |
| --- | --- | --- | --- | --- |
| Implementation pilot | 20 | 6 | 1 | 480 |
| Development diagnostic | 300 | 5 | 1 | 6,000 |
| Main evaluation | 600 | 6 | 1 | 14,400 |
| Isolated timing | 60 | 6 | 3 | 4,320 |
| Total | - | - | - | 25,200 |

Development thresholds were 0.005, 0.01 and 0.05. The frozen rule selected 0.01 a priori for the prospective conjunction; development did not optimize the reported main threshold. The selection record and guard verify this choice. The legacy threshold remained 0.05. No prospective budget sweep, fitted allocation curve, transfer study or scheduling experiment was executed in this reduced design.

### 2.2. Models, prompts and generation

The models were Qwen2.5-7B-Instruct-1M (Yang et al., 2025), revision `e28526f7bb80e2a9c8af03b831a9af3812f18fba`, and Mistral-7B-Instruct-v0.3 (Mistral AI, 2024), revision `c170c708c41dac9275d15a8fff4eca08d52bab71`. We used each tokenizer's native chat template with a generation prompt and one user message, without in-context examples. Model revision pins were recorded; weight bytes were not independently rehashed.

The numeric instruction ended: Solve the problem step by step. End with a final line exactly "#### <number>" using a signed integer or decimal, no units or commas. Put a newline after the final line. ARC used the analogous instruction with the instance's allowed choice letters. The exact prompts, question text and choices are reconstructible from input manifests and the runner. Prompts and generation settings were identical across policies for a question.

Generation used BF16, Transformers SDPA, batch size one, greedy decoding, one beam, cache enabled, repetition penalty 1.0, no forced EOS token and no minimum new-token requirement. Every policy performed real inference; outputs were not reconstructed by truncating a saved baseline. Each call recorded generated token IDs, text, token count, stop reason, parser outcomes, timing and provenance. Token counts include an emitted EOS token. Deterministic algorithms were not enabled, so observed identity checks describe these runs rather than a guarantee across kernels or hardware.

### 2.3. Terminal-answer contract and diagnostic extraction

The prespecified primary quality endpoint is boundary-certified terminal-marker contract accuracy, shortened below to contract accuracy. The parser locates the last line-start `####` marker. Numeric values must be signed integers or decimals; commas, units and scientific notation are excluded. ARC values must be an allowed choice letter. After that value, the suffix may contain whitespace only. Online completion requires a newline after the value. Offline validity additionally requires either EOS termination or a newline-terminated terminal answer in the returned text. The scorer recomputes this boundary from the returned text rather than reading a stored completion event. A numeric fragment at the cap without either certificate is not credited.

A valid answer is correct if its value, compared as a decimal or choice letter, equals the gold answer. Validity is reported separately from correctness. The same parser scores every main policy, including Uniform. This endpoint measures compliance with a specific terminal interface, not correctness under arbitrary extraction conventions.

The parser does not validate document syntax before the marker. A marked line inside an unclosed LaTeX display or code fence can satisfy the contract when stopped after its newline. Later closing that wrapper can invalidate the terminal suffix. This behavior is central to interpreting the results: a caller requiring well-formed Markdown or LaTeX needs a different contract and a new evaluation.

A legacy-style extractor supplies diagnostic sensitivity scores. GSM8K extraction prioritizes a marked number, then a boxed answer, answer-like phrases or equalities, and finally a trailing number. The ARC diagnostic uses the last standalone A-E letter without filtering to the instance's allowed choices; it is not a historical JANUS parser. These scores describe extraction outcomes and do not establish that incomplete or contradictory text is semantically acceptable.

### 2.4. Implemented stopping policies

Uniform (U) runs to model EOS or the 512-token cap without entropy monitoring. Marker (M) stops at the first observed `####` substring without requiring a value or newline. Marker is a deliberately incomplete negative control, not a proposed usable efficiency method.

Complete (C) stops at the earliest online boundary satisfying the marked answer-line contract. It does not calculate entropy. Shadow (S; code identifier `entropy_observe`) computes entropy diagnostics but uses the Complete stopping rule. Its runtime contrast with Complete isolates the tested monitoring path only if generated token IDs match. A mechanism audit checks that condition.

Legacy entropy (L) calculates full-vocabulary next-token entropy, H = -sum(p log(p + 10^-12)), from pre-token logits. Successive entropy differences are smoothed with coefficient 2/11. After the minimum-step gate, it requires five consecutive stable steps with absolute smoothed difference below 0.05, five identical nonempty legacy answer candidates, and an observed marked or boxed answer. The retained legacy candidate prefix includes the final prompt token. Trigger decisions are applied after the subsequent generated token. The code and traces preserve this timing detail; it is not a completed-answer guarantee.

Conjunction (E; `entropy_complete`) requires at least 21 generated steps, five stable entropy steps at threshold 0.01, and a complete answer boundary at the current step. Completion is not latched: an earlier acceptable line is insufficient if later text changes the suffix. The tested mechanism therefore requires simultaneous completion and stability. Entropy callbacks return the logits unchanged. EOS has priority in stop-reason classification. Exact gates, indexing and special-token handling are executable in `core.py` and `engine.py`.

### 2.5. Hardware and timing

Quality stages used two NVIDIA A800 80 GB PCIe GPUs, one model per GPU. Only the isolated stage supports our latency conclusions. In timing, models ran sequentially on the same physical GPU without other GPU inference jobs. Each model had 24 warmup calls, two per task/policy, for 48 timing warmups. Jobs were shuffled by the frozen seed within each model session; the saved order was independently reconstructed. Qwen ran on 21 October 2026 from 14:07 to 16:26 UTC, followed by Mistral from 16:29 to 19:17 UTC. Model-session order was not counterbalanced.

The runtime used Python 3.11.12, PyTorch 2.6.0+cu124, CUDA 12.4, driver 570.211.01, Transformers 4.48.2, Datasets 3.2.0, NumPy 1.26.4 and SciPy 1.14.1. Timing used two PyTorch CPU threads and 64 interop threads. TF32 matrix multiplication and cuDNN benchmarking were disabled; Flash, memory-efficient and mathematical SDPA backends were enabled. Environment snapshots are archived.

Generation time starts after input preparation and a CUDA synchronization and ends after generation and final synchronization. End-to-end time starts before chat templating, tokenization and device transfer, and ends after generation, synchronization, token-ID transfer and decoding. It excludes model loading, warmup, scoring, logging, network transport and queues. It is a local request interval, not deployed service latency or throughput. Full-vocabulary entropy and scalar transfers introduce GPU/CPU synchronization; measured overhead includes these implementation choices and Python callbacks. It is not a hardware lower bound on entropy estimation.

### 2.6. Analysis and computational verification

Analyses pair policies by question within model and task. The four primary Complete-minus-Uniform accuracy comparisons form one family. Each uses a conservative 98.75% interval, giving at least 95% family coverage by Bonferroni adjustment. The paired binary interval bounds win and loss probabilities using simultaneous one-sided Clopper-Pearson bounds. The frozen practical noninferiority margin is two percentage points. Sensitivity compares the same interval against zero-, one-, two- and five-point margins; changing a margin does not add evidence.

Other main binary contrasts use conservative paired 95% intervals. Continuous metrics use paired question-level bootstrap intervals with 5,000 replicates and seed 20261019. Timing repetitions are first averaged within question before paired resampling, giving 60 clusters per task/model rather than 180. Timing accuracy intervals are descriptive, not a second confirmatory accuracy family. Timing P95 values use nearest-rank individual-call summaries. Secondary intervals are not adjusted for the full set of exploratory comparisons.

Tokens per credited answer equal total output tokens divided by contract-correct calls, and are undefined when no answer is credited. This descriptive ratio does not imply semantic correctness or a deployment price. Relative savings use a no-monitor baseline, never the configured cap, as denominator.

Offline validation checked all 25,200 records, complete job grids, input/protocol provenance, stage separation, threshold selection and mechanism identities. All observed policy outputs were prefixes of their paired Uniform outputs; Complete and Shadow token IDs matched; Conjunction never ended before Complete. Local reanalysis reproduced summaries and mechanisms exactly and intervals within 10^-12 numerical tolerance across Python/SciPy versions. Original server results remain unchanged. This is computational reproduction of an archived experiment, not independent experimental replication.

## 3. Results

### 3.1. Main contract accuracy and actual consumption

Table 2 reports all policies. Marker never delivered a contract-valid answer; its apparent token savings are not useful savings for this interface. Complete and Shadow had identical quality and token counts in all 2,400 main question/model pairs. Permissive diagnostic results appear in the supplementary metrics.

Table 2. Main results at cap 512, with 600 questions per row. Correct and valid are terminal-contract percentages. Tok/correct is total tokens per contract-correct call; a dash indicates a zero denominator. U: Uniform; M: Marker; L: Legacy entropy; C: Complete; S: Shadow; E: Conjunction.

| Model / task | Policy | Correct % | Valid % | Mean tokens | Tok/correct |
| --- | --- | --- | --- | --- | --- |
| Qwen / GSM8K | U | 67.83 | 92.50 | 181.05 | 266.90 |
| Qwen / GSM8K | M | 0.00 | 0.00 | 176.45 | - |
| Qwen / GSM8K | L | 53.83 | 74.50 | 180.27 | 334.87 |
| Qwen / GSM8K | C | 70.17 | 97.17 | 180.91 | 257.83 |
| Qwen / GSM8K | S | 70.17 | 97.17 | 180.91 | 257.83 |
| Qwen / GSM8K | E | 67.83 | 92.50 | 181.05 | 266.90 |
| Qwen / ARC-C | U | 87.67 | 96.50 | 191.55 | 218.50 |
| Qwen / ARC-C | M | 0.00 | 0.00 | 189.60 | - |
| Qwen / ARC-C | L | 62.67 | 71.00 | 191.29 | 305.26 |
| Qwen / ARC-C | C | 87.67 | 96.50 | 191.55 | 218.50 |
| Qwen / ARC-C | S | 87.67 | 96.50 | 191.55 | 218.50 |
| Qwen / ARC-C | E | 87.67 | 96.50 | 191.55 | 218.50 |
| Mistral / GSM8K | U | 44.00 | 74.17 | 229.03 | 520.53 |
| Mistral / GSM8K | M | 0.00 | 0.00 | 219.04 | - |
| Mistral / GSM8K | L | 32.00 | 54.17 | 227.42 | 710.70 |
| Mistral / GSM8K | C | 57.50 | 95.67 | 223.75 | 389.13 |
| Mistral / GSM8K | S | 57.50 | 95.67 | 223.75 | 389.13 |
| Mistral / GSM8K | E | 44.00 | 74.17 | 229.03 | 520.53 |
| Mistral / ARC-C | U | 50.83 | 68.50 | 183.58 | 361.14 |
| Mistral / ARC-C | M | 0.00 | 0.00 | 173.45 | - |
| Mistral / ARC-C | L | 34.17 | 46.67 | 180.05 | 526.97 |
| Mistral / ARC-C | C | 54.00 | 76.33 | 178.83 | 331.16 |
| Mistral / ARC-C | S | 54.00 | 76.33 | 178.83 | 331.16 |
| Mistral / ARC-C | E | 51.00 | 68.67 | 182.90 | 358.63 |

Table 3. Main Complete-minus-Uniform contrasts. Accuracy changes are percentage points with family-adjusted 98.75% intervals. Token changes are tokens per call with paired bootstrap 95% intervals. Wins and losses concern paired contract correctness.

| Model / task | Win / loss | Accuracy change [CI] | Token change [CI] |
| --- | --- | --- | --- |
| Qwen / GSM8K | 14 / 0 | +2.33 [0.03, 4.57] | -0.137 [-0.188, -0.088] |
| Qwen / ARC-C | 0 / 0 | +0.00 [-0.96, 0.96] | +0.000 [0.000, 0.000] |
| Mistral / GSM8K | 81 / 0 | +13.50 [8.98, 17.72] | -5.285 [-6.227, -4.388] |
| Mistral / ARC-C | 19 / 0 | +3.17 [0.59, 5.66] | -4.750 [-7.508, -2.623] |

Complete met the frozen two-point noninferiority criterion in all four cells. Three accuracy intervals excluded zero positively. Qwen ARC-C had no discordant correctness pairs, with an interval of -0.96 to 0.96 points; this supports a two-point tolerance but does not prove zero loss probability. Token savings were 0.08% for Qwen GSM8K, 0.00% for Qwen ARC-C, 2.31% for Mistral GSM8K and 2.59% for Mistral ARC-C. Contract-accuracy differences can therefore be much larger than consumption differences.

Complete gained 114 credited answers and lost none relative to Uniform. Every gain had a missing terminal-contract prediction under Uniform rather than a different extracted valid prediction. This supports contract preservation, not better mathematical or multiple-choice reasoning. Qwen GSM8K's 14 gains comprised 13 responses with a later LaTeX display closure and one with a later code-fence closure. An accepted prefix can thus be syntactically incomplete under a richer document validator while satisfying the frozen terminal-marker contract.

### 3.2. Entropy conditions and completion opportunities

Legacy entropy reduced contract accuracy relative to Uniform by 14.00 points for Qwen GSM8K, 25.00 for Qwen ARC-C, 12.00 for Mistral GSM8K and 16.67 for Mistral ARC-C. The respective 95% intervals were [-17.48, -10.25], [-29.19, -20.39], [-15.30, -8.46] and [-20.54, -12.48] points. Mean token reductions were only 0.43%, 0.13%, 0.70% and 1.92%. These findings concern the retained rule and its parser gates, not entropy stopping generally.

Conjunction matched Uniform token IDs in 2,399 of 2,400 main pairs. Relative to Complete it lost 113 credited answers, gained none, and always consumed at least as many tokens. One Mistral ARC-C trajectory stopped before Uniform, explaining their near rather than complete identity. The observed issue is a gate mismatch: entropy stability and the current acceptable suffix often fail to coincide. When continuation changes the suffix, the rule cannot recover the earlier boundary without a latched-completion design, which was not tested.

Permissive extraction makes some policy outcomes appear similar. Mistral GSM8K's diagnostic accuracy was 57.83% under Uniform, Complete and Conjunction, while their contract accuracies were 44.00%, 57.50% and 44.00%. These answer different questions about delivered text. Independent human semantic ratings are pending, so we do not resolve which rejected responses a human would accept.

### 3.3. Isolated latency and shadow monitoring

Table 4 reports isolated mean end-to-end intervals. Each cell contains 60 questions with three repetitions per policy. Complete was not universally faster than Uniform. Its paired difference was +32.96 ms [22.47, 44.43] for Qwen GSM8K and +36.99 ms [27.30, 46.86] for Qwen ARC-C, approximately 0.9% in both. Mistral GSM8K's signed difference was -98.23 ms [-191.99, -19.47], or -1.96%. Mistral ARC-C's signed difference was -43.07 ms [-130.72, 27.16], crossing zero. Parsing and callback costs can offset very small output reductions.

Table 4. Mean local end-to-end interval, seconds, from isolated timing. Concurrent main-stage times are not used for latency claims. Generation-time, median, P95 and quality summaries are in the timing supplement.

| Model / task | U | C | S | E | L |
| --- | --- | --- | --- | --- | --- |
| Qwen / GSM8K | 3.603 | 3.636 | 3.679 | 3.681 | 3.693 |
| Qwen / ARC-C | 4.075 | 4.112 | 4.164 | 4.160 | 4.185 |
| Mistral / GSM8K | 5.005 | 4.907 | 4.936 | 5.077 | 5.063 |
| Mistral / ARC-C | 4.384 | 4.341 | 4.358 | 4.445 | 4.452 |

Shadow matched Complete token IDs in all 720 paired timing calls. Its additional runtime thus measures the monitoring path while holding observed output fixed. Mean overhead ranged from 16.46 to 51.18 ms (Table 5), with positive unadjusted 95% intervals in all four cells. Relative overhead was 0.38%-1.24%. These values are implementation-specific; token counts alone cannot reveal them.

Table 5. Shadow minus Complete end-to-end overhead. Intervals are paired question-cluster bootstrap 95% intervals. Relative overhead divides by the Complete mean.

| Model / task | Added ms [95% CI] | Relative |
| --- | --- | --- |
| Qwen / GSM8K | 43.76 [35.45, 53.03] | 1.20% |
| Qwen / ARC-C | 51.18 [40.33, 62.81] | 1.24% |
| Mistral / GSM8K | 28.45 [17.54, 38.21] | 0.58% |
| Mistral / ARC-C | 16.46 [5.77, 27.89] | 0.38% |

Legacy entropy reduced timing output by only 0.22-2.12 tokens per call but increased mean end-to-end latency by 1.15%-2.69% relative to Uniform. Conjunction matched Uniform IDs in all 720 timing calls and never terminated through its policy gate. Timing repeats showed no within-question output variation. These observations validate the shadow comparison while limiting any claim that fewer tokens necessarily imply shorter elapsed time.

## 4. Discussion

### 4.1. Meaning of the quality differences

The main accuracy differences arise because the interface accepts a marked final line and rejects later non-whitespace continuation. Stopping preserves an accepted representation; it does not demonstrate additional solved problems. A consumer using permissive extraction would see a different benefit. The wrapper examples explain why the contract must be precise: terminal-line validity and complete-document validity are distinct. A richer structured-output interface could remove some gains, while a tolerant consumer might consider continuation harmless.

The result nevertheless matters to systems enforcing a terminal field, parser or protocol. A monitor intended to improve reliability can harm delivery if it waits past the accepted boundary. It should be evaluated jointly with the consumer's parser, including cases where completion becomes true and subsequently false. Our evidence supports this implementation check, without establishing that the tested contract is optimal for deployment.

### 4.2. Interpreting monitoring cost

The shadow arm separates two otherwise confounded effects: changing generation length and paying to observe generation. Entropy monitoring here adds a small measurable latency cost without changing a token. Legacy entropy combines that cost with very small token savings and substantially lower contract accuracy. This configuration offers no efficiency advantage for the measured endpoint. The result does not rule out fused monitors, asynchronous estimates, less frequent checks or different stopping conditions.

A useful evaluation sequence is to verify a shadow arm's token-path identity, measure its overhead in the intended execution mode, and compare the stopping arm against both shadow and no-monitor controls. This diagnoses cost in the tested system; it is not a physical scheduling algorithm. A token allowance specifies neither GPU allocation nor FLOPs, energy, monetary cost or throughput. Peak allocated memory includes model and cache storage and cannot supply these missing measurements.

### 4.3. Generalization limits and further validation

The study contains two approximately 7B instruction-tuned models, two tasks, one allowance, one sampling/order seed, greedy decoding and batch size one on A800 hardware. The models share questions, and timing uses a subset of the accuracy cohort. The benchmarks do not represent long-horizon agents, tool calls, concurrent queues, speculative decoding or reasoning-model budget forcing. Fixed model-session order permits session-level drift; randomized within-session jobs do not remove that limitation. Small latency effects may differ under another runtime.

Independent human semantic audit is pending. Two blinded rating forms, a stratified sample and a private sampling key have been prepared; there are no completed human scores or agreement statistics. The 600 sampled outputs enrich contract/diagnostic disagreements, so an unweighted mean would not estimate population semantic accuracy. Later analysis must retain inclusion probabilities, independent ratings and sealed pre-adjudication records. Until then, conclusions are confined to contract outcomes and observed runtime.

The record motivates tests of latched completion, richer contracts and cheaper monitors but contains no observations for them. The single-allowance design cannot estimate a budget-response function or validate dynamic allocation. Public release and an independent rerun would strengthen external reproducibility beyond the local computational checks.

### 4.4. Historical JANUS evidence

Historical JANUS results motivated these controls and are not pooled with the prospective cohort. The earlier audit found TCJS/TokOnly identity in 3,000 paired records and identical CompRoute results across nominal allowances 64, 128 and 256. A separate offline tokenizer-based reconstruction indicated that all three allowances were clamped to an effective cap of 64. Historical logs did not record every effective cap directly, and the reconstruction used a different tokenizer patch version, as documented in the archived audit. Those findings diagnose implementation naming and cap transformations, not scheduling efficacy. Historical prompts, scoring and sampling differ. Preserving those artifacts supports accountability; counting them as prospective replications would be inappropriate.

## 5. Conclusions

Under a frozen terminal-answer contract, completion stopping preserved 114 additional credited answers across 2,400 question/model pairs, with modest or zero token savings. Entropy shadow monitoring left observed outputs unchanged while adding measurable isolated latency. The tested conjunction usually missed the completion opportunity, and the retained legacy entropy rule reduced contract accuracy without reducing elapsed time. The findings support explicit parser contracts, policy-path audits and output-invariant runtime controls. They do not establish semantic reasoning gains, universal acceleration or joint token/compute scheduling.

## Data and code availability

A complete local archive contains the frozen protocol, revision pins, input manifests, raw outputs, attempt/completion receipts, environment snapshots and analysis scripts. The downloaded bundle was verified before the rental instance was shut down. The v6 package adds dated provenance, offline checks and manuscript sources while preserving frozen experimental files. A public repository/archive URL and, if obtained, DOI must be inserted after authors approve release and verify redistribution permissions. No public deposit is claimed. Reproduction instructions distinguish release material from the private human-audit key.

## Declarations requiring author confirmation

**Funding.** Pending confirmation of actual support, grant identifiers and funders' roles. Absence of funding is not assumed.

**Competing interests.** Pending author confirmation, including employment and support relevant to this work. The supplied affiliation is retained and is not a verified disclosure.

**Author contributions.** Pending a factual account of contributions and final approval. Supplied author order and correspondence details are retained for confirmation.

**AI-assisted work.** AI assistance was used in manuscript revision, code inspection and modification, experiment operation, computational analysis and document preparation. Authors must verify the precise account against actual use and current journal disclosure fields. AI output has not substituted for independent human semantic ratings. Human authors remain responsible for methods, data, interpretations and final text.

## References

Clark P, Cowhey I, Etzioni O, Khot T, Sabharwal A, Schoenick C, Tafjord O. 2018. Think you have solved question answering? Try ARC, the AI2 Reasoning Challenge. arXiv:1803.05457. https://arxiv.org/abs/1803.05457

Cobbe K, Kosaraju V, Bavarian M, Chen M, Jun H, Kaiser L, Plappert M, Tworek J, Hilton J, Nakano R, Hesse C, Schulman J. 2021. Training verifiers to solve math word problems. arXiv:2110.14168. https://arxiv.org/abs/2110.14168

Han T, Wang Z, Fang C, Zhao S, Ma S, Chen Z. 2025. Token-budget-aware LLM reasoning. Findings of the Association for Computational Linguistics: ACL 2025, 24842-24855. DOI: 10.18653/v1/2025.findings-acl.1274. https://aclanthology.org/2025.findings-acl.1274/

Mistral AI. 2024. Mistral-7B-Instruct-v0.3 model card. https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3

Muennighoff N, Yang Z, Shi W, Li XL, Fei-Fei L, Hajishirzi H, Zettlemoyer L, Liang P, Candes E, Hashimoto T. 2025. s1: Simple test-time scaling. arXiv:2501.19393, version 3. https://arxiv.org/abs/2501.19393v3

Wang J, Jain S, Zhang D, Ray B, Kumar V, Athiwaratkun B. 2024. Reasoning in token economies: Budget-aware evaluation of LLM reasoning strategies. Proceedings of EMNLP 2024, 19916-19939. DOI: 10.18653/v1/2024.emnlp-main.1112. https://aclanthology.org/2024.emnlp-main.1112/

Yang A, Yu B, Li C, Liu D, Huang F, Huang H, Jiang J, Tu J, Zhang J, Zhou J, Lin J, et al. 2025. Qwen2.5-1M technical report. arXiv:2501.15383. https://arxiv.org/abs/2501.15383

Yu Q, Zheng Z, Song S, Li Z, Xiong F, Tang B, Chen D. 2025. xFinder: Large language models as automated evaluators for reliable evaluation. ICLR 2025; arXiv:2405.11874, version 3. https://arxiv.org/abs/2405.11874
