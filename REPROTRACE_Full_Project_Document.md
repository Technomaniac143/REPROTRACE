# REPROTRACE: Full Project Document

Multi-agent research reproducibility auditing platform | K! Hacks 4.0, Agentic AI track | Team IMPACT | Prepared 25 November 2026

## 1. Purpose and status of this document

This document holds the full context of the REPROTRACE idea: where it came from, how it changed, what it is today, and what is still open. It is written so that a teammate, mentor or judge can read it from the top and understand the project without any other material.

Status: the idea is final at concept level. The 8-slide deck exists, and problem statement, solution abstract, features, USPs, risks and architecture text have all been written. Some items still need checking before submission (see section 17).

## 2. Event and team context

•         **Event:** K! Hacks 4.0, part of Kurukshetra 2027, an international techno-management fest run by CEG Tech Forum, College of Engineering Guindy, Anna University, Chennai.

•         **Team name:** IMPACT

•         **College:** Chennai Institute of Technology

•         **Problem track:** Agentic AI

•         **Team size:** four members. The team had limited prior familiarity with Agentic AI when the idea was chosen.

•         **Submission format:** online submission, 8 slides built from the K! Hacks template.

**Slide structure:**

1.       Cover (team name, college, track)

2.       Problem statement

3.       Solution abstract

4.       Architecture and system design

5.       Feasibility and unique selling points

6.       Market study and business model

7.       Research and references

8.       Team details (some placeholders still open)

## 2.1 How the idea was chosen

The team first explored hackathon tracks and shortlisted research-backed Agentic AI ideas. REPROTRACE (originally "Multi-Agent Research Reproducibility Verification") was selected because the problem is documented, the workflow suits multiple agents, the technical depth is strong, and a working demo is realistic for a small team.

## 3. Background: the reproducibility problem

Machine-learning papers report results such as "our CNN reaches 94.2% accuracy on Dataset X". To trust or reuse that result, another researcher has to rerun the experiment. In practice that is hard, because a paper is not a complete execution manual.

**What commonly goes missing or differs**

•         Preprocessing steps, data splits, hyperparameters and random seeds are not fully stated.

•         Code may be incomplete, outdated, or may not match the method described in the paper.

•         Datasets may be private, paid, restricted or removed.

•         Trained model weights may not be released.

•         Different hardware, drivers and library versions can change numerical results.

•         Randomness in training can produce different numbers even with the same code.

**Evidence the problem is real**

•         Semmelrock et al. (2025, *AI Magazine*) review the barriers to reproducibility in ML research: missing code and data, incomplete transparency, configuration, dependency and hardware variation, randomness, compute cost and publication incentives.

•         PaperBench (OpenAI, ICML 2025) tests whether AI agents can replicate 20 ICML 2024 papers across 8,316 gradable tasks. The best agent configuration scored about 21% on average. Important caveat: this is a score for agent task performance. It does **not** mean only 21% of papers are reproducible. These figures come from the earlier analysis and should be re-checked against the source before they appear on a slide.

## 4. The core problem statement

**The central problem is not that research code fails to run. It is that researchers cannot easily establish whether the experiment that ran actually supports the claim published in the paper.**

A paper's results depend on many separate things: the paper, code, data, settings and computer setup. Nothing connects a claim such as "94.2% accuracy" to the exact code and data that produced it.

### 4.1 What researchers face today

•         Verifying a result means manually tracing it across the paper, code, data and settings.

•         Papers often omit key details needed to rerun the experiment.

•         Released code may be incomplete or inconsistent with the paper.

•         When results differ, the cause is hard to identify: missing artifacts, a different environment, random variation or a genuine mismatch.

### 4.2 Why existing tools fall short

•         **Experiment trackers** (MLflow, DVC) record experiments a team runs and instruments itself. They do not read a paper or check its claims.

•         **Execution platforms** (Code Ocean, Whole Tale) package and run code. Code Ocean's own documentation says its verification does not check whether capsule results match the published article (confirm the exact wording from its documentation before quoting).

•         **AI reproduction agents** (Paper2Agent, ReproAgent) focus on turning papers into agents or generating code, not on auditing claims against independent evidence.

### 4.3 The real gap

Running the code is not the same as verifying the claim. Today that verification is manual, slow and inconsistent.

### 4.4 Impact

