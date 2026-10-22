from pathlib import Path
import shutil, hashlib, json

ROOT = Path('/workspace/paper-review')
SRC = ROOT / 'latex/peerj_latex_20261022_v6'
OUT = ROOT / 'revision_v7'
OUT.mkdir(exist_ok=True)
original = (SRC / 'main.tex').read_text()
t = original
old_title = 'Terminal-answer contracts and monitoring cost in token-limited LLM inference'
title = 'Evaluating answer-boundary stopping: terminal contracts, transient validity, and monitoring cost'
t = t.replace(old_title, title)
t = t.replace('pdfsubject={Research manuscript draft, v6}', 'pdfsubject={Structural revision v7; additional validation pending}')
t = t.replace('% Derived from the frozen-content v6 manuscript, 22 October 2026.', '% v7 structural revision; existing experimental results retained from v6.\n% New formal analysis is retrospective; proposed validation has not been executed.')
t = t.replace('Revision dated 22 October 2026. Research manuscript draft; author metadata, declarations and public archive location require author confirmation before submission.', 'Structural revision v7, 22 October 2026. Working manuscript: existing experimental results are retained from v6; the formal analysis and validation framework are new. Additional validation, source-level verification, author declarations and public archiving remain pending.')

abstract = r'''\section*{Abstract}
Stopping a language model at an apparent answer boundary changes both the returned text and the conditions under which a downstream parser accepts it. We examine this interaction through an interface-specific evaluation framework that separates terminal-contract correctness, output consumption and monitoring cost. We formalize prefix-dependent acceptance and show that an earliest-completion rule cannot guarantee correctness preservation: continuation may invalidate an accepted answer, but it may also correct an earlier wrong answer. A conjunction with a second gate can act only when the gate overlaps a current completion opportunity. These observations motivate paired output audits and an output-invariant shadow control. The existing experiment comprises two instruction-tuned models, GSM8K and ARC-Challenge, six policies and a 512-token cap, with 25,200 scored calls across implementation, development, main and isolated-timing stages. On 600 held-out questions per task, completion stopping changed terminal-contract accuracy by +2.33, 0.00, +13.50 and +3.17 percentage points across the four model--task cells, with 0.00\%--2.59\% mean token savings. All 114 additional credited answers reflected terminal-contract preservation rather than correction of an incorrect baseline prediction. Output-matched entropy observation added 16.46--51.18 ms per call in isolated timing. The tested conjunction matched baseline tokens in 2,399 of 2,400 main pairs. These results establish behavior for the specified parser and implementation, not semantic reasoning gains or general acceleration. Contract-sensitivity analysis, independent semantic assessment and additional mechanism controls remain necessary to assess practical delivery quality and broader validity.

Keywords: large language models; stopping criteria; interface contracts; answer extraction; monitoring overhead; empirical evaluation

'''
start=t.index('\\section*{Abstract}')
end=t.index('\\section{Introduction}')
t=t[:start]+abstract+t[end:]

