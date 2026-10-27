# Historical experiments supporting the budget-viable commitment research draft

Version v8.8, 27 October 2026. This supplement preserves executed precursor evidence. It does not evaluate the proposed constrained-repair decoder. All ten numerical table bodies are preserved verbatim from v8.6. Historical section/table labels have been updated for this separate supplement.

## Historical Supplement A. Executed protocols

**Evidence separation.** The experiments in this section evaluated historical stopping and monitoring policies. None ran the budget-viable commitment controller in Section 3 of the main manuscript. The numerical tables below are retained to explain the failure modes motivating the proposal; they provide no measured gain for the new mask, compiler, commitment coverage or repair latency. The additional transition and cost analyses are retrospective.

### A.1. Frozen design and sampling

The executed specification was `janus-prospective-v5.1-cap512-reduced`, with seed 20261019 and one output allowance, 512 tokens. Input preparation, an independent implementation pilot, development diagnostics, the main evaluation and isolated timing were separate stages. The pilot checked implementation and provenance gates, rather than a significance threshold or minimum improvement. The execution chain, gate receipts and formal analyses completed successfully. The archived protocol's pre-execution wording is preserved as provenance; dated execution receipts and raw records establish the completed work.

GSM8K used `openai/gsm8k`, configuration `main`, revision `740312add88f781978c0658806c59bc2815b9866`. ARC-Challenge used `allenai/ai2_arc`, configuration `ARC-Challenge`, revision `210d026faf9955653af8916fad021475a3f00453`. Development contained 300 training questions per task; the held-out evaluation contained 600 test questions per task. Exact prompt duplicates and development/test overlap were checked. The 582 GSM8K test questions touched by historical JANUS work were excluded before drawing the new cohort from the remaining 737 eligible questions. ARC sampling used 1,172 eligible test questions. Deterministic manifests record the resulting membership.

The pilot used the first 20 development questions per task. Timing used the first 60 main questions per task, with three repetitions per policy. Thus pilot and timing are nested diagnostic subsets, not independent accuracy replications. Both models answered the same cohorts. There are 1,200 distinct main question identities, 600 per task; the 14,400 main calls arise from two models and six policies. Calls and repetitions do not substitute for independent questions in uncertainty estimates.

Table S1. Executed scored-call counts. Main and pilot evaluate six policies; development evaluates Uniform, Complete and three conjunction thresholds. Warmup calls are outside these counts.

| Stage | Questions per task/model | Settings | Repeats | Scored calls |
| --- | --- | --- | --- | --- |
| Implementation pilot | 20 | 6 | 1 | 480 |
| Development diagnostic | 300 | 5 | 1 | 6,000 |
| Main evaluation | 600 | 6 | 1 | 14,400 |
| Isolated timing | 60 | 6 | 3 | 4,320 |
| Total | - | - | - | 25,200 |

Development thresholds were 0.005, 0.01 and 0.05. The frozen rule selected 0.01 a priori for the prospective conjunction; development did not optimize the reported main threshold. The selection record and guard verify this choice. The legacy threshold remained 0.05. No prospective budget sweep, fitted allocation curve, transfer study or scheduling experiment was executed in this reduced design.

### A.2. Models, prompts and generation

The models were Qwen2.5-7B-Instruct-1M (Yang et al., 2025), revision `e28526f7bb80e2a9c8af03b831a9af3812f18fba`, and Mistral-7B-Instruct-v0.3 (Mistral AI, 2024), revision `c170c708c41dac9275d15a8fff4eca08d52bab71`. We used each tokenizer's native chat template with a generation prompt and one user message, without in-context examples. For the initial experiment, model revision pins were recorded but weight bytes were not independently rehashed. The follow-up verified model and tokenizer files against its frozen SHA-256 manifest.

The numeric instruction ended: Solve the problem step by step. End with a final line exactly "#### <number>" using a signed integer or decimal, no units or commas. Put a newline after the final line. ARC used the analogous instruction with the instance's allowed choice letters. The exact prompts, question text and choices are reconstructible from input manifests and the runner. Prompts and generation settings were identical across policies for a question.

Generation used BF16, Transformers SDPA, batch size one, greedy decoding, one beam, cache enabled, repetition penalty 1.0, no forced EOS token and no minimum new-token requirement. Every policy in the initial experiment and the new timing experiment performed real inference. The separate retrospective analysis reconstructed stopping outcomes from saved baseline sequences and is explicitly identified as replay in Supplement A.7. Each inference call recorded generated token IDs, text, token count, stop reason, parser outcomes, timing and provenance. Token counts include an emitted EOS token. Deterministic algorithms were not enabled, so observed identity checks describe these runs rather than a guarantee across kernels or hardware.