•         PhD scholars, ML labs and reviewers lose time building on results they cannot trust.

•         A failed rerun can be misread as "the paper is wrong" when the real cause was missing data or an infrastructure problem.

## 5. How the idea evolved

1.       **Original idea:** upload a paper, let AI agents read it, run its code, and check whether the results reproduce.

2.       **Clarification round:** the problem was made concrete with examples, proof, stakeholders and a narrow initial scope. Key principle set here: a failed run does not prove a paper is false, and "not verifiable" must be kept separate from "result mismatch".

3.       **Loophole and competitor review:** the review found 12 scientific loopholes, 6 agent and AI loopholes, several security risks and 6 product risks. It also showed that Paper2Agent, PaperBench and ReproAgent already overlap heavily, so "the first AI that reproduces papers" is not a defensible claim. Novelty as originally pitched was rated weak to moderate.

4.       **Pivot (current idea):** from a *reproduction agent* to a *claim verification and audit system*. The product is the evidence-backed verification, and agents are the technology that coordinates it.

5.       **Latest research check:** newer systems (REPRO-Bench, PaperRepro, ARA and a 2026 ML conference audit agent) already cover parts of the idea, so the USPs were cut from five to three and reframed (section 11).

**Two directions that were compared**

•         *Direction A, research reproduction agent:* reads a paper, writes or fixes code, tries to match the reported result. Crowded area.

•         *Direction B, claim verification and audit system:* checks original artifacts against specific claims, verifies execution evidence independently, and explains discrepancies. **This is the chosen direction.**

## 6. The solution

**One line:** REPROTRACE is a multi-agent AI platform that checks whether each claim in a machine-learning paper is supported by its code, data and independently run results, and reports the evidence claim by claim.

**Abstract (short):** REPROTRACE extracts the claims, checks that the code and data match the paper, runs the original experiment in a secure sandbox, and compares the results with the published claims.

**Abstract (long):** It takes a paper and its public code repository, extracts the specific claims to verify, and checks that the code, data and settings match what the paper describes. It then runs the original experiment in an isolated environment and compares the observed results with the published claims. Every conclusion links to its evidence: paper location, code files, execution logs and metrics. Any fixes the system suggests run separately, so the original result is never altered.

### 6.1 Worked example (hypothetical)

A paper claims: "Our proposed CNN achieves 94.2% accuracy on Dataset X."

1.       REPROTRACE finds the claim and records its page and table.

2.       It identifies the dataset, model, metric and settings.

3.       It inspects the linked GitHub repository and finds the implementation and config files.

4.       It checks whether the implementation follows the paper's stated protocol.

5.       It runs the original experiment in a restricted environment, if resources allow.

6.       It measures the observed accuracy and compares it with 94.2%, allowing for normal variation.

7.       It shows the evidence and explains any gap.

If the run gives 92.1%, the system does **not** conclude the paper is false. It reports a result mismatch and lists possible explanations: different preprocessing, a missing checkpoint, an unspecified random seed, or a different data split.

**Example report (hypothetical):** Claim 94.2%. Observed 92.1%. Status: Result mismatch, requires investigation. Findings: claim extracted (complete), repository located (available), model weights (missing), settings (partially matched), original execution (completed). Possible causes: checkpoint not available, training seed not specified, preprocessing needs confirmation. Conclusion: the claim was not fully reproduced under the available conditions. This is not evidence that the published result is false.

### 6.2 Verdict statuses

•         **Verified (Reproduced):** the specified experiment ran under sufficiently matching conditions and met the predefined comparison criteria.

•         **Partially reproduced (optional):** some claims or stages were verified, others were not.

•         **Result mismatch:** execution succeeded, but one or more results missed the comparison criteria.

•         **Not verifiable:** essential evidence, data, code or conditions were unavailable.

•         **Execution failed:** the run could not complete. The cause is classified, not treated as a scientific failure.

This is deliberately richer than a "reproducible / not reproducible" badge.

## 7. Core features (final five)

