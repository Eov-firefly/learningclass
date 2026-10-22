**Evaluating answer-boundary stopping: terminal contracts, transient validity, and monitoring cost**

Ya Bai, GuoZhen Bian\*, Cheng Chang, ZhengGuang Cui, HaiLong Qin, ZhiHui Huang, Yue Wang

China Telecom Cloud Network Operating System R&D Center, Beijing, China

\* Correspondence: biangz@chinatelecom.cn

Structural revision v7, 22 October 2026. Working manuscript: existing experimental results are retained from v6; the formal analysis and validation framework are new. Additional validation, source-level verification, author declarations and public archiving remain pending.

# Abstract

Stopping a language model at an apparent answer boundary changes both the returned text and the conditions under which a downstream parser accepts it. We examine this interaction through an interface-specific evaluation framework that separates terminal-contract correctness, output consumption and monitoring cost. We formalize prefix-dependent acceptance and show that an earliest-completion rule cannot guarantee correctness preservation: continuation may invalidate an accepted answer, but it may also correct an earlier wrong answer. A conjunction with a second gate can act only when the gate overlaps a current completion opportunity. These observations motivate paired output audits and an output-invariant shadow control. The existing experiment comprises two instruction-tuned models, GSM8K and ARC-Challenge, six policies and a 512-token cap, with 25,200 scored calls across implementation, development, main and isolated-timing stages. On 600 held-out questions per task, completion stopping changed terminal-contract accuracy by +2.33, 0.00, +13.50 and +3.17 percentage points across the four model–task cells, with 0.00%–2.59% mean token savings. All 114 additional credited answers reflected terminal-contract preservation rather than correction of an incorrect baseline prediction. Output-matched entropy observation added 16.46–51.18 ms per call in isolated timing. The tested conjunction matched baseline tokens in 2,399 of 2,400 main pairs. These results establish behavior for the specified parser and implementation, not semantic reasoning gains or general acceleration. Contract-sensitivity analysis, independent semantic assessment and additional mechanism controls remain necessary to assess practical delivery quality and broader validity.

Keywords: large language models; stopping criteria; interface contracts; answer extraction; monitoring overhead; empirical evaluation

# Introduction

An inference budget limits how much text a language model may generate; a stopping rule decides which prefix is returned. The quality of that prefix depends on the consumer. A numeric extractor may accept a value embedded in an unfinished response, whereas an interface may require a complete final field. Evaluating stopping therefore requires three separate observations: what the consumer accepts, what answer it receives, and what computation was actually performed.

Acceptance need not persist during continuation. A final answer line can satisfy a terminal-field contract and then cease to satisfy it when more text is appended. Conversely, a model can revise an early complete but incorrect answer. The first case creates an opportunity for early stopping; the second creates a risk. An evaluation based only on final token counts or one extraction convention cannot distinguish these mechanisms.

A separate confound concerns monitoring. An entropy-based rule changes generation length while paying for full-vocabulary operations, host callbacks and synchronization. A shorter output need not have a shorter request interval. An output-invariant monitor provides a control: when it returns exactly the same token sequence as the unmonitored stopping rule, their runtime difference measures the added monitoring path under the tested execution conditions.

We organize this study around three questions. RQ1: under a declared terminal-answer contract, which paired outcomes reflect preservation of a deliverable answer, and which would reflect premature commitment? RQ2: when generated output is held fixed, what runtime overhead does the tested monitoring path introduce? RQ3: when completion is transient, does an additional entropy gate overlap the opportunity to stop? These questions concern interface-specific stopping, not a new reasoning model or joint resource scheduler.

The contribution has three parts. First, a formal account of prefix acceptance gives an exact paired correctness decomposition, a counterexample to universal correctness preservation, and an overlap condition for conjunction stopping. These are elementary analytical results used to specify testable mechanisms. Second, an evaluation framework separates contract outcomes, trajectory identity and monitoring overhead, with a distinct evidence requirement for each. Third, an existing two-model, two-task experiment provides a bounded case study with matched prompts, a shadow arm and isolated timing. Contract robustness and general performance superiority are not established by that experiment.

The study originated in an audit of JANUS, an earlier token-budget experiment whose tested TCJS and TokOnly paths were identical. The present evidence is narrower and concerns single-request generation. Historical audit findings are not pooled with the new cohort. The formal treatment in this revision was developed after the existing experiment; it is not described as part of that experiment’s frozen protocol.

## Related work and the unresolved comparison

Budget-aware reasoning studies how inference computation is used. Wang et al. (2024) compare reasoning strategies under budgets; Han et al. (2025) investigate token-budget-aware reasoning; and Muennighoff et al. (2025) study test-time scaling and budget forcing. The present intervention operates at the stopping callback of greedy instruction-model generation. Those systems supply context, but their training, prompting and allocation procedures are not reproduced here.

Answer extraction affects measured performance. Yu et al. (2025) examine automated extraction in xFinder. Here a fixed parser defines a delivery contract, while a more permissive extractor is diagnostic. Neither establishes semantic quality by itself. GSM8K (Cobbe et al. 2021) and ARC (Clark et al. 2018) provide numeric and multiple-choice cases, not comprehensive coverage of structured interfaces.