### A.3. Terminal-answer contract and diagnostic extraction

The prespecified primary quality endpoint is boundary-certified terminal-marker contract accuracy, shortened below to contract accuracy. The parser locates the last line-start `####` marker. Numeric values must be signed integers or decimals; commas, units and scientific notation are excluded. ARC values must be an allowed choice letter. After that value, the suffix may contain whitespace only. Online completion requires a newline after the value. Offline validity additionally requires either EOS termination or a newline-terminated terminal answer in the returned text. The scorer recomputes this boundary from the returned text rather than reading a stored completion event. A numeric fragment at the cap without either certificate is not credited.

A valid answer is correct if its value, compared as a decimal or choice letter, equals the gold answer. Validity is reported separately from correctness. The same parser scores every main policy, including Uniform. This endpoint measures compliance with a specific terminal interface, not correctness under arbitrary extraction conventions.

The parser does not validate document syntax before the marker. A marked line inside an unclosed LaTeX display or code fence can satisfy the contract when stopped after its newline. Later closing that wrapper can invalidate the terminal suffix. This behavior is central to interpreting the results: terminal-line validity and complete-document validity are different requirements. Supplement A.7 retrospectively evaluates several explicit alternatives without changing the frozen primary contract.

A legacy-style extractor supplies diagnostic sensitivity scores. GSM8K extraction prioritizes a marked number, then a boxed answer, answer-like phrases or equalities, and finally a trailing number. The ARC diagnostic uses the last standalone A-E letter without filtering to the instance's allowed choices; it is not a historical JANUS parser. These scores describe extraction outcomes and do not establish that incomplete or contradictory text is semantically acceptable.

### A.4. Implemented stopping policies

Uniform (U) runs to model EOS or the 512-token cap without entropy monitoring. Marker (M) stops at the first observed `####` substring without requiring a value or newline. Marker is a deliberately incomplete negative control, not a proposed usable efficiency method.

Complete (C) stops at the earliest online boundary satisfying the marked answer-line contract. It does not calculate entropy. Shadow (S; code identifier `entropy_observe`) computes entropy diagnostics but uses the Complete stopping rule. Its runtime contrast with Complete isolates the tested monitoring path only if generated token IDs match. A mechanism audit checks that condition.

Legacy entropy (L) calculates full-vocabulary next-token entropy, H = -sum(p log(p + 10^-12)), from pre-token logits. Successive entropy differences are smoothed with coefficient 2/11. After the minimum-step gate, it requires five consecutive stable steps with absolute smoothed difference below 0.05, five identical nonempty legacy answer candidates, and an observed marked or boxed answer. The retained legacy candidate prefix includes the final prompt token. Trigger decisions are applied after the subsequent generated token. The code and traces preserve this timing detail; it is not a completed-answer guarantee.

Conjunction (E; `entropy_complete`) requires at least 21 generated steps, five stable entropy steps at threshold 0.01, and a complete answer boundary at the current step. Completion is not latched: an earlier acceptable line is insufficient if later text changes the suffix. The tested mechanism therefore requires simultaneous completion and stability. Entropy callbacks return the logits unchanged. EOS has priority in stop-reason classification. Exact gates, indexing and special-token handling are executable in `core.py` and `engine.py`.

### A.5. Hardware and timing

Quality stages in the initial experiment used two NVIDIA A800 80 GB PCIe GPUs, one model per GPU. Its latency analysis uses only the separate isolated timing stage. Models ran sequentially on the same physical GPU without other GPU inference jobs. Each model had 24 warmup calls, two per task/policy, for 48 timing warmups. Jobs were shuffled by the frozen seed within each model session; the saved order was independently reconstructed. Qwen ran on 21 October 2026 from 14:07 to 16:26 UTC, followed by Mistral from 16:29 to 19:17 UTC. Model-session order was not counterbalanced. The later concurrent three-GPU experiment is described separately in Supplement A.7 and is not pooled with these measurements.