| # | Feature                 | What    it does                                                                                                                                            |
| - | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | **Claim Extractor**     | Finds each claim in the paper with its   source reference and builds an experiment checklist. Inferred or missing   details are flagged for user approval. |
| 2 | **Consistency Auditor** | Checks the repository, data and   checkpoints, lists what is available or missing, and confirms the code   matches the paper's method.                     |
| 3 | **Original Execution**  | Runs the untouched code in an isolated,   resource-limited sandbox and records logs, metrics and environment details.                                      |
| 4 | **Claim Verification**  | Compares observed results and settings   with each claim, allowing for run-to-run variation, and assigns a status.                                         |
| 5 | **Evidence Report**     | Explains why a result differs, tests any   fixes in a separate copy, and produces a claim-by-claim report linking every   verdict to its evidence.         |

**How the earlier eight modules were merged:** Paper Analyzer and Protocol Builder became the Claim Extractor. The Artifact Auditor became the Consistency Auditor. The Environment Manager and Execution Engine became Original Execution. The Verification Engine stayed. Discrepancy Diagnosis and the Evidence Report became one feature.

**Detail on the most important module, Claim Verification:** it checks whether the code follows the described method, whether the right data and evaluation settings were used, whether measured metrics agree with the paper, whether variation across runs explains differences, and whether the evidence is enough to support a conclusion. It uses deterministic comparisons wherever possible and an independent AI verifier only for ambiguous cases.

## 8. Architecture and workflow

**Flow:** Input, then Orchestrator, then the five modules, then the report.

### 8.1 End-to-end workflow

1.       **Submission:** the user provides the paper PDF, the GitHub repo link and any dataset or checkpoint links.

2.       **Paper understanding:** claim cards are created with source references. The user confirms which claims to audit.

3.       **Experiment specification:** a structured checklist per claim covers model, data, settings, metrics and conditions. Missing or inferred information is marked.

4.       **Artifact and consistency audit:** repo, data, weights, dependencies and configs are examined and compared with the paper.

5.       **Readiness and approval:** an isolated environment is prepared and resource needs are checked. The user approves the run before any code executes.

6.       **Original execution:** the untouched code runs. Logs, metrics, errors, environment details and artifact hashes are captured.

7.       **Independent verification:** observed method, conditions and results are compared with the published claims, with numerical tolerances.

8.       **Discrepancy diagnosis:** when results differ, likely causes are investigated. Any suggested fix runs in a separate repair branch and is reported separately.

9.       **Final report:** a claim-level evidence report with source references, execution history, limitations and status.

### 8.2 Agent design

Use one orchestrator and six specialist roles, not nine independent agents. Too many agents raise cost, complexity and the chance of disagreement.

•         **Orchestrator:** manages workflow, shared state, task order, budgets, approvals and retries.

•         **Paper Analyst:** extracts claims and methodology.

•         **Artifact Auditor:** inspects code, data and dependencies.

•         **Protocol Agent:** builds and checks the experiment specification.

•         **Environment and Execution Agent:** prepares the sandbox and runs the original code.

•         **Independent Verifier:** checks conditions, metrics and evidence.

•         **Diagnosis and Report Agent:** explains discrepancies and compiles findings.

**Critical rule:** the verifier must receive the original paper, the approved protocol and the recorded execution evidence. It must never just trust the execution agent's summary.

### 8.3 Supporting layers

•         **Evidence store:** logs, metrics, file hashes, timestamps and environment metadata. A shared structured experiment specification is the single source of truth between agents.

•         **Sandbox:** containers with no network access, no host credentials, read-only inputs where possible, disposable environments and CPU, memory and time limits. A container alone is not a complete security boundary, so these extra controls matter.

•         **Approval gates:** user confirms claims before auditing and approves the run before execution.

•         **Safety limits:** retry limits, time limits and compute budgets prevent endless debugging loops.

### 8.4 Suggested technology stack

LLM API with an orchestration framework such as LangGraph; Python with FastAPI; Docker for execution; PostgreSQL or SQLite for the evidence ledger; React or Streamlit for the frontend. These are suggestions and can change to fit the team's skills.

## 9. MVP scope and build priorities

**Hackathon MVP boundary**

•         Machine-learning papers only.

•         Public PDF and public GitHub repository.

•         Python experiments, initially PyTorch and/or scikit-learn.

•         One selected experiment and one or two reported metrics per paper.

•         Accessible data or a small permitted sample.

•         CPU or modest GPU execution.

Do not attempt arbitrary scientific-paper reproduction, and never run unknown repositories without a restricted environment.