Direct boundary detection, structured-output validation and constrained decoding are necessary neighboring comparisons for an interface-level contribution. They differ in whether they detect an emitted boundary, validate a returned artifact or restrict the generation trajectory. The existing experiment tests only the first category and selected monitoring variants. It does not establish an advantage over the latter categories. A source-verified literature expansion and matched practical controls are required before claiming novelty or competitive superiority in that broader space.

# Formal analysis of interface-aware stopping

## Trajectories, acceptance and correctness

Fix a prompt, decoder, model state and output cap $K$. Let $x_{1:t}$ be the generated token prefix and $d_t$ its decoded text, with special tokens handled by the declared decoder. Uniform returns at $T_U\leq K$, determined by EOS or the cap. Let $e_t$ indicate whether EOS has terminated the prefix. We analyze stopping policies conditional on a shared token trajectory up to their stopping times. This condition must be checked empirically; greedy decoding alone does not guarantee identity across implementations or hardware.

For an interface contract $\mathcal C$, define offline validity $A_{\mathcal C}(d_t,e_t)\in\{0,1\}$ and answer extraction $g_{\mathcal C}(d_t,e_t)$. Extraction is defined only for valid text. For gold answer $y$, credited correctness is $$Q_{\mathcal C}(t;y)=A_{\mathcal C}(d_t,e_t)\,
 \mathbf 1\{g_{\mathcal C}(d_t,e_t)=y\},$$ with $Q_{\mathcal C}=0$ on invalid text. A semantic judgment or a complete-document validator is a separate endpoint and is not implied by $Q_{\mathcal C}$.

An online completion indicator $B_{\mathcal C}(t)$ certifies validity if the prefix is returned at that step. It must not use the gold answer or future tokens. In the implemented contract, a newline after the marked value provides the online certificate; EOS can certify an offline final value without that newline. Thus online and offline acceptance are related but not identical. Complete returns at $$T_C=\min\left(\{t<T_U:B_{\mathcal C}(t)=1\}\cup\{T_U\}\right).$$ Using $t<T_U$ incorporates baseline EOS priority: an event at the same final step cannot save a token. The rule returns the emitted prefix and performs no gold-aware selection or rewriting.

Call validity continuation-stable on a class of non-EOS trajectories if $A_{\mathcal C}(d_t,0)=1$ implies $A_{\mathcal C}(d_s,0)=1$ for every later prefix in that class. A terminal-value contract generally lacks this property because later non-whitespace can invalidate its suffix. Validity stability and answer stability are different properties: even if later text remains valid, its extracted value can change.

## Paired gains do not imply a correctness guarantee

**Proposition 1 (exact paired decomposition).** For $n$ paired questions, let $W$ count cases with $Q_C=1,Q_U=0$ and $L$ count cases with $Q_C=0,Q_U=1$, under the same scoring contract. Then $$\label{eq:paired}
 \widehat{\Delta Q}=\frac{1}{n}\sum_{i=1}^{n}(Q_{C,i}-Q_{U,i})=\frac{W-L}{n}.$$ *Proof.* Each binary pair contributes $+1$, $-1$ or $0$; summing gives the identity. This is an accounting identity, not a claim of novelty or a distributional guarantee.

For a win, Uniform’s outcome can be invalid, or valid with a wrong value. Those mechanisms require separate classification. The existing record reports all 114 wins as cases without a valid terminal prediction under Uniform. That observation supports contract preservation, conditional on verification of the paired records; it does not show that the model solved 114 previously unsolved questions.

**Proposition 2 (no universal correctness dominance).** Shared prefixes and a sound online validity certificate do not imply $Q_C\geq Q_U$ on every question.

*Proof by counterexample.* For gold answer 42, consider a trajectory that first emits a newline-terminated `#### 41`, then explanatory correction text, and finally `#### 42` followed by EOS. Complete returns the first valid but wrong answer. Uniform returns a final valid correct answer under the last-marker parser. Thus $Q_C=0$ and $Q_U=1$. Conversely, appending non-whitespace closure text after a correct marked line can give $Q_C=1,Q_U=0$ under the tested terminal-suffix rule. Both directions are possible.

A sufficient condition for correctness dominance on a trajectory class is stronger: whenever $Q_{\mathcal C}(T_U;y)=1$, the earliest certified prefix must extract the same correct answer, or no earlier certificate may occur. Merely requiring persistent validity does not ensure this answer consistency. The observed zero losses in the present cohort must therefore be accompanied by uncertainty intervals and tests of answer revision, repeated markers and marker-like content in quotations or examples.

## Conjunction stopping requires temporal overlap

Let $G(t)$ collect the non-completion gates, including minimum step count and entropy stability. A non-latched conjunction returns at $$T_E=\min\left(\{t<T_U:B_{\mathcal C}(t)G(t)=1\}\cup\{T_U\}\right).$$ **Proposition 3 (overlap and ordering).** On a shared trajectory, $T_C\leq T_E\leq T_U$. The conjunction stops strictly before Uniform if and only if a step $t<T_U$ satisfies both $B_{\mathcal C}(t)=1$ and $G(t)=1$.

*Proof.* The conjunction’s eligible steps are a subset of Complete’s eligible steps. Taking their minima with the same fallback gives the ordering. An eligible step before $T_U$ is necessary and sufficient for earlier stopping.