The runtime used Python 3.11.12, PyTorch 2.6.0+cu124, CUDA 12.4, driver 570.211.01, Transformers 4.48.2, Datasets 3.2.0, NumPy 1.26.4 and SciPy 1.14.1. Timing used two PyTorch CPU threads and 64 interop threads. TF32 matrix multiplication and cuDNN benchmarking were disabled; Flash, memory-efficient and mathematical SDPA backends were enabled. Environment snapshots are archived.

Generation time starts after input preparation and a CUDA synchronization and ends after generation and final synchronization. End-to-end time starts before chat templating, tokenization and device transfer, and ends after generation, synchronization, token-ID transfer and decoding. It excludes model loading, warmup, scoring, logging, network transport and queues. It is a local request interval, not deployed service latency or throughput. Full-vocabulary entropy and scalar transfers introduce GPU/CPU synchronization; measured overhead includes these implementation choices and Python callbacks. It is not a hardware lower bound on entropy estimation.

### A.6. Analysis and computational verification

Analyses pair policies by question within model and task. The four primary Complete-minus-Uniform accuracy comparisons form one family. Each uses a conservative 98.75% interval, giving at least 95% family coverage by Bonferroni adjustment. The paired binary interval bounds win and loss probabilities using simultaneous one-sided Clopper-Pearson bounds. The frozen practical noninferiority margin is two percentage points. Sensitivity compares the same interval against zero-, one-, two- and five-point margins; changing a margin does not add evidence.

Other main binary contrasts use conservative paired 95% intervals. Continuous metrics use paired question-level bootstrap intervals with 5,000 replicates and seed 20261019. Timing repetitions are first averaged within question before paired resampling, giving 60 clusters per task/model rather than 180. Timing accuracy intervals are descriptive, not a second confirmatory accuracy family. Timing P95 values use nearest-rank individual-call summaries. Secondary intervals are not adjusted for the full set of exploratory comparisons.

Tokens per credited answer equal total output tokens divided by contract-correct calls, and are undefined when no answer is credited. This descriptive ratio does not imply semantic correctness or a deployment price. Relative savings use a no-monitor baseline, never the configured cap, as denominator.

Offline validation checked all 25,200 records, complete job grids, input/protocol provenance, stage separation, threshold selection and mechanism identities. All observed policy outputs were prefixes of their paired Uniform outputs; Complete and Shadow token IDs matched; Conjunction never ended before Complete. Local reanalysis reproduced summaries and mechanisms exactly and intervals within 10^-12 numerical tolerance across Python/SciPy versions. Original server results remain unchanged. This is computational reproduction of an archived experiment, not independent experimental replication.

### A.7. Frozen follow-up and retrospective sensitivity analyses

The follow-up separates reanalysis from newly executed inference. Retrospective reconstruction used 3,600 saved Uniform trajectories (1,200 development and 2,400 main model/question pairs) to form 10,800 reconstructed policy records. Those records are not additional inference calls or independent observations. Reconstruction matched the recorded token sequences, text, stopping outcomes and scores in the audited comparisons. Main-cohort contract sensitivity uses the same 600 questions per model/task cell as the initial experiment. A mechanism audit inspected all 114 strict-contract Complete-over-Uniform wins. These are computational checks of saved outputs; they establish operational parser outcomes only.

Five operational contracts were applied to the saved main outputs: the frozen strict terminal rule; a closure-tolerant rule allowing recognized closing wrappers; a wrapper-balanced strict rule; a closure-balanced rule combining closure tolerance with wrapper balance; and a last-marked-answer rule that permits later text. These finite rules do not implement a general Markdown or LaTeX parser, and numeric comparison remains exact. The source snapshot used for the reported sensitivity counts requires a line-start marker. A received alternative implementation also accepts indentation before the marker. Their sole affected main-cohort question changes both policies' absolute correct counts in three Qwen/GSM8K contract cells by one, while all 20 paired accuracy differences and win/loss counts remain unchanged. The preserved parser provenance audit documents both implementations; none of these alternatives replaces the frozen primary endpoint.

A separate trace audit reused 240 SHA-verified trajectories and evaluated 12 parameter combinations (2,880 replay evaluations). The frozen entropy conjunction used threshold 0.01, five stable steps and a minimum of 21 steps. More permissive combinations were exploratory and were not used to replace the deployed rule or select new accuracy results. The previously completed 56-call smoke check and 240-call trace set were reused by hash; five-GPU timing observations were excluded from the three-GPU analysis. No additional quality extension was executed.