intro=r'''\section{Introduction}
An inference budget limits how much text a language model may generate; a stopping rule decides which prefix is returned. The quality of that prefix depends on the consumer. A numeric extractor may accept a value embedded in an unfinished response, whereas an interface may require a complete final field. Evaluating stopping therefore requires three separate observations: what the consumer accepts, what answer it receives, and what computation was actually performed.

Acceptance need not persist during continuation. A final answer line can satisfy a terminal-field contract and then cease to satisfy it when more text is appended. Conversely, a model can revise an early complete but incorrect answer. The first case creates an opportunity for early stopping; the second creates a risk. An evaluation based only on final token counts or one extraction convention cannot distinguish these mechanisms.

A separate confound concerns monitoring. An entropy-based rule changes generation length while paying for full-vocabulary operations, host callbacks and synchronization. A shorter output need not have a shorter request interval. An output-invariant monitor provides a control: when it returns exactly the same token sequence as the unmonitored stopping rule, their runtime difference measures the added monitoring path under the tested execution conditions.

We organize this study around three questions. RQ1: under a declared terminal-answer contract, which paired outcomes reflect preservation of a deliverable answer, and which would reflect premature commitment? RQ2: when generated output is held fixed, what runtime overhead does the tested monitoring path introduce? RQ3: when completion is transient, does an additional entropy gate overlap the opportunity to stop? These questions concern interface-specific stopping, not a new reasoning model or joint resource scheduler.

The contribution has three parts. First, a formal account of prefix acceptance gives an exact paired correctness decomposition, a counterexample to universal correctness preservation, and an overlap condition for conjunction stopping. These are elementary analytical results used to specify testable mechanisms. Second, an evaluation framework separates contract outcomes, trajectory identity and monitoring overhead, with a distinct evidence requirement for each. Third, an existing two-model, two-task experiment provides a bounded case study with matched prompts, a shadow arm and isolated timing. Contract robustness and general performance superiority are not established by that experiment.

The study originated in an audit of JANUS, an earlier token-budget experiment whose tested TCJS and TokOnly paths were identical. The present evidence is narrower and concerns single-request generation. Historical audit findings are not pooled with the new cohort. The formal treatment in this revision was developed after the existing experiment; it is not described as part of that experiment's frozen protocol.

\subsection{Related work and the unresolved comparison}
Budget-aware reasoning studies how inference computation is used. \citet{wang2024} compare reasoning strategies under budgets; \citet{han2025} investigate token-budget-aware reasoning; and \citet{muennighoff2025} study test-time scaling and budget forcing. The present intervention operates at the stopping callback of greedy instruction-model generation. Those systems supply context, but their training, prompting and allocation procedures are not reproduced here.

Answer extraction affects measured performance. \citet{yu2025} examine automated extraction in xFinder. Here a fixed parser defines a delivery contract, while a more permissive extractor is diagnostic. Neither establishes semantic quality by itself. GSM8K \citep{cobbe2021} and ARC \citep{clark2018} provide numeric and multiple-choice cases, not comprehensive coverage of structured interfaces.

Direct boundary detection, structured-output validation and constrained decoding are necessary neighboring comparisons for an interface-level contribution. They differ in whether they detect an emitted boundary, validate a returned artifact or restrict the generation trajectory. The existing experiment tests only the first category and selected monitoring variants. It does not establish an advantage over the latter categories. A source-verified literature expansion and matched practical controls are required before claiming novelty or competitive superiority in that broader space.

'''
start=t.index('\\section{Introduction}')
end=t.index('\\section{Materials and methods}')
t=t[:start]+intro+t[end:]

