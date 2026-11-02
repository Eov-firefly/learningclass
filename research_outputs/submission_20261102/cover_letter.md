Dear Editor,

Please consider our manuscript, **“Budget-viable commitment for finite-language decoding under hard token budgets,”** as a research article.

The paper addresses a practical distinction in constrained language-model generation: a grammar-legal prefix need not have an accepting continuation inside the remaining output budget. We present a contract-explicit finite-language controller and characterize its feasible token support, conditional completion guarantee and preservation of already successful matched greedy grammar trajectories.

The empirical contribution is deliberately multidimensional. In two-model exploratory tight-budget comparisons, the controller improves native completion and prevents canonical budget dead ends relative to the matched grammar-only policy. It also retains successful grammar answers that global candidate scoring sometimes changes. These gains coexist with small or absent correct-yield gains. We retain the original inactive-budget comparison, strong deterministic and candidate-scoring baselines, canonical reference-reachability diagnostics and terminal-policy sensitivity. The paper does not claim universal accuracy or speed superiority. We believe its precise control guarantees and reproducible evidence of both benefits and failure boundaries are relevant to readers studying reliable and resource-constrained language-model systems.

The manuscript, supplementary material, implementation, raw experimental records and offline analyses are available at https://github.com/Eov-firefly/learningclass. The two studies' reused-cohort status and measurement boundaries are explicit. No human-rating endpoint is claimed.

All authors have agreed to submission. No funding was received for this study, and the authors declare no competing interests. The use of OpenAI conversational and coding assistants for manuscript editing and code preparation is disclosed in the manuscript.

Thank you for considering the manuscript.

Sincerely,

GuoZhen Bian, corresponding author\
On behalf of Ya Bai, GuoZhen Bian, Cheng Chang, ZhengGuang Cui, HaiLong Qin, ZhiHui Huang and Yue Wang\
China Telecom Cloud Network Operating System R&D Center, Beijing, China\
Email: biangz@chinatelecom.cn