The v8.3 protocol first ran a three-GPU timing pilot with 400 scored calls and 120 warmups, using six workers in two waves. Its complete grid, exit codes, barriers, token identity checks and analysis underwent independent AI-agent technical review before a hash-bound decision released formal timing. This was an operational implementation review, not a semantic-quality endpoint. Formal timing comprised 10,800 scored calls: two models, two tasks, 60 questions per task, five policies, three within-session repetitions and three sessions. Eighteen workers ran in six waves with 360 additional warmups. Thus, new generation comprised 11,200 scored calls and 480 warmups. The formal 120 distinct questions are a reused subset of the original main cohort; the three sessions do not add new questions.

Each of three A800 80 GB GPUs ran one independent batch-size-one worker. Models, revisions, allowance of 512 tokens, BF16 precision and SDPA attention were retained. Workers used four assigned CPU cores and two intra-operation and two inter-operation threads. Model order was Qwen then Mistral in sessions 0 and 2 and Mistral then Qwen in session 1. This partly varies order but does not fully counterbalance it. The five follow-up policies were Uniform (U); boundary_observe (BO), which processes the token prefix and parses the boundary without stopping early; Complete (C), which stops at that boundary; entropy_observe (EO), which adds entropy observation to Complete without gating it; and entropy_uniform (EU), which adds entropy observation to BO without early stopping. These five controls differ from the six-policy initial accuracy experiment.

Four prespecified operational contrasts were evaluated: EO-C for added entropy monitoring on the completion path, BO-U for boundary processing without truncation, EU-BO for added entropy monitoring on the full-output path, and C-U for the net effect of completion stopping. Calls were paired by model, task, session, question, repetition and recorded worker/GPU provenance. Within each contrast and session, three repetitions were averaged per question before a paired question-cluster percentile bootstrap (5,000 replicates; seed 20261019; n = 60). All 48 resulting 95% intervals are descriptive and unadjusted for multiple comparisons. The same questions recur across sessions and models; neither repeated calls nor GPU shards are treated as independent questions. Ranges across the three session means are descriptive ranges, not confidence intervals.

The new end-to-end timer starts before tokenization of an already constructed prompt and includes transfer, synchronized generation, token-ID transfer to CPU and decoding. It excludes chat-template construction, model loading, warmups, scoring, logging and network or queue latency. The original end-to-end timer also included chat-template construction and used different CPU thread settings. Hardware sharing, model order and timing boundaries therefore preclude pooling the old isolated, old five-GPU and new three-GPU results or attributing their differences solely to GPU count. The experiment measures paired request latency under concurrent deployment, not aggregate service throughput or a threefold speedup.

### A.8. Additional retrospective transition and contrast analysis

For this revision, the original main JSONL records were joined by model, task and question ID for Uniform and Complete. Token-prefix identity, 600-pair grids, validity transitions and correctness outcomes were checked directly. We compared the exact set of shortened trajectories with the set of invalid-to-valid transitions. This analysis uses stored frozen scores already checked against an independent parser; it is not a new model experiment or semantic annotation. For formal timing, B, D and R_L were calculated from the preserved session-level contrasts. The new raw per-call timing archive was not available to this revision, so derived covariance and intervals were not estimated. Numerical table bodies and frozen endpoints are unchanged; table labels use the supplement prefix S. Analysis code, input hashes and machine-readable outputs accompany the revision.

## Historical Supplement B. Results and retrospective diagnostics

### B.1. Main contract accuracy and actual consumption

Table S2 reports all policies. Marker never delivered a contract-valid answer; its apparent token savings are not useful savings for this interface. Complete and Shadow had identical quality and token counts in all 2,400 main question/model pairs. Permissive diagnostic results appear in the supplementary metrics.

Table S2. Main results at cap 512, with 600 questions per row. Correct and valid are terminal-contract percentages. Tok/correct is total tokens per contract-correct call; a dash indicates a zero denominator. U: Uniform; M: Marker; L: Legacy entropy; C: Complete; S: Shadow; E: Conjunction.

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

Table S3. Main Complete-minus-Uniform contrasts. Accuracy changes are percentage points with family-adjusted 98.75% intervals. Token changes are tokens per call with paired bootstrap 95% intervals. Wins and losses concern paired contract correctness.

