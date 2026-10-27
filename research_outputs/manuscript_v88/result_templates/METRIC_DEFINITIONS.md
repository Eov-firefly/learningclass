# Common scoring definitions

For each frozen eligible request, retain the raw return and status even on failure.

- D: declared submission, not explicit abstention. A baseline without controller states declares submission on a normal return; exceptions remain failures.
- A: D AND final consumer-contract validity AND applicable bound-field preservation. This is certified commitment.
- Q: A AND reference-answer match under the frozen extractor/equivalence rule.

Report primary quality as sum(Q)/n_all_eligible, certified coverage as sum(A)/n_all_eligible, and conditional accuracy as sum(Q)/sum(A). Conditional accuracy is NA when sum(A)=0. Never credit a reference-matching fragment from an invalid artifact as Q.

Also retain declared submissions, invalid submissions D*(1-A), raw invalid returns, binding violations, failure categories and all costs. Explicitly abstaining after validation does not convert an invalid trace into a correct answer or remove it from n_all_eligible.

For methods with no bound fields, P_b is vacuously true; match the user-visible consumer contract, and interpret differences in activation/binding as system comparisons. Matched-prefix causal ablations require the same binding rule and language.

The file named quality_by_cell.csv is a header-only output schema, not experimental data. All intervals, sample sizes and differences must be produced from a frozen protocol and complete raw/scoring archive. Do not impute missing results as zeros. Forward calls count entered model invocations, including invocations that raise an error; supplied-prefix and inserted tokens are separate from generated tokens.