The result does not identify why overlap is absent. A strict threshold, minimum-step gate, token indexing or a short completion window can each prevent it. Aggregate non-triggering is insufficient to distinguish these explanations. Trace-level gate occupancy and targeted ablations are needed. Latching a past completion event alone also does not preserve final validity: if generation continues, a system must specify whether it returns the new text or buffers and returns an earlier prefix, and account for the computation already spent.

## Output length and elapsed time are distinct quantities

Write a policy’s measured request interval on a paired trajectory as $$T^{\mathrm{wall}}_P=\sum_{t=1}^{N_P}b_t+M_P+r_P,$$ where $N_P$ is actual generated length, $b_t$ is a common reference per-step execution cost, $M_P$ represents policy-specific monitoring and parsing work, and $r_P$ collects departures from that reference, including runtime interference and execution changes. These terms define an explanatory decomposition; the experiment does not identify each term separately.

**Proposition 4 (runtime break-even identity).** For $N_C\leq N_U$, $$\label{eq:break-even}
 T^{\mathrm{wall}}_C-T^{\mathrm{wall}}_U
 =-\sum_{t=N_C+1}^{N_U}b_t+(M_C-M_U)+(r_C-r_U).$$ *Proof.* Subtract the two decompositions and cancel shared reference steps. Consequently, fewer tokens are not sufficient for lower latency: saved reference execution time must exceed the added work and residual difference.

When Shadow and Complete have identical generated IDs and stopping lengths, the saved-step term is zero. Their contrast estimates the added monitoring path under the randomized within-session measurement design, subject to runtime variability. It does not isolate a hardware-invariant entropy cost or eliminate all session effects. The empirical evidence must report output identity, measurement boundaries and uncertainty together.

## From analytical statements to validation

The framework yields separate obligations: paired outputs and alternate contracts for Proposition 1; revision and repeated-marker cases for Proposition 2; per-step gates and controlled ablations for Proposition 3; and output-matched repeated timing for Proposition 4. The existing experiment addresses parts of these obligations. The supplementary validation plan identifies the missing checks without treating them as executed experiments or retroactively adding them to the frozen protocol.

# Materials and methods

## Frozen design and sampling

The executed specification was `janus-prospective-v5.1-cap512-reduced`, with seed 20261019 and one output allowance, 512 tokens. Input preparation, an independent implementation pilot, development diagnostics, the main evaluation and isolated timing were separate stages. The pilot checked implementation and provenance gates, rather than a significance threshold or minimum improvement. The execution chain, gate receipts and formal analyses completed successfully. The archived protocol’s pre-execution wording is preserved as provenance; dated execution receipts and raw records establish the completed work.

GSM8K used `openai/gsm8k`, configuration `main`, revision `740312add88f781978c0658806c59bc2815b9866`. ARC-Challenge used `allenai/ai2_arc`, configuration `ARC-Challenge`, revision `210d026faf9955653af8916fad021475a3f00453`. Development contained 300 training questions per task; the held-out evaluation contained 600 test questions per task. Exact prompt duplicates and development/test overlap were checked. The 582 GSM8K test questions touched by historical JANUS work were excluded before drawing the new cohort from the remaining 737 eligible questions. ARC sampling used 1,172 eligible test questions. Deterministic manifests record the resulting membership.

The pilot used the first 20 development questions per task. Timing used the first 60 main questions per task, with three repetitions per policy. Thus pilot and timing are nested diagnostic subsets, not independent accuracy replications. Both models answered the same cohorts. There are 1,200 distinct main question identities, 600 per task; the 14,400 main calls arise from two models and six policies. Calls and repetitions do not substitute for independent questions in uncertainty estimates.

<div class="singlespace">

<div id="tab:design">

| Stage                  | Questions per task/model | Settings | Repeats | Scored calls |
|:-----------------------|:-------------------------|:---------|:--------|:-------------|
|                        |                          |          |         |              |
| Stage                  | Questions per task/model | Settings | Repeats | Scored calls |
|                        |                          |          |         |              |
| Implementation pilot   |                          |          |         |              |
| Development diagnostic |                          |          |         | ,000         |
| Main evaluation        |                          |          |         | ,400         |
| Isolated timing        |                          |          |         | ,320         |
| Total                  | \-                       | \-       | \-      | ,200         |

Executed scored-call counts. Main and pilot evaluate six policies; development evaluates Uniform, Complete and three conjunction thresholds. Warmup calls are outside these counts. (continued)

</div>

</div>

Development thresholds were 0.005, 0.01 and 0.05. The frozen rule selected 0.01 a priori for the prospective conjunction; development did not optimize the reported main threshold. The selection record and guard verify this choice. The legacy threshold remained 0.05. No prospective budget sweep, fitted allocation curve, transfer study or scheduling experiment was executed in this reduced design.

## Models, prompts and generation

The models were Qwen2.5-7B-Instruct-1M (Yang et al. 2025), revision `e28526f7bb80e2a9c8af03b831a9af3812f18fba`, and Mistral-7B-Instruct-v0.3 (Mistral AI 2024), revision `c170c708c41dac9275d15a8fff4eca08d52bab71`. We used each tokenizer’s native chat template with a generation prompt and one user message, without in-context examples. Model revision pins were recorded; weight bytes were not independently rehashed.