| Model / task | Win / loss | Accuracy change [CI] | Token change [CI] |
| --- | --- | --- | --- |
| Qwen / GSM8K | 14 / 0 | +2.33 [0.03, 4.57] | -0.137 [-0.188, -0.088] |
| Qwen / ARC-C | 0 / 0 | +0.00 [-0.96, 0.96] | +0.000 [0.000, 0.000] |
| Mistral / GSM8K | 81 / 0 | +13.50 [8.98, 17.72] | -5.285 [-6.227, -4.388] |
| Mistral / ARC-C | 19 / 0 | +3.17 [0.59, 5.66] | -4.750 [-7.508, -2.623] |

Complete met the frozen two-point noninferiority criterion in all four cells. Three accuracy intervals excluded zero positively. Qwen ARC-C had no discordant correctness pairs, with an interval of -0.96 to 0.96 points; this supports a two-point tolerance but does not prove zero loss probability. Token savings were 0.08% for Qwen GSM8K, 0.00% for Qwen ARC-C, 2.31% for Mistral GSM8K and 2.59% for Mistral ARC-C. Contract-accuracy differences can therefore be much larger than consumption differences.

Complete gained 114 credited answers and lost none relative to Uniform. Every gain had a missing terminal-contract prediction under Uniform rather than a different extracted valid prediction. This supports contract preservation, not better mathematical or multiple-choice reasoning. Qwen GSM8K's 14 gains comprised 13 responses with a later LaTeX display closure and one with a later code-fence closure. An accepted prefix can thus be syntactically incomplete under a richer document validator while satisfying the frozen terminal-marker contract.

### B.2. Entropy conditions and completion opportunities

Legacy entropy reduced contract accuracy relative to Uniform by 14.00 points for Qwen GSM8K, 25.00 for Qwen ARC-C, 12.00 for Mistral GSM8K and 16.67 for Mistral ARC-C. The respective 95% intervals were [-17.48, -10.25], [-29.19, -20.39], [-15.30, -8.46] and [-20.54, -12.48] points. Mean token reductions were only 0.43%, 0.13%, 0.70% and 1.92%. These findings concern the retained rule and its parser gates, not entropy stopping generally.

Conjunction matched Uniform token IDs in 2,399 of 2,400 main pairs. Relative to Complete it lost 113 credited answers, gained none, and always consumed at least as many tokens. One Mistral ARC-C trajectory stopped before Uniform, explaining their near rather than complete identity. The observed issue is a gate mismatch: entropy stability and the current acceptable suffix often fail to coincide. When continuation changes the suffix, the rule cannot recover the earlier boundary without a latched-completion design. The follow-up included only an execution-consistency smoke check of this design; its prospective quality and latency efficacy were not evaluated.

Permissive extraction makes some policy outcomes appear similar. Mistral GSM8K's diagnostic accuracy was 57.83% under Uniform, Complete and Conjunction, while their contract accuracies were 44.00%, 57.50% and 44.00%. These answer different questions about delivered text. These computational endpoints do not establish whether a reader would accept an incomplete or contradictory response.

### B.3. Isolated latency and shadow monitoring

Table S4 reports isolated mean end-to-end intervals. Each cell contains 60 questions with three repetitions per policy. Complete was not universally faster than Uniform. Its paired difference was +32.96 ms [22.47, 44.43] for Qwen GSM8K and +36.99 ms [27.30, 46.86] for Qwen ARC-C, approximately 0.9% in both. Mistral GSM8K's signed difference was -98.23 ms [-191.99, -19.47], or -1.96%. Mistral ARC-C's signed difference was -43.07 ms [-130.72, 27.16], crossing zero. Parsing and callback costs can offset very small output reductions.

Table S4. Mean local end-to-end interval, seconds, from isolated timing. Concurrent main-stage times are not used for latency claims. Generation-time, median, P95 and quality summaries are in the timing supplement.

| Model / task | U | C | S | E | L |
| --- | --- | --- | --- | --- | --- |
| Qwen / GSM8K | 3.603 | 3.636 | 3.679 | 3.681 | 3.693 |
| Qwen / ARC-C | 4.075 | 4.112 | 4.164 | 4.160 | 4.185 |
| Mistral / GSM8K | 5.005 | 4.907 | 4.936 | 5.077 | 5.063 |
| Mistral / ARC-C | 4.384 | 4.341 | 4.358 | 4.445 | 4.452 |

Shadow matched Complete token IDs in all 720 paired timing calls. Its additional runtime thus measures the monitoring path while holding observed output fixed. Mean overhead ranged from 16.46 to 51.18 ms (Table S5), with positive unadjusted 95% intervals in all four cells. Relative overhead was 0.38%-1.24%. These values are implementation-specific; token counts alone cannot reveal them.