| Priority           | Items                                                                                                                                                |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Must build**     | Claim extraction with source references,   GitHub artifact audit, protocol checklist, one original experiment run,   metric comparison, audit report |
| **Good to add**    | Separate repair branch, multiple seeds,   artifact hashes, evidence graph, discrepancy diagnosis                                                     |
| **Future roadmap** | More frameworks, large GPU workloads,   private datasets, journal integration, collaboration, institutional reports                                  |

**Demo plan:** pick one small, known paper with a manageable experiment and walk the full flow end to end. There is no need to prove it can reproduce huge state-of-the-art models.

## 10. Feasibility

•         **Technically realistic:** LLM extraction, Docker sandboxing and metric comparison are established techniques.

•         **Scoped for four people:** only the "must build" row is required for the demo.

•         **Honest by design:** failures are classed as Mismatch, Not verifiable or Execution failed, never "paper is false".

•         **Demo-ready:** one pre-selected paper that works end to end is more convincing than broad but shaky coverage.

## 11. Unique selling points and novelty

### 11.1 Final three USPs

1.       **Claim-to-Evidence Traceability (headline).** Every verdict links to its paper location, code, run logs and file hashes. Chain: published claim, then method and code, then artifacts (data, split, weights, environment), then execution evidence (run ID, logs, metrics, timestamps, hashes), then the verification report.

2.       **Integrity-Guarded Verdicts.** The original run stays untouched, and results are verified as truly computed in the run, not copied from the paper or read from saved files. Any agent-assisted fix is isolated and disclosed.

3.       **Independent, Self-Serve Audit.** Works on any public ML paper and repository with no author input or venue workflow, and gives each claim a clear status with the cause.

**Tagline:** Other tools run the code. REPROTRACE verifies the claim.

### 11.2 Why the original five USPs were cut to three

The original five were claim-level auditing, paper-to-code consistency, evidence-backed verification, original-versus-repaired execution and explainable discrepancy diagnosis. Research showed that (a) each restated a feature already on the solution slide, and (b) several are already done by recent systems. They were merged or removed:

| Original    USP              | Same    as feature               | Already    done by others? | Outcome                    |
| ---------------------------- | -------------------------------- | -------------------------- | -------------------------- |
| Claim-level auditing         | Claim Extractor and Verification | Yes, per table or figure   | Merged into USP 1          |
| Paper-to-code consistency    | Consistency Auditor              | Yes (REPRO-Bench)          | Removed, kept as a feature |
| Evidence-backed verification | Evidence Report                  | Partly                     | Merged into USP 1          |
| Original vs. repaired        | Original Execution               | Partly                     | Merged into USP 2          |
| Explainable diagnosis        | Evidence Report                  | Yes                        | Removed, kept as a feature |

### 11.3 Novelty (what can honestly be claimed)

No single component is new: multi-agent paper analysis, execution, debugging, experiment tracking and provenance all exist. The novelty is the combination and the purpose: a **verification-first** approach that connects each paper claim to its implementation, configuration and independent run evidence, keeps original and AI-repaired results strictly separate, and gives explained verdicts instead of a pass/fail badge.

Three separate questions are checked, not one:

1.       Does the implementation match the paper's methodology?

2.       Does the executed experiment follow the intended configuration?

3.       Do the observed results agree with the reported claims within appropriate criteria?

These are proposed design choices, **not** a claim that no research system has ever implemented any one of them.

## 12. Competitive landscape

| Category                           | Examples                            | What    it does                                                                                                           | What    is missing                                             |
| ---------------------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| Paper-code discovery               | Papers with Code                    | Links papers to code, datasets,   leaderboards                                                                            | No execution or claim audit                                    |
| Experiment tracking                | MLflow, DVC                         | Records parameters, code versions,   metrics                                                                              | Only for experiments a team instruments   itself               |
| Execution platforms                | Code Ocean, Whole Tale              | Packages and runs code and environments                                                                                   | Do not check results against paper claims                      |
| AI reproduction agents             | Paper2Agent, ReproAgent, PaperBench | Turn papers into agents, generate code,   benchmark agents                                                                | Not an independent claim audit service                         |
| Agentic reproducibility assessment | REPRO-Bench, PaperRepro, ARA        | Assess reproducibility with agents                                                                                        | Mostly social science, or paper-only (ARA   does not run code) |
| Conference audit agent             | Dong et al. (2026)                  | Audits ML conference papers, executes   code per table or figure, keeps the original code unchanged, preserves   evidence | Needs authors' checklists and a venue-run   workflow           |
| Human-led review                   | ACM artifact review and badging     | Reviewers check artifacts and award   badges                                                                              | Manual, slow, not scalable                                     |