The numeric instruction ended: Solve the problem step by step. End with a final line exactly "#### \<number\>" using a signed integer or decimal, no units or commas. Put a newline after the final line. ARC used the analogous instruction with the instance’s allowed choice letters. The exact prompts, question text and choices are reconstructible from input manifests and the runner. Prompts and generation settings were identical across policies for a question.

Generation used BF16, Transformers SDPA, batch size one, greedy decoding, one beam, cache enabled, repetition penalty 1.0, no forced EOS token and no minimum new-token requirement. Every policy performed real inference; outputs were not reconstructed by truncating a saved baseline. Each call recorded generated token IDs, text, token count, stop reason, parser outcomes, timing and provenance. Token counts include an emitted EOS token. Deterministic algorithms were not enabled, so observed identity checks describe these runs rather than a guarantee across kernels or hardware.

## Terminal-answer contract and diagnostic extraction

The prespecified primary quality endpoint is boundary-certified terminal-marker contract accuracy, shortened below to contract accuracy. The parser locates the last line-start `####` marker. Numeric values must be signed integers or decimals; commas, units and scientific notation are excluded. ARC values must be an allowed choice letter. After that value, the suffix may contain whitespace only. Online completion requires a newline after the value. Offline validity additionally requires either EOS termination or a newline-terminated terminal answer in the returned text. The scorer recomputes this boundary from the returned text rather than reading a stored completion event. A numeric fragment at the cap without either certificate is not credited.

A valid answer is correct if its value, compared as a decimal or choice letter, equals the gold answer. Validity is reported separately from correctness. The same parser scores every main policy, including Uniform. This endpoint measures compliance with a specific terminal interface, not correctness under arbitrary extraction conventions.

The parser does not validate document syntax before the marker. A marked line inside an unclosed LaTeX display or code fence can satisfy the contract when stopped after its newline. Later closing that wrapper can invalidate the terminal suffix. This behavior is central to interpreting the results: a caller requiring well-formed Markdown or LaTeX needs a different contract and a new evaluation.

A legacy-style extractor supplies diagnostic sensitivity scores. GSM8K extraction prioritizes a marked number, then a boxed answer, answer-like phrases or equalities, and finally a trailing number. The ARC diagnostic uses the last standalone A-E letter without filtering to the instance’s allowed choices; it is not a historical JANUS parser. These scores describe extraction outcomes and do not establish that incomplete or contradictory text is semantically acceptable.

## Implemented stopping policies

Uniform (U) runs to model EOS or the 512-token cap without entropy monitoring. Marker (M) stops at the first observed `####` substring without requiring a value or newline. Marker is a deliberately incomplete negative control, not a proposed usable efficiency method.

Complete (C) stops at the earliest online boundary satisfying the marked answer-line contract. It does not calculate entropy. Shadow (S; code identifier `entropy_observe`) computes entropy diagnostics but uses the Complete stopping rule. Its runtime contrast with Complete isolates the tested monitoring path only if generated token IDs match. A mechanism audit checks that condition.

Legacy entropy (L) calculates full-vocabulary next-token entropy, $H=-\sum p\log(p+10^{-12})$, from pre-token logits. Successive entropy differences are smoothed with coefficient 2/11. After the minimum-step gate, it requires five consecutive stable steps with absolute smoothed difference below 0.05, five identical nonempty legacy answer candidates, and an observed marked or boxed answer. The retained legacy candidate prefix includes the final prompt token. Trigger decisions are applied after the subsequent generated token. The code and traces preserve this timing detail; it is not a completed-answer guarantee.

Conjunction (E; `entropy_complete`) requires at least 21 generated steps, five stable entropy steps at threshold 0.01, and a complete answer boundary at the current step. Completion is not latched: an earlier acceptable line is insufficient if later text changes the suffix. The tested mechanism therefore requires simultaneous completion and stability. Entropy callbacks return the logits unchanged. EOS has priority in stop-reason classification. Exact gates, indexing and special-token handling are executable in `core.py` and `engine.py`.

## Hardware and timing

Quality stages used two NVIDIA A800 80 GB PCIe GPUs, one model per GPU. Only the isolated stage supports our latency conclusions. In timing, models ran sequentially on the same physical GPU without other GPU inference jobs. Each model had 24 warmup calls, two per task/policy, for 48 timing warmups. Jobs were shuffled by the frozen seed within each model session; the saved order was independently reconstructed. Qwen ran on 21 October 2026 from 14:07 to 16:26 UTC, followed by Mistral from 16:29 to 19:17 UTC. Model-session order was not counterbalanced.

The runtime used Python 3.11.12, PyTorch 2.6.0+cu124, CUDA 12.4, driver 570.211.01, Transformers 4.48.2, Datasets 3.2.0, NumPy 1.26.4 and SciPy 1.14.1. Timing used two PyTorch CPU threads and 64 interop threads. TF32 matrix multiplication and cuDNN benchmarking were disabled; Flash, memory-efficient and mathematical SDPA backends were enabled. Environment snapshots are archived.

Generation time starts after input preparation and a CUDA synchronization and ends after generation and final synchronization. End-to-end time starts before chat templating, tokenization and device transfer, and ends after generation, synchronization, token-ID transfer and decoding. It excludes model loading, warmup, scoring, logging, network transport and queues. It is a local request interval, not deployed service latency or throughput. Full-vocabulary entropy and scalar transfers introduce GPU/CPU synchronization; measured overhead includes these implementation choices and Python callbacks. It is not a hardware lower bound on entropy estimation.