Table S5. Shadow minus Complete end-to-end overhead. Intervals are paired question-cluster bootstrap 95% intervals. Relative overhead divides by the Complete mean.

| Model / task | Added ms [95% CI] | Relative |
| --- | --- | --- |
| Qwen / GSM8K | 43.76 [35.45, 53.03] | 1.20% |
| Qwen / ARC-C | 51.18 [40.33, 62.81] | 1.24% |
| Mistral / GSM8K | 28.45 [17.54, 38.21] | 0.58% |
| Mistral / ARC-C | 16.46 [5.77, 27.89] | 0.38% |

Legacy entropy reduced timing output by only 0.22-2.12 tokens per call but increased mean end-to-end latency by 1.15%-2.69% relative to Uniform. Conjunction matched Uniform IDs in all 720 timing calls and never terminated through its policy gate. Timing repeats showed no within-question output variation. These observations validate the shadow comparison while limiting any claim that fewer tokens necessarily imply shorter elapsed time.

### B.4. Contract sensitivity and trace evidence

The apparent accuracy benefit depends on which output representation a consumer accepts (Table S6). Closure tolerance eliminates the 14 Qwen/GSM8K strict-contract wins; adding a wrapper-balance requirement reverses the Qwen/GSM8K difference under the closure-balanced rule. Last-marked-answer extraction gives zero Complete-Uniform difference in all four model/task cells. These are paired rescoring results on existing outputs and do not show that continuation is semantically harmless.

Table S6. Retrospective Complete-Uniform contract-accuracy differences, in percentage points, on 600 main questions per model/task cell. The columns use the same paired outputs under each operational parser. These alternative endpoints are sensitivity analyses, not new primary tests.

| Contract | Qwen/GSM8K | Qwen/ARC | Mistral/GSM8K | Mistral/ARC |
| --- | --- | --- | --- | --- |
| Strict terminal | 2.33 | 0.00 | 13.50 | 3.17 |
| Closure-tolerant | 0.00 | 0.00 | 13.50 | 3.17 |
| Wrapper-balanced strict | 0.00 | 0.00 | 13.50 | 3.17 |
| Closure-balanced | -2.33 | 0.00 | 13.50 | 3.17 |
| Last marked answer | 0.00 | 0.00 | 0.00 | 0.00 |

The 114 strict-contract wins were mechanically categorized as 13 LaTeX-wrapper cases, one code-fence case, 98 post-answer continuations and two loop cases. The generated prefix and last marked answer value were unchanged in the audited pairs. Two lexical disavowal or placeholder flags overlap these categories; they are lexical flags, not semantic judgments. Under the frozen conjunction settings, the trace audit found 3,116 stable non-EOS steps but no simultaneous answer-boundary opportunity and no early trigger across 240 trajectories. A more permissive exploratory combination produced 16 triggers, which does not validate a revised stopping policy or its accuracy.

### B.5. Repeated concurrent three-GPU timing

The formal run completed the full 10,800-call scored grid across 18 workers and six waves after the separately reviewed pilot. All three output-invariant monitoring contrasts preserved both generated and returned token IDs. Their 36 model/task/session contrasts yielded 6,480 matched output-pair checks; outputs are reused across contrasts, so this is not a count of independent observations. The pilot had 240 additional matched pair checks. Each formal inference comparison still has 60 question clusters. All 36 descriptive monitoring intervals were above zero, and all 108 corresponding GPU-stratum mean differences were positive. The latter are descriptive point estimates, not 108 independent significance tests or causal GPU effects.

Table S7. Ranges of the three session-specific mean latency differences in the formal concurrent experiment. Each cell is the minimum and maximum of three point estimates, not an interval estimate. EO-C adds entropy monitoring to completion; BO-U adds boundary processing without truncation; EU-BO adds entropy monitoring without truncation. Full session estimates and descriptive bootstrap intervals are retained in the supplement.

| Model/task | Entropy EO-C (ms) | Boundary BO-U (ms) | Entropy EU-BO (ms) |
| --- | --- | --- | --- |
| Qwen/GSM8K | 43.42-48.02 | 90.74-95.89 | 41.98-44.87 |
| Qwen/ARC | 49.49-58.57 | 115.76-121.43 | 48.35-51.48 |
| Mistral/GSM8K | 22.33-25.27 | 150.46-154.96 | 20.48-25.15 |
| Mistral/ARC | 12.79-25.07 | 107.42-115.32 | 23.02-31.60 |