**Closest overlap:** the Dong et al. conference audit system, and Paper2Agent on the paper-understanding side. **Do not claim REPROTRACE is the first AI to reproduce or audit papers.** The defensible position is an independent, self-serve, claim-level audit with a traceable evidence trail.

## 13. Risks, loopholes and mitigations

### 13.1 The two headline risks (for the slide)

| Risk                                                            | Mitigation                                                                                      |
| --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Unsafe code: unknown repos could harm the   system              | Isolated sandbox with no network and user   approval before any run                             |
| Wrong verdicts: the AI may misread a   claim or blame the paper | Claims are source-linked and   user-confirmed, and failures are never labelled "paper is false" |

### 13.2 Fuller loophole list and fixes

**Scientific and technical**

•         Paper is not a full manual: mark inferred or missing details instead of inventing them.

•         Code may not match the paper: record the commit hash and compare behaviour with the described method.

•         Dataset or weights unavailable: support accessible data first and mark the rest Not verifiable.

•         Hardware and randomness: record environment details, run multiple seeds where feasible, compare distributions not single numbers.

•         **Most dangerous: a matching metric from the wrong method.** Verify methodology, splits, preprocessing and intermediate outputs, not just the final number.

•         A failed run does not prove irreproducibility: separate infrastructure failure, artifact failure and result mismatch.

•         Partial scope: define exactly which claims are in scope and report claim by claim.

•         Statistical comparison: use paper-specific tolerances, not one universal pass or fail threshold.

•         Agent fixes can change the experiment: preserve original code, log every patch, report original and repaired runs separately.

•         Some experiments cannot be reproduced by code alone (clinical, physical, human studies): restrict version one to computational ML.

**Agent and AI**

•         Hallucinated details: link every extracted claim to its page, table or section.

•         Agents disagree: use a shared structured specification as the single source of truth.

•         Infinite loops: set retry, time and compute limits.

•         Biased verifier: use deterministic checks, independent verification and human review for ambiguous cases.

•         LLM output is not evidence: store real logs, outputs, metrics, hashes and environment data.

•         Malicious repository text: treat repository content as untrusted data that can never override system policy.

**Security and infrastructure:** malicious code, data exfiltration, resource exhaustion, dependency attacks, license limits and privacy of unpublished research. Minimum protection: restricted network, no host credentials, quotas, read-only inputs, disposable environments and explicit user consent before running code.

**Product and adoption:** who pays, compute cost, trust in automated verdicts (researchers will want evidence, not a badge), misreading "not reproduced" as fraud, and an over-large scope for a hackathon.

**Known limitations of the newest evidence:** a 2026 conference deployment found that agent assessments varied between repeated runs and that human reviewers corrected agent mistakes. REPROTRACE keeps the user in the loop at two approval points for this reason.

## 14. Users, market and business model

**Users**

•         PhD scholars and graduate students: check whether a published method is worth building on.

•         University ML labs: validate external research and compare their own implementations.

•         Conference and journal reproducibility reviewers: get structured evidence for manual assessment.

•         Corporate R&D teams: check whether outside research is supported before adopting it.

•         **First target:** research scholars and university ML labs. Reviewers, publishers and corporate R&D come later.

**Business model (proposed)**

•         Free tier with a limited number of audits for students.

•         Pro or Lab subscription with more audits and higher compute limits.

•         Pay-per-audit for heavy experiments, covering compute cost.

•         Institutional licences for universities, publishers and conferences.

•         API so reviewers' tools can pull machine-readable evidence reports.

**Growth path:** students and labs, then conference reviewers, then publishers and corporate R&D.

Market-size figures are intentionally not included because no reliable source was found. Add numbers only with a citation.

## 15. Limits the project should state openly

REPROTRACE can help assess whether a computational result is reproducible **under the tested conditions**. It cannot establish that a scientific hypothesis is true, that a study is free of bias, or that an author acted fraudulently. Saying this plainly makes the project more credible.

## 16. Prepared answers for judges