theory=r'''\section{Formal analysis of interface-aware stopping}\label{sec:formal}
\subsection{Trajectories, acceptance and correctness}
Fix a prompt, decoder, model state and output cap $K$. Let $x_{1:t}$ be the generated token prefix and $d_t$ its decoded text, with special tokens handled by the declared decoder. Uniform returns at $T_U\leq K$, determined by EOS or the cap. Let $e_t$ indicate whether EOS has terminated the prefix. We analyze stopping policies conditional on a shared token trajectory up to their stopping times. This condition must be checked empirically; greedy decoding alone does not guarantee identity across implementations or hardware.

For an interface contract $\mathcal C$, define offline validity $A_{\mathcal C}(d_t,e_t)\in\{0,1\}$ and answer extraction $g_{\mathcal C}(d_t,e_t)$. Extraction is defined only for valid text. For gold answer $y$, credited correctness is
\begin{equation}
 Q_{\mathcal C}(t;y)=A_{\mathcal C}(d_t,e_t)\,
 \mathbf 1\{g_{\mathcal C}(d_t,e_t)=y\},
\end{equation}
with $Q_{\mathcal C}=0$ on invalid text. A semantic judgment or a complete-document validator is a separate endpoint and is not implied by $Q_{\mathcal C}$.

An online completion indicator $B_{\mathcal C}(t)$ certifies validity if the prefix is returned at that step. It must not use the gold answer or future tokens. In the implemented contract, a newline after the marked value provides the online certificate; EOS can certify an offline final value without that newline. Thus online and offline acceptance are related but not identical. Complete returns at
\begin{equation}
 T_C=\min\left(\{t<T_U:B_{\mathcal C}(t)=1\}\cup\{T_U\}\right).
\end{equation}
Using $t<T_U$ incorporates baseline EOS priority: an event at the same final step cannot save a token. The rule returns the emitted prefix and performs no gold-aware selection or rewriting.

Call validity continuation-stable on a class of non-EOS trajectories if $A_{\mathcal C}(d_t,0)=1$ implies $A_{\mathcal C}(d_s,0)=1$ for every later prefix in that class. A terminal-value contract generally lacks this property because later non-whitespace can invalidate its suffix. Validity stability and answer stability are different properties: even if later text remains valid, its extracted value can change.

\subsection{Paired gains do not imply a correctness guarantee}
\textbf{Proposition 1 (exact paired decomposition).} For $n$ paired questions, let $W$ count cases with $Q_C=1,Q_U=0$ and $L$ count cases with $Q_C=0,Q_U=1$, under the same scoring contract. Then
\begin{equation}\label{eq:paired}
 \widehat{\Delta Q}=\frac{1}{n}\sum_{i=1}^{n}(Q_{C,i}-Q_{U,i})=\frac{W-L}{n}.
\end{equation}
\emph{Proof.} Each binary pair contributes $+1$, $-1$ or $0$; summing gives the identity. This is an accounting identity, not a claim of novelty or a distributional guarantee.

For a win, Uniform's outcome can be invalid, or valid with a wrong value. Those mechanisms require separate classification. The existing record reports all 114 wins as cases without a valid terminal prediction under Uniform. That observation supports contract preservation, conditional on verification of the paired records; it does not show that the model solved 114 previously unsolved questions.

\textbf{Proposition 2 (no universal correctness dominance).} Shared prefixes and a sound online validity certificate do not imply $Q_C\geq Q_U$ on every question.

\emph{Proof by counterexample.} For gold answer 42, consider a trajectory that first emits a newline-terminated \texttt{\#\#\#\# 41}, then explanatory correction text, and finally \texttt{\#\#\#\# 42} followed by EOS. Complete returns the first valid but wrong answer. Uniform returns a final valid correct answer under the last-marker parser. Thus $Q_C=0$ and $Q_U=1$. Conversely, appending non-whitespace closure text after a correct marked line can give $Q_C=1,Q_U=0$ under the tested terminal-suffix rule. Both directions are possible.

A sufficient condition for correctness dominance on a trajectory class is stronger: whenever $Q_{\mathcal C}(T_U;y)=1$, the earliest certified prefix must extract the same correct answer, or no earlier certificate may occur. Merely requiring persistent validity does not ensure this answer consistency. The observed zero losses in the present cohort must therefore be accompanied by uncertainty intervals and tests of answer revision, repeated markers and marker-like content in quotations or examples.

\subsection{Conjunction stopping requires temporal overlap}
Let $G(t)$ collect the non-completion gates, including minimum step count and entropy stability. A non-latched conjunction returns at
\begin{equation}
 T_E=\min\left(\{t<T_U:B_{\mathcal C}(t)G(t)=1\}\cup\{T_U\}\right).
\end{equation}
\textbf{Proposition 3 (overlap and ordering).} On a shared trajectory, $T_C\leq T_E\leq T_U$. The conjunction stops strictly before Uniform if and only if a step $t<T_U$ satisfies both $B_{\mathcal C}(t)=1$ and $G(t)=1$.

\emph{Proof.} The conjunction's eligible steps are a subset of Complete's eligible steps. Taking their minima with the same fallback gives the ordering. An eligible step before $T_U$ is necessary and sufficient for earlier stopping.

The result does not identify why overlap is absent. A strict threshold, minimum-step gate, token indexing or a short completion window can each prevent it. Aggregate non-triggering is insufficient to distinguish these explanations. Trace-level gate occupancy and targeted ablations are needed. Latching a past completion event alone also does not preserve final validity: if generation continues, a system must specify whether it returns the new text or buffers and returns an earlier prefix, and account for the computation already spent.

\subsection{Output length and elapsed time are distinct quantities}
Write a policy's measured request interval on a paired trajectory as
\begin{equation}
 T^{\mathrm{wall}}_P=\sum_{t=1}^{N_P}b_t+M_P+r_P,
\end{equation}
where $N_P$ is actual generated length, $b_t$ is a common reference per-step execution cost, $M_P$ represents policy-specific monitoring and parsing work, and $r_P$ collects departures from that reference, including runtime interference and execution changes. These terms define an explanatory decomposition; the experiment does not identify each term separately.

\textbf{Proposition 4 (runtime break-even identity).} For $N_C\leq N_U$,
\begin{equation}\label{eq:break-even}
 T^{\mathrm{wall}}_C-T^{\mathrm{wall}}_U
 =-\sum_{t=N_C+1}^{N_U}b_t+(M_C-M_U)+(r_C-r_U).
\end{equation}
\emph{Proof.} Subtract the two decompositions and cancel shared reference steps. Consequently, fewer tokens are not sufficient for lower latency: saved reference execution time must exceed the added work and residual difference.

When Shadow and Complete have identical generated IDs and stopping lengths, the saved-step term is zero. Their contrast estimates the added monitoring path under the randomized within-session measurement design, subject to runtime variability. It does not isolate a hardware-invariant entropy cost or eliminate all session effects. The empirical evidence must report output identity, measurement boundaries and uncertainty together.

\subsection{From analytical statements to validation}
The framework yields separate obligations: paired outputs and alternate contracts for Proposition 1; revision and repeated-marker cases for Proposition 2; per-step gates and controlled ablations for Proposition 3; and output-matched repeated timing for Proposition 4. The existing experiment addresses parts of these obligations. The supplementary validation plan identifies the missing checks without treating them as executed experiments or retroactively adding them to the frozen protocol.

'''
t=t.replace('\\section{Materials and methods}',theory+'\\section{Materials and methods}',1)