Boundary processing without early stopping added approximately 91-155 ms per call across the model/task/session cells. Added entropy monitoring ranged from approximately 13-59 ms on the completion path and 20-52 ms on the full-output path. The consistency of the matched-output contrasts isolates overhead from output truncation within this runtime; it does not imply an implementation-independent monitoring cost.

Table S8. Complete-Uniform mean latency differences in milliseconds, with descriptive, unadjusted 95% paired question-cluster bootstrap intervals. Negative values favor completion stopping. Every cell uses 60 questions with three within-session repetitions averaged per question; sessions reuse the same questions.

| Model/task | Session 0 | Session 1 | Session 2 |
| --- | --- | --- | --- |
| Qwen/GSM8K | 90.87 [68.19, 117.65] | 92.13 [72.34, 116.03] | 90.72 [72.06, 112.54] |
| Qwen/ARC | 110.49 [91.31, 131.74] | 114.50 [97.00, 132.79] | 118.62 [99.21, 140.28] |
| Mistral/GSM8K | 0.29 [-97.67, 88.08] | -0.10 [-98.14, 86.27] | -2.34 [-98.14, 83.51] |
| Mistral/ARC | 21.60 [-58.03, 91.23] | 26.22 [-53.36, 94.76] | 19.66 [-58.51, 86.43] |

Completion stopping did not produce a stable overall latency improvement. All Qwen session intervals were above zero, corresponding to approximately 2.5%-2.9% more elapsed time despite unchanged or slightly shortened output. Mistral point differences were near zero or positive and every interval spanned zero; these intervals permit both benefit and harm and do not establish equivalence. Mistral's shorter output therefore did not establish a net latency gain in this concurrent setting. The Complete-Uniform contrast includes output differences and is not an output-invariant overhead control. These findings complement, but are not pooled with, the earlier isolated measurements in Tables S4 and S5.

### B.6. Validity repair and the location of token savings

A new retrospective transition audit of the original main records distinguishes interface repair from solving additional questions (Table S9). Complete produced 204 invalid-to-valid transitions and no valid-to-invalid transitions across 2,400 model–question pairs. Of the newly valid outputs, 114 matched the gold answer and 90 did not. The latter are valid deliveries of wrong answers, demonstrating why interface validity and answer correctness must be separate endpoints.

Table S9. Retrospective validity transitions, with 600 paired questions in each model/task cell. Counts refer to the frozen strict contract. They are model–question outcomes, not additional inference calls.

| Model/task | Validity gains | Validity losses | Correct repairs | Wrong repairs | Shortened |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen / GSM8K | 28 | 0 | 14 | 14 | 28 |
| Qwen / ARC | 0 | 0 | 0 | 0 | 0 |
| Mistral / GSM8K | 129 | 0 | 81 | 48 | 129 |
| Mistral / ARC | 47 | 0 | 19 | 28 | 47 |

An exact pairwise set check found that the 204 shortened outputs were precisely the 204 validity repairs. There was no observed shortening of an already valid Uniform output. On this cohort, token savings were therefore concentrated in contract-breaking continuation rather than broad compression of the reasoning preceding an acceptable answer. This equality is an empirical property of these traces, not a general consequence of earliest-boundary stopping. Zero validity losses describes the historical early-stop rule under its shared-prefix assumptions; neither that observation nor the zero correctness losses validates the proposed repair controller. No pooled population significance claim is made from these model–question totals.

### B.7. Boundary-path and net stopping effects

Table S10 applies the historical identity D = B - R_L, where D = C-U, B = BO-U and R_L = BO-C, to the existing formal timing means. It does not create new timing observations or confidence intervals. In Qwen, the net slowdown is close to the output-matched boundary-path cost. For Mistral, the boundary-arm contrast offsets much of that cost, yet the original net-effect intervals still span benefit and harm. A near-zero net effect therefore does not by itself show that detecting an earlier boundary saved no work.

Table S10. Ranges across the three session point estimates, in milliseconds. B = BO-U; D = C-U; R_L = BO-C = B-D. Ranges are not uncertainty intervals; no interval is assigned to the derived R_L.