## Analysis and computational verification

Analyses pair policies by question within model and task. The four primary Complete-minus-Uniform accuracy comparisons form one family. Each uses a conservative 98.75% interval, giving at least 95% family coverage by Bonferroni adjustment. The paired binary interval bounds win and loss probabilities using simultaneous one-sided Clopper-Pearson bounds. The frozen practical noninferiority margin is two percentage points. Sensitivity compares the same interval against zero-, one-, two- and five-point margins; changing a margin does not add evidence.

Other main binary contrasts use conservative paired 95% intervals. Continuous metrics use paired question-level bootstrap intervals with 5,000 replicates and seed 20261019. Timing repetitions are first averaged within question before paired resampling, giving 60 clusters per task/model rather than 180. Timing accuracy intervals are descriptive, not a second confirmatory accuracy family. Timing P95 values use nearest-rank individual-call summaries. Secondary intervals are not adjusted for the full set of exploratory comparisons.

Tokens per credited answer equal total output tokens divided by contract-correct calls, and are undefined when no answer is credited. This descriptive ratio does not imply semantic correctness or a deployment price. Relative savings use a no-monitor baseline, never the configured cap, as denominator.

Offline validation checked all 25,200 records, complete job grids, input/protocol provenance, stage separation, threshold selection and mechanism identities. All observed policy outputs were prefixes of their paired Uniform outputs; Complete and Shadow token IDs matched; Conjunction never ended before Complete. Local reanalysis reproduced summaries and mechanisms exactly and intervals within $10^{-12}$ numerical tolerance across Python/SciPy versions. Original server results remain unchanged. This is computational reproduction of an archived experiment, not independent experimental replication.

## Evidence mapping and interpretation safeguards

The primary contract is the one used in the completed experiment. This revision does not change that endpoint or recalculate reported values under a new parser. Contract validity, contract correctness, permissive extraction, document structure and independent semantic acceptance answer different questions. Only the first two are fully tabulated in the main results; diagnostic extraction is referenced in the original supplementary record, and human assessment remains pending.

The following interpretation rules apply. A contract gain is not called a reasoning gain. A negative result for Legacy or Conjunction is attributed to that implemented policy rather than to entropy stopping as a class. A shadow runtime contrast is conditional on exact output identity and the specified execution mode. Additional contract sensitivity, practical stopping controls and gate ablations are proposed follow-up work, not completed comparisons. Source records are required to independently check the manuscript’s mechanism and provenance claims.

# Results

## Main contract accuracy and actual consumption

Table <a href="#tab:main" data-reference-type="ref" data-reference="tab:main">2</a> reports all policies. Marker never delivered a contract-valid answer; its apparent token savings are not useful savings for this interface. Complete and Shadow had identical quality and token counts in all 2,400 main question/model pairs. Permissive diagnostic results appear in the supplementary metrics.

<div class="singlespace">

<div id="tab:main">

| Model / task    | Policy | Correct % | Valid % | Mean tokens | Tok/correct |
|:----------------|:-------|:----------|:--------|:------------|:------------|
|                 |        |           |         |             |             |
| Model / task    | Policy | Correct % | Valid % | Mean tokens | Tok/correct |
|                 |        |           |         |             |             |
| Qwen / GSM8K    | U      |           |         |             |             |
| Qwen / GSM8K    | M      |           |         |             | \-          |
| Qwen / GSM8K    | L      |           |         |             |             |
| Qwen / GSM8K    | C      |           |         |             |             |
| Qwen / GSM8K    | S      |           |         |             |             |
| Qwen / GSM8K    | E      |           |         |             |             |
| Qwen / ARC-C    | U      |           |         |             |             |
| Qwen / ARC-C    | M      |           |         |             | \-          |
| Qwen / ARC-C    | L      |           |         |             |             |
| Qwen / ARC-C    | C      |           |         |             |             |
| Qwen / ARC-C    | S      |           |         |             |             |
| Qwen / ARC-C    | E      |           |         |             |             |
| Mistral / GSM8K | U      |           |         |             |             |
| Mistral / GSM8K | M      |           |         |             | \-          |
| Mistral / GSM8K | L      |           |         |             |             |
| Mistral / GSM8K | C      |           |         |             |             |
| Mistral / GSM8K | S      |           |         |             |             |
| Mistral / GSM8K | E      |           |         |             |             |
| Mistral / ARC-C | U      |           |         |             |             |
| Mistral / ARC-C | M      |           |         |             | \-          |
| Mistral / ARC-C | L      |           |         |             |             |
| Mistral / ARC-C | C      |           |         |             |             |
| Mistral / ARC-C | S      |           |         |             |             |
| Mistral / ARC-C | E      |           |         |             |             |

Main results at cap 512, with 600 questions per row. Correct and valid are terminal-contract percentages. Tok/correct is total tokens per contract-correct call; a dash indicates a zero denominator. U: Uniform; M: Marker; L: Legacy entropy; C: Complete; S: Shadow; E: Conjunction. (continued)

</div>

</div>

<div class="singlespace">

<div id="tab:contrasts">