# Add a retrospective evidence mapping; do not change the executed methods.
mapping=r'''\subsection{Evidence mapping and interpretation safeguards}
The primary contract is the one used in the completed experiment. This revision does not change that endpoint or recalculate reported values under a new parser. Contract validity, contract correctness, permissive extraction, document structure and independent semantic acceptance answer different questions. Only the first two are fully tabulated in the main results; diagnostic extraction is referenced in the original supplementary record, and human assessment remains pending.

The following interpretation rules apply. A contract gain is not called a reasoning gain. A negative result for Legacy or Conjunction is attributed to that implemented policy rather than to entropy stopping as a class. A shadow runtime contrast is conditional on exact output identity and the specified execution mode. Additional contract sensitivity, practical stopping controls and gate ablations are proposed follow-up work, not completed comparisons. Source records are required to independently check the manuscript's mechanism and provenance claims.

'''
t=t.replace('\\section{Results}',mapping+'\\section{Results}',1)

discussion=r'''\section{Discussion}
\subsection{What the existing evidence establishes}
The strongest result is an interface-specific separation of contract preservation, generated length and monitoring time. Complete obtained 114 additional credited answers without an observed paired correctness loss, yet saved at most 2.59\% of mean output tokens. Equation~\ref{eq:paired} accounts for this difference; it does not establish correctness dominance. The counterexample in Proposition 2 shows why an empirical zero-loss result needs a bounded interpretation.

The contract deliberately treats post-answer non-whitespace as invalid. In Qwen/GSM8K, 13 of the 14 gains followed a LaTeX display closure and one followed a code-fence closure. A prefix accepted by this parser can therefore be less complete as a document than its continuation. These examples support the proposed mechanism but also challenge the contract's application relevance. A strict consumer may require terminal-field compliance, while a reader or document renderer may prefer the full response. No deployed consumer is evaluated here, and practical delivery improvement remains unproven.

\subsection{What the controls identify and leave unresolved}
Exact Complete--Shadow token identity is an important control because it removes output-length differences from their runtime contrast. The observed overhead belongs to the complete monitoring path, including synchronization and callback choices. It is not an estimate of an unavoidable entropy-computation lower bound. Similarly, Complete's slower Qwen intervals show that small token savings can be outweighed by boundary-detection costs and runtime effects, consistent with Equation~\ref{eq:break-even}.

Marker is a negative control, not a competitive delivery method. Legacy retains historical candidate and indexing behavior, so its poor results may depend on those implementation details. Conjunction's near-identity with Uniform is consistent with absent gate overlap, but the aggregate result does not isolate threshold strictness, minimum-step effects or transient completion. Existing Legacy and Conjunction also differ in more than the completion condition. Single-factor ablations and trace-level gate diagnostics are required before a stronger mechanistic attribution.

\subsection{Contribution and scope}
The proposed contribution is an evaluation method for interface-dependent stopping: declare the consumer contract, verify actual trajectories, classify paired gains and losses, and measure observation cost with output-matched controls. The formal results specify why each check is needed; they are elementary consequences of the definitions, not claims of a new stopping optimum. The present case study illustrates the checks but does not yet establish cross-contract robustness, superiority over practical structured-output methods or a generally optimal entropy threshold.

\subsection{Threats to validity and required follow-up}
Construct validity is the leading concern. The current parser permits a marked line inside an unclosed wrapper and rejects later closure. Contract-sensitive rescoring, structural validation and semantic assessment must determine whether the credited gains correspond to useful deliveries. The original supplementary diagnostic results should be released in full rather than selectively quoted.

Independent human semantic audit remains pending. The existing record describes two blinded rating forms, a stratified sample and a private sampling key, but no completed ratings or agreement statistics. The 600 sampled outputs enrich contract/diagnostic disagreements; their unweighted mean cannot estimate population semantic accuracy. Any later assessment must preserve inclusion probabilities, independent pre-adjudication ratings and the distinction between design-weighted estimates and diagnostic subgroup summaries.

Internal validity requires access to source code, per-call records and frozen artifacts. This revision preserves the v6 experiment's reported values but does not independently verify its raw records. The claimed offline reproduction and protocol gates require auditable receipts. A frozen local protocol is not necessarily a public preregistration, and the new formal analysis is retrospective. The two-point noninferiority margin also needs an application-based justification in addition to its reported prespecification.

Timing uses one model session per model on the same GPU, with a fixed model-session order. Within-session randomization and question-cluster intervals do not capture independent-session variability or remove session-level drift. Additional independent sessions and monitoring-path profiling are especially important for sub-percent effects. Three repetitions per question are not three independent hardware experiments.

External validity is limited to two approximately 7B instruction-tuned models, two short-answer tasks, one 512-token cap, greedy decoding, batch size one and A800 hardware. Excluding 582 historically used GSM8K test questions protects the new comparison from that prior exposure but changes the eligible test population; it does not rule out model-training contamination. The results cannot establish budget-response curves, concurrent serving throughput, long-horizon agent behavior or general reasoning-model performance. Multi-budget and additional-model experiments are needed only if those broader claims are pursued.

\subsection{Historical JANUS evidence}
Historical JANUS results motivated these controls and are not pooled with the prospective cohort. The earlier audit found TCJS/TokOnly identity in 3,000 paired records and identical CompRoute results across nominal allowances 64, 128 and 256. A separate offline tokenizer-based reconstruction indicated that all three allowances were clamped to an effective cap of 64. Historical logs did not record every effective cap directly, and the reconstruction used a different tokenizer patch version, as documented in the archived audit. Those findings diagnose implementation naming and cap transformations, not scheduling efficacy. Historical prompts, scoring and sampling differ. Preserving those artifacts supports accountability; counting them as prospective replications would be inappropriate.

\section{Conclusions}
Stopping should be evaluated against the interface that consumes the returned prefix and the runtime that implements the decision. The formal analysis shows why completion need not persist, why early commitment can either preserve or lose a credited answer, and why an additional gate requires temporal overlap with completion. In the existing experiment, Complete preserved 114 additional terminal-contract answers with modest or zero token savings; output-matched entropy observation added measurable runtime, and the tested conjunction almost always behaved like Uniform. These findings support explicit contracts, paired trajectory audits and output-invariant monitoring controls. Practical delivery quality, robustness to alternative contracts and broader performance advantages remain to be tested with the specified follow-up controls and auditable experiment records.

'''
start=t.index('\\section{Discussion}')
end=t.index('\\section*{Data and code availability}')
t=t[:start]+discussion+t[end:]
start=t.index('A complete local archive contains')
end=t.index('\\section*{Declarations requiring author confirmation}')
t=t[:start]+r'''The v6 manuscript reports a local experimental archive containing the frozen protocol, revision pins, input manifests, per-call outputs, execution receipts, environment snapshots and analysis scripts. Those experimental materials were not included in the public manuscript package available for this revision, so their completeness and the reported computational reproduction could not be independently checked here. The available package contains manuscript sources, bibliography and a rendered PDF; file-integrity and typesetting checks do not validate the experiment. Before submission, provide an author-approved repository or review-access archive, redistribution-compliant reconstruction instructions and the complete supplementary metrics. A DOI may be added after an actual deposit; none is claimed here. Private human-audit keys must remain separate from public release material.

'''+t[end:]

# Verify that the full numerical results block and all five existing tables survived verbatim.
def block(text,a,b): return text[text.index(a):text.index(b)]
assert block(t,r'\section{Results}',r'\section{Discussion}') == block(original,r'\section{Results}',r'\section{Discussion}')
assert t.count(r'\begin{longtable}') == 5
assert block(t,r'\subsection{Frozen design and sampling}',r'\section{Results}').startswith(block(original,r'\subsection{Frozen design and sampling}',r'\section{Results}'))
(OUT/'main.tex').write_text(t)
shutil.copy2(SRC/'references.bib',OUT/'references.bib')
verification={
 'source_commit':'f0fd7d37f8f9cba4ea827a363db0f0b81798531f',
 'source_main_sha256':hashlib.sha256(original.encode()).hexdigest(),
 'results_block_unchanged':True,'original_executed_methods_retained_verbatim':True,
 'existing_tables':5,'new_experiments_run':False,'new_formal_analysis':'retrospective',
 'external_bibliography_verification':'pending',
 'new_empirical_claims_added':False
}
(OUT/'revision_checks.json').write_text(json.dumps(verification,indent=2)+'\n')
print(OUT)