| Question                                                               | Answer                                                                                                              |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| How are you different from Paper2Agent?                                | It turns papers into reusable agents. We   audit specific claims against independent evidence.                      |
| Why not just Docker or Code Ocean?                                     | They package and run code. We also check   whether the run supports the paper's claim.                              |
| How are you different from conference   audit agents like Dong et al.? | They need authors' checklists and a venue   workflow. We work independently on any public paper and repo.           |
| What if the paper has no code?                                         | We report the missing artifacts and mark   the claim Not verifiable.                                                |
| What if the accuracy differs?                                          | We investigate data, seeds,   preprocessing, environment and variation. We never label the paper wrong.             |
| How do you prevent hallucination?                                      | Claims are source-linked and   user-confirmed, and verdicts rest on logs and deterministic checks.                  |
| What if the code is malicious?                                         | Isolated sandbox, no network, resource   limits and user approval before execution.                                 |
| Can you reproduce every paper?                                         | No. The first version covers accessible   computational ML experiments.                                             |
| What is innovative?                                                    | Claim-to-evidence traceability,   integrity-guarded verdicts, and a self-serve independent audit in one   workflow. |

## 17. Open items before submission

1.       Update the problem slide and market gap table to mention the newer systems (REPRO-Bench, PaperRepro, ARA, Dong et al.).

2.       Add those four to the references slide.

3.       Verify Semmelrock et al. (2025) and PaperBench (Starace et al., ICML 2025) directly. Confirm the Code Ocean statement from its own documentation.

4.       Open Artisan, ArtifactCopilot and VERITAS before citing them. They are known only through another paper's related-work section.

5.       ReproAgent: cite it as an arXiv preprint (arXiv:2608.24291). The earlier claim that it appeared at ACL Findings 2026 was not confirmed.

6.       Fill the placeholder team details on slide 8.

7.       Choose the demo paper and test the full flow once end to end.

8.       Build and show the "computed, not copied" check, since USP 2 depends on it.

9.       Add market numbers only with sources.

## 18. References

**Checked directly during research**

•         Miao et al. (2026). Reimagining research papers as interactive and reliable AI agents (Paper2Agent). *Nature*, published 16 September 2026. DOI 10.1038/s41586-026-11044-y.

•         Hu et al. (2026). ReproAgent: Contract-Guided Paper-to-Code Reproduction. arXiv:2608.24291, August 2026.

•         Hu et al. (2025). REPRO-Bench: Can Agentic AI Systems Assess the Reproducibility of Social Science Research? Findings of ACL 2025. arXiv:2507.18901.

•         Zhang et al. (2026). PaperRepro: Automated Computational Reproducibility Assessment for Social Science Papers. arXiv:2603.00058.

•         Riehl et al. (2026). ARA: Agentic Reproducibility Assessment for Scalable Support of Scientific Peer-Review. arXiv:2605.02651, May 2026.

•         Dong, Zhang and Zheng (2026). Author-in-the-loop Agentic Reproducibility Auditing for a Machine Learning Conference. arXiv:2610.22465.

**Cited from earlier analysis, still to verify**

•         Semmelrock et al. (2025). Reproducibility in machine-learning-based research: Overview, barriers, and drivers. *AI Magazine*.

•         Starace et al. (2025). PaperBench: Evaluating AI's Ability to Replicate AI Research. OpenAI / ICML 2025.

•         Code Ocean documentation (Compute Capsules, verification process); Whole Tale, MLflow and DVC documentation; Papers with Code; ACM artifact review and badging; IEEE reproducibility-review guidance.

**Known only secondhand (listed in the Dong et al. paper)**

•         Baek and Pradel (2026), Artisan, arXiv:2602.10046.

•         Wu et al. (2026), ArtifactCopilot (agent-based software artifact evaluation), arXiv:2602.02235.

•         Liu et al. (2026), VERITAS, arXiv:2607.02931.

## 19. Slide-ready text (final wording)

**Problem in one line:** The problem is not that research code fails to run. It is that researchers can't easily tell whether the experiment they ran actually proves the paper's claim.

**Solution in one line:** REPROTRACE is an AI platform that checks whether each claim in a machine-learning paper is supported by its code, data and independently run results, and reports the evidence claim by claim.

**USPs:** Claim-to-Evidence Traceability; Integrity-Guarded Verdicts; Independent, Self-Serve Audit.

**Risk line:** Every claim is linked to its source in the paper and confirmed by the user, and a failed run is never reported as "the paper is wrong".