| Model / task    | Win / loss | Accuracy change \[CI\] | Token change \[CI\]     |
|:----------------|:-----------|:-----------------------|:------------------------|
|                 |            |                        |                         |
| Model / task    | Win / loss | Accuracy change \[CI\] | Token change \[CI\]     |
|                 |            |                        |                         |
| Qwen / GSM8K    | / 0        | +2.33 \[0.03, 4.57\]   | \[-0.188, -0.088\]      |
| Qwen / ARC-C    | / 0        | +0.00 \[-0.96, 0.96\]  | +0.000 \[0.000, 0.000\] |
| Mistral / GSM8K | / 0        | +13.50 \[8.98, 17.72\] | \[-6.227, -4.388\]      |
| Mistral / ARC-C | / 0        | +3.17 \[0.59, 5.66\]   | \[-7.508, -2.623\]      |

Main Complete-minus-Uniform contrasts. Accuracy changes are percentage points with family-adjusted 98.75% intervals. Token changes are tokens per call with paired bootstrap 95% intervals. Wins and losses concern paired contract correctness. (continued)

</div>

</div>

Complete met the frozen two-point noninferiority criterion in all four cells. Three accuracy intervals excluded zero positively. Qwen ARC-C had no discordant correctness pairs, with an interval of -0.96 to 0.96 points; this supports a two-point tolerance but does not prove zero loss probability. Token savings were 0.08% for Qwen GSM8K, 0.00% for Qwen ARC-C, 2.31% for Mistral GSM8K and 2.59% for Mistral ARC-C. Contract-accuracy differences can therefore be much larger than consumption differences.

Complete gained 114 credited answers and lost none relative to Uniform. Every gain had a missing terminal-contract prediction under Uniform rather than a different extracted valid prediction. This supports contract preservation, not better mathematical or multiple-choice reasoning. Qwen GSM8K’s 14 gains comprised 13 responses with a later LaTeX display closure and one with a later code-fence closure. An accepted prefix can thus be syntactically incomplete under a richer document validator while satisfying the frozen terminal-marker contract.

## Entropy conditions and completion opportunities

Legacy entropy reduced contract accuracy relative to Uniform by 14.00 points for Qwen GSM8K, 25.00 for Qwen ARC-C, 12.00 for Mistral GSM8K and 16.67 for Mistral ARC-C. The respective 95% intervals were \[-17.48, -10.25\], \[-29.19, -20.39\], \[-15.30, -8.46\] and \[-20.54, -12.48\] points. Mean token reductions were only 0.43%, 0.13%, 0.70% and 1.92%. These findings concern the retained rule and its parser gates, not entropy stopping generally.

Conjunction matched Uniform token IDs in 2,399 of 2,400 main pairs. Relative to Complete it lost 113 credited answers, gained none, and always consumed at least as many tokens. One Mistral ARC-C trajectory stopped before Uniform, explaining their near rather than complete identity. The observed issue is a gate mismatch: entropy stability and the current acceptable suffix often fail to coincide. When continuation changes the suffix, the rule cannot recover the earlier boundary without a latched-completion design, which was not tested.

Permissive extraction makes some policy outcomes appear similar. Mistral GSM8K’s diagnostic accuracy was 57.83% under Uniform, Complete and Conjunction, while their contract accuracies were 44.00%, 57.50% and 44.00%. These answer different questions about delivered text. Independent human semantic ratings are pending, so we do not resolve which rejected responses a human would accept.

## Isolated latency and shadow monitoring

Table <a href="#tab:timing" data-reference-type="ref" data-reference="tab:timing">4</a> reports isolated mean end-to-end intervals. Each cell contains 60 questions with three repetitions per policy. Complete was not universally faster than Uniform. Its paired difference was +32.96 ms \[22.47, 44.43\] for Qwen GSM8K and +36.99 ms \[27.30, 46.86\] for Qwen ARC-C, approximately 0.9% in both. Mistral GSM8K’s signed difference was -98.23 ms \[-191.99, -19.47\], or -1.96%. Mistral ARC-C’s signed difference was -43.07 ms \[-130.72, 27.16\], crossing zero. Parsing and callback costs can offset very small output reductions.

<div class="singlespace">

<div id="tab:timing">

| Model / task    | U   | C   | S   | E   | L   |
|:----------------|:----|:----|:----|:----|:----|
|                 |     |     |     |     |     |
| Model / task    | U   | C   | S   | E   | L   |
|                 |     |     |     |     |     |
| Qwen / GSM8K    |     |     |     |     |     |
| Qwen / ARC-C    |     |     |     |     |     |
| Mistral / GSM8K |     |     |     |     |     |
| Mistral / ARC-C |     |     |     |     |     |

Mean local end-to-end interval, seconds, from isolated timing. Concurrent main-stage times are not used for latency claims. Generation-time, median, P95 and quality summaries are in the timing supplement. (continued)

</div>

</div>

Shadow matched Complete token IDs in all 720 paired timing calls. Its additional runtime thus measures the monitoring path while holding observed output fixed. Mean overhead ranged from 16.46 to 51.18 ms (Table <a href="#tab:overhead" data-reference-type="ref" data-reference="tab:overhead">5</a>), with positive unadjusted 95% intervals in all four cells. Relative overhead was 0.38%-1.24%. These values are implementation-specific; token counts alone cannot reveal them.

<div class="singlespace">

<div id="tab:overhead">