| Model/task | Boundary path B | Net completion D | Boundary-arm difference R_L |
| --- | ---: | ---: | ---: |
| Qwen / GSM8K | 90.74 to 95.89 | 90.72 to 92.13 | -0.14 to 5.17 |
| Qwen / ARC | 115.76 to 121.43 | 110.49 to 118.62 | 2.81 to 5.27 |
| Mistral / GSM8K | 150.46 to 154.96 | -2.34 to 0.29 | 152.03 to 155.05 |
| Mistral / ARC | 107.42 to 115.32 | 19.66 to 26.22 | 81.20 to 93.72 |

The small negative R_L estimate in one Qwen/GSM8K session illustrates why this residual must not be labeled isolated saved GPU time. Output-path differences and timing noise remain. These descriptive values motivate optimizing the detection path, but do not predict the performance of an unmeasured native or incremental implementation. New raw timing records would be required to estimate paired uncertainty for R_L.


## References

Clark P, Cowhey I, Etzioni O, Khot T, Sabharwal A, Schoenick C, Tafjord O. 2018. Think you have solved question answering? Try ARC, the AI2 Reasoning Challenge. arXiv:1803.05457. <https://arxiv.org/abs/1803.05457>

Cobbe K, Kosaraju V, Bavarian M, Chen M, Jun H, Kaiser L, Plappert M, Tworek J, Hilton J, Nakano R, Hesse C, Schulman J. 2021. Training verifiers to solve math word problems. arXiv:2110.14168. <https://arxiv.org/abs/2110.14168>

Han T, Wang Z, Fang C, Zhao S, Ma S, Chen Z. 2025. Token-budget-aware LLM reasoning. Findings of the Association for Computational Linguistics: ACL 2025, 24842-24855. DOI: 10.18653/v1/2025.findings-acl.1274. <https://aclanthology.org/2025.findings-acl.1274/>

Mistral AI. 2024. Mistral-7B-Instruct-v0.3 model card. <https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3>

Muennighoff N, Yang Z, Shi W, Li XL, Fei-Fei L, Hajishirzi H, Zettlemoyer L, Liang P, Candes E, Hashimoto T. 2025. s1: Simple test-time scaling. arXiv:2501.19393, version 3. <https://arxiv.org/abs/2501.19393v3>

Wang J, Jain S, Zhang D, Ray B, Kumar V, Athiwaratkun B. 2024. Reasoning in token economies: Budget-aware evaluation of LLM reasoning strategies. Proceedings of EMNLP 2024, 19916-19939. DOI: 10.18653/v1/2024.emnlp-main.1112. <https://aclanthology.org/2024.emnlp-main.1112/>

Yang A, Yu B, Li C, Liu D, Huang F, Huang H, Jiang J, Tu J, Zhang J, Zhou J, Lin J, et al. 2025. Qwen2.5-1M technical report. arXiv:2501.15383. <https://arxiv.org/abs/2501.15383>

Yu Q, Zheng Z, Song S, Li Z, Xiong F, Tang B, Chen D. 2025. xFinder: Large language models as automated evaluators for reliable evaluation. ICLR 2025; arXiv:2405.11874, version 3. <https://arxiv.org/abs/2405.11874>

XGrammar project. 2026. Official project documentation, README, commit `e085851aec8f417924be5f460d1e038cac0e3bd5`. <https://github.com/mlc-ai/xgrammar/blob/e085851aec8f417924be5f460d1e038cac0e3bd5/README.md> (accessed 26 October 2026).

Outlines project. 2026. Official project documentation, README, commit `c52af8472c6fe8a607a733ec11b709476af77a96`. <https://github.com/dottxt-ai/outlines/blob/c52af8472c6fe8a607a733ec11b709476af77a96/README.md> (accessed 26 October 2026).

Hokamp C, Liu Q. 2017. Lexically Constrained Decoding for Sequence Generation Using Grid Beam Search. Proceedings of ACL 2017 (Volume 1: Long Papers), 1535–1546. DOI: 10.18653/v1/P17-1141. <https://aclanthology.org/P17-1141/>.

Geng S, Josifoski M, Peyrard M, West R. 2023. Grammar-Constrained Decoding for Structured NLP Tasks without Finetuning. Proceedings of EMNLP 2023, 10932–10952. DOI: 10.18653/v1/2023.emnlp-main.674. <https://aclanthology.org/2023.emnlp-main.674/>.

Hugging Face. 2025. Transformers v4.48.2: generation stopping criteria, including StopStringCriteria. Versioned implementation documentation. <https://github.com/huggingface/transformers/blob/v4.48.2/src/transformers/generation/stopping_criteria.py> (accessed 26 October 2026).