| Model / task    | Added ms \[95% CI\] | Relative |
|:----------------|:--------------------|:---------|
|                 |                     |          |
| Model / task    | Added ms \[95% CI\] | Relative |
|                 |                     |          |
| Qwen / GSM8K    | \[35.45, 53.03\]    | %        |
| Qwen / ARC-C    | \[40.33, 62.81\]    | %        |
| Mistral / GSM8K | \[17.54, 38.21\]    | %        |
| Mistral / ARC-C | \[5.77, 27.89\]     | %        |

Shadow minus Complete end-to-end overhead. Intervals are paired question-cluster bootstrap 95% intervals. Relative overhead divides by the Complete mean. (continued)

</div>

</div>

Legacy entropy reduced timing output by only 0.22-2.12 tokens per call but increased mean end-to-end latency by 1.15%-2.69% relative to Uniform. Conjunction matched Uniform IDs in all 720 timing calls and never terminated through its policy gate. Timing repeats showed no within-question output variation. These observations validate the shadow comparison while limiting any claim that fewer tokens necessarily imply shorter elapsed time.

# Discussion

## What the existing evidence establishes

The strongest result is an interface-specific separation of contract preservation, generated length and monitoring time. Complete obtained 114 additional credited answers without an observed paired correctness loss, yet saved at most 2.59% of mean output tokens. Equation <a href="#eq:paired" data-reference-type="ref" data-reference="eq:paired">[eq:paired]</a> accounts for this difference; it does not establish correctness dominance. The counterexample in Proposition 2 shows why an empirical zero-loss result needs a bounded interpretation.

The contract deliberately treats post-answer non-whitespace as invalid. In Qwen/GSM8K, 13 of the 14 gains followed a LaTeX display closure and one followed a code-fence closure. A prefix accepted by this parser can therefore be less complete as a document than its continuation. These examples support the proposed mechanism but also challenge the contract’s application relevance. A strict consumer may require terminal-field compliance, while a reader or document renderer may prefer the full response. No deployed consumer is evaluated here, and practical delivery improvement remains unproven.

## What the controls identify and leave unresolved

Exact Complete–Shadow token identity is an important control because it removes output-length differences from their runtime contrast. The observed overhead belongs to the complete monitoring path, including synchronization and callback choices. It is not an estimate of an unavoidable entropy-computation lower bound. Similarly, Complete’s slower Qwen intervals show that small token savings can be outweighed by boundary-detection costs and runtime effects, consistent with Equation <a href="#eq:break-even" data-reference-type="ref" data-reference="eq:break-even">[eq:break-even]</a>.

Marker is a negative control, not a competitive delivery method. Legacy retains historical candidate and indexing behavior, so its poor results may depend on those implementation details. Conjunction’s near-identity with Uniform is consistent with absent gate overlap, but the aggregate result does not isolate threshold strictness, minimum-step effects or transient completion. Existing Legacy and Conjunction also differ in more than the completion condition. Single-factor ablations and trace-level gate diagnostics are required before a stronger mechanistic attribution.

## Contribution and scope

The proposed contribution is an evaluation method for interface-dependent stopping: declare the consumer contract, verify actual trajectories, classify paired gains and losses, and measure observation cost with output-matched controls. The formal results specify why each check is needed; they are elementary consequences of the definitions, not claims of a new stopping optimum. The present case study illustrates the checks but does not yet establish cross-contract robustness, superiority over practical structured-output methods or a generally optimal entropy threshold.

## Threats to validity and required follow-up

Construct validity is the leading concern. The current parser permits a marked line inside an unclosed wrapper and rejects later closure. Contract-sensitive rescoring, structural validation and semantic assessment must determine whether the credited gains correspond to useful deliveries. The original supplementary diagnostic results should be released in full rather than selectively quoted.

Independent human semantic audit remains pending. The existing record describes two blinded rating forms, a stratified sample and a private sampling key, but no completed ratings or agreement statistics. The 600 sampled outputs enrich contract/diagnostic disagreements; their unweighted mean cannot estimate population semantic accuracy. Any later assessment must preserve inclusion probabilities, independent pre-adjudication ratings and the distinction between design-weighted estimates and diagnostic subgroup summaries.

Internal validity requires access to source code, per-call records and frozen artifacts. This revision preserves the v6 experiment’s reported values but does not independently verify its raw records. The claimed offline reproduction and protocol gates require auditable receipts. A frozen local protocol is not necessarily a public preregistration, and the new formal analysis is retrospective. The two-point noninferiority margin also needs an application-based justification in addition to its reported prespecification.

Timing uses one model session per model on the same GPU, with a fixed model-session order. Within-session randomization and question-cluster intervals do not capture independent-session variability or remove session-level drift. Additional independent sessions and monitoring-path profiling are especially important for sub-percent effects. Three repetitions per question are not three independent hardware experiments.

External validity is limited to two approximately 7B instruction-tuned models, two short-answer tasks, one 512-token cap, greedy decoding, batch size one and A800 hardware. Excluding 582 historically used GSM8K test questions protects the new comparison from that prior exposure but changes the eligible test population; it does not rule out model-training contamination. The results cannot establish budget-response curves, concurrent serving throughput, long-horizon agent behavior or general reasoning-model performance. Multi-budget and additional-model experiments are needed only if those broader claims are pursued.

## Historical JANUS evidence

Historical JANUS results motivated these controls and are not pooled with the prospective cohort. The earlier audit found TCJS/TokOnly identity in 3,000 paired records and identical CompRoute results across nominal allowances 64, 128 and 256. A separate offline tokenizer-based reconstruction indicated that all three allowances were clamped to an effective cap of 64. Historical logs did not record every effective cap directly, and the reconstruction used a different tokenizer patch version, as documented in the archived audit. Those findings diagnose implementation naming and cap transformations, not scheduling efficacy. Historical prompts, scoring and sampling differ. Preserving those artifacts supports accountability; counting them as prospective replications would be inappropriate.

# Conclusions

Stopping should be evaluated against the interface that consumes the returned prefix and the runtime that implements the decision. The formal analysis shows why completion need not persist, why early commitment can either preserve or lose a credited answer, and why an additional gate requires temporal overlap with completion. In the existing experiment, Complete preserved 114 additional terminal-contract answers with modest or zero token savings; output-matched entropy observation added measurable runtime, and the tested conjunction almost always behaved like Uniform. These findings support explicit contracts, paired trajectory audits and output-invariant monitoring controls. Practical delivery quality, robustness to alternative contracts and broader performance advantages remain to be tested with the specified follow-up controls and auditable experiment records.

# Data and code availability

The v6 manuscript reports a local experimental archive containing the frozen protocol, revision pins, input manifests, per-call outputs, execution receipts, environment snapshots and analysis scripts. Those experimental materials were not included in the public manuscript package available for this revision, so their completeness and the reported computational reproduction could not be independently checked here. The available package contains manuscript sources, bibliography and a rendered PDF; file-integrity and typesetting checks do not validate the experiment. Before submission, provide an author-approved repository or review-access archive, redistribution-compliant reconstruction instructions and the complete supplementary metrics. A DOI may be added after an actual deposit; none is claimed here. Private human-audit keys must remain separate from public release material.

# Declarations requiring author confirmation

**Funding.** Pending confirmation of actual support, grant identifiers and funders’ roles. Absence of funding is not assumed.

**Competing interests.** Pending author confirmation, including employment and support relevant to this work. The supplied affiliation is retained and is not a verified disclosure.

**Author contributions.** Pending a factual account of contributions and final approval. Supplied author order and correspondence details are retained for confirmation.

**AI-assisted work.** AI assistance was used in manuscript revision, code inspection and modification, experiment operation, computational analysis and document preparation. Authors must verify the precise account against actual use and current journal disclosure fields. AI output has not substituted for independent human semantic ratings. Human authors remain responsible for methods, data, interpretations and final text.

<div id="refs" class="references csl-bib-body hanging-indent" entry-spacing="0">

<div id="ref-clark2018" class="csl-entry">

Clark, P., I. Cowhey, O. Etzioni, T. Khot, A. Sabharwal, C. Schoenick, and O. Tafjord. 2018. “Think You Have Solved Question Answering? Try ARC, the AI2 Reasoning Challenge.” <https://arxiv.org/abs/1803.05457>.

</div>

<div id="ref-cobbe2021" class="csl-entry">

Cobbe, K., V. Kosaraju, M. Bavarian, M. Chen, H. Jun, L. Kaiser, M. Plappert, et al. 2021. “Training Verifiers to Solve Math Word Problems.” <https://arxiv.org/abs/2110.14168>.

</div>

<div id="ref-han2025" class="csl-entry">

Han, T., Z. Wang, C. Fang, S. Zhao, S. Ma, and Z. Chen. 2025. “Token-Budget-Aware LLM Reasoning.” In *Findings of the Association for Computational Linguistics: ACL 2025*, 24842–55. <https://doi.org/10.18653/v1/2025.findings-acl.1274>.

</div>

<div id="ref-mistral2024" class="csl-entry">

Mistral AI. 2024. “<span class="nocase">Mistral-7B-Instruct-v0.3</span> Model Card.” <https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3>.

</div>

<div id="ref-muennighoff2025" class="csl-entry">

Muennighoff, N., Z. Yang, W. Shi, X. L. Li, L. Fei-Fei, H. Hajishirzi, L. Zettlemoyer, P. Liang, E. Candes, and T. Hashimoto. 2025. “<span class="nocase">s1</span>: Simple Test-Time Scaling.” <https://arxiv.org/abs/2501.19393v3>.

</div>

<div id="ref-wang2024" class="csl-entry">

Wang, J., S. Jain, D. Zhang, B. Ray, V. Kumar, and B. Athiwaratkun. 2024. “Reasoning in Token Economies: Budget-Aware Evaluation of LLM Reasoning Strategies.” In *Proceedings of EMNLP 2024*, 19916–39. <https://doi.org/10.18653/v1/2024.emnlp-main.1112>.

</div>

<div id="ref-yang2025" class="csl-entry">

Yang, A., B. Yu, C. Li, D. Liu, F. Huang, H. Huang, J. Jiang, et al. 2025. “Qwen2.5-1M Technical Report.” <https://arxiv.org/abs/2501.15383>.

</div>

<div id="ref-yu2025" class="csl-entry">

Yu, Q., Z. Zheng, S. Song, Z. Li, F. Xiong, B. Tang, and D. Chen. 2025. “<span class="nocase">xFinder</span>: Large Language Models as Automated Evaluators for Reliable Evaluation.” In *ICLR 2025*. <https://arxiv.org/abs/2405.11874>.

</div>

</div>
