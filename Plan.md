# Plan.md: current and next iterations

Living work plan. Read [Project.md](Project.md) first; its hard rules (section 4) bind every task here. Background is in [REPROTRACE_Full_Project_Document.md](REPROTRACE_Full_Project_Document.md) ("the master").

- **Last updated:** 2026-11-26
- **Current iteration:** 2, Claim extraction (proposed)
- **State:** PAUSED by the user on 2026-11-26. Iteration 1 done; iteration 2 not started and not yet agreed

---

## 1. Agent instructions for this file

**Before work**
1. Read the handoff note (section 2) and blockers (section 3).
2. Check the codespace. Where it disagrees with this file, fix this file first.
3. Take the first `TODO` task whose dependencies are `DONE` and that has no open blocker.
4. Read the master sections named in the task before coding.

**During work**
- Mark one task `DOING` at a time.
- Work in the folders set by `Project.md` section 8.
- Put new ideas in the backlog (section 7), not in the current iteration.
- If a task needs a decision only the user can make, add it to section 4, mark the task `BLOCKED`, and take the next unblocked task.
- Do not bypass a blocker. In particular, **never run a third-party repo on the host because the sandbox is missing.**

**After work**
1. Set the status and fill in Evidence: the command run and its result, or a file path.
2. Rewrite the handoff note.
3. Move lasting decisions to the `Project.md` decision log. This file holds only work state.

**Statuses:** `TODO`, `DOING`, `BLOCKED`, `DONE`, `DROPPED` (with a reason). `DONE` means the acceptance check was run and passed. Partial work stays `DOING`.

**Iteration rollover**, when all tasks are `DONE` or `DROPPED`:
1. Add a short entry to section 8: result, what was learned, what was left.
2. Re-read master §9 and §17 and confirm the next iteration still serves them.
3. Expand the next iteration from section 6 into a task table in section 5, each task with an acceptance check.
4. Show the user the new plan and get agreement before starting.

---

## 2. Handoff note

Rewrite at the end of each session.

- **Paused:** the user stopped work on 2026-11-26. Do not start iteration 2 until they say so.
- **Done:** iteration 1, tasks 1.1 to 1.8 (section 8). No task is in progress.
- **Exists:** the verification core in `src/reprotrace`; at the pause, `uv run pytest -q` gave 145 passed and `uv run reprotrace audit fixtures/synthetic` worked. All evidence is synthetic. No git repository, so there is no history to roll back to.
- **To resume:** (1) run the tests; (2) get the user's answer on the iteration 2 table (section 5), Q7 and Q8; (3) start task 2.1. Tasks 2.1 to 2.6 need no LLM key; 2.7 needs Q8; 2.8 needs B2.
- **Watch out:** Docker was still not found at the pause, so B1 stands for iteration 4. The Bash tool failed on large multi-file heredocs; write files with the file tools.
- **Process slips in this session, not to repeat:** `.venv` and one generated synthetic `evidence/` output were deleted without asking; tasks 1.2 to 1.8 were not marked `DOING` one at a time.
- **Not project files:** `2026-11-26-*.txt` in the root is a chat export the user made. `evidence/audit-*` holds two generated synthetic outputs (git-ignored).

---

## 3. Blockers

| ID | Blocker | Blocks | Needed from |
|---|---|---|---|
| B1 | No sandbox: Docker not found; WSL fails with `REGDB_E_CLASSNOTREG` | Iteration 4, real demo | User: repair WSL and install Docker, or provide another Docker host |
| B2 | No LLM provider or API key chosen | Iteration 2 live extraction | User |
| B3 | No demo paper chosen (master §17.7) | Iteration 3 real audit, iteration 4 | User, from a shortlist the agent prepares |

---

## 4. Questions for the user

| ID | Question | Default until answered |
|---|---|---|
| Q1 | What is the submission deadline, and is a working demo due then or only slides? | None; iterations are ordered but undated |
| Q2 | Which LLM provider and budget? | Build against a small provider interface; no paid calls |
| Q3 | Fix Docker here or use another machine? | Continue with work that needs no sandbox |
| Q4 | Accept the defaults for T1 to T8 in `Project.md` section 11? T3 (verdicts) matters most | Use the defaults, marked provisional |
| Q5 | How is work split among the four members? | Single task queue |
| Q6 | Initialise git here, and is there a GitHub remote? | No git until approved |
| Q7 | Accept the verdict rules added in iteration 1 (`Project.md` section 6, steps 0 and 6, and decision log)? | Use them, marked provisional |
| Q8 | Which two or three openly licensed papers may be hand-labelled for task 2.7? | Agent prepares a shortlist |

---

## 5. Current iteration: 2, Claim extraction (proposed, not started)

**Goal:** a paper PDF becomes user-confirmed claim cards and draft experiment specs that the iteration 1 engine accepts.

**Serves:** master §9 "claim extraction with source references" and "protocol checklist"; §17.7 needs it for the end-to-end flow.

**Out of scope:** cloning repos, running third-party code, UI beyond the command line.

| ID | Task | Depends on | Master | Acceptance check | Status | Evidence |
|---|---|---|---|---|---|---|
| 2.1 | LLM provider interface with call, token and retry limits, plus a scripted fake | none | §8.3 | Tests run offline on the fake; exceeding a limit stops with an error; no key needed | TODO | |
| 2.2 | PDF text by page, with table text where possible | none | §6.1 | On a PDF we generate, each known sentence and table cell is found on the right page | TODO | |
| 2.3 | Claim extraction into `Claim` cards, with deterministic grounding | 2.1, 2.2 | §7, §13.2 | A quote or value not found on its cited page is rejected, not repaired | TODO | |
| 2.4 | Paper text handled as untrusted data | 2.3 | §13.2 | A PDF containing instructions changes no confirmation, limit or schema; output still has to pass grounding | TODO | |
| 2.5 | Draft `ExperimentSpec`: settings stated, inferred or missing | 2.3 | §8.1 | A setting absent from the test paper is `missing`, never filled in; stated settings pass grounding | TODO | |
| 2.6 | Gate 1 on the command line: confirm, edit or reject claims; set criteria; freeze | 2.3, 2.5 | §8.1, §8.3 | Nothing is confirmed by default; the approval hash matches the confirmed claim; an edited claim needs a new confirmation | TODO | |
| 2.7 | Hand-labelled claims for two or three papers, and a comparison script | 2.3 | §13.1 | Script reports found, missed and spurious claims, and wrong locations | TODO, needs Q8 | |
| 2.8 | One live provider, run on the labelled papers | 2.1, 2.7 | §13 | Results of 2.7 recorded with model and cost; limits stated | BLOCKED (B2) | |

**Exit condition:** one command takes a PDF to confirmed claims and frozen specs using the fake provider, all tests pass, and either 2.8 is done or B2 is still open and stated.

---

## 6. Next iterations

Outlines only. Expand at rollover. Order may change after Q1.

| # | Iteration | Outcome | Needs |
|---|---|---|---|
| 2 | Claim extraction | PDF to claim cards with page/table references; experiment checklist; gate 1 confirmation. Compared against hand-labelled claims | B2 for live calls |
| 3 | Artifact and consistency audit | Public repo fetched at a fixed commit as untrusted data, inspected **statically**; available/missing list; paper-to-code findings with file locations | Iteration 2, B3 |
| 4 | Sandboxed original run | Two-phase build and no-network run with limits; gate 2 approval; logs, metrics, environment and hashes captured. First prove isolation with our own test repos | B1, B3 |
| 5 | End-to-end demo | Orchestrator joins the modules with budgets and gates; simple UI; the demo paper runs from PDF to report | Iterations 1 to 4 |
| 6 | Harden and extend | Failure rehearsal, recorded backup demo, then "good to add": seeds, repair copy, evidence graph | Iteration 5 |

**Demo paper criteria** (for B3): public PDF and repo with a usable licence; scikit-learn or PyTorch; one clear metric in a table; small public data; runs on CPU in minutes; dependencies still install. Shortlist three, so there is a fallback.

**If time is short**, cut in this order: repair copy and seeds, evidence graph, UI polish, live extraction (use confirmed claim cards, labelled as such). Do not cut source links, gates, isolation, hashes or the integrity check.

---

## 7. Backlog

**Submission work** (from master §17; can run alongside the build)

| ID | Item | Master | Status |
|---|---|---|---|
| S1 | Add REPRO-Bench, PaperRepro, ARA and Dong et al. to the problem slide and market gap table | §17.1 | TODO |
| S2 | Add those four to the references slide | §17.2 | TODO |
| S3 | Verify Semmelrock et al., PaperBench and the Code Ocean wording at source | §17.3 | TODO |
| S4 | Open Artisan, ArtifactCopilot and VERITAS before citing | §17.4 | TODO |
| S5 | Cite ReproAgent as an arXiv preprint only | §17.5 | TODO |
| S6 | Fill in team details on slide 8 | §17.6 | TODO, needs user |
| S7 | Choose the demo paper and test the full flow | §17.7 | B3, then iteration 5 |
| S8 | Build and show the "computed, not copied" check | §17.8 | Task 1.7, then iteration 4 |
| S9 | Add market numbers only with sources | §17.9 | TODO |
| S10 | Check whether Papers with Code still operates before listing it as a current tool (not in the master; suggested) | §12 | TODO |

**Build ideas**

| Date | Idea |
|---|---|
| 2026-11-26 | Let the user review a `value_not_in_inputs` hit. Numeric datasets and low-precision claims (90%, 0.95) will often hit by coincidence and block Verified |
| 2026-11-26 | Gate 2 approves the spec hash only; it should also cover command, image and limits (iteration 4) |
| 2026-11-26 | Recompute a metric from saved predictions, the fourth method in `Project.md` section 7 (not built) |
| 2026-11-26 | Store the pre-run input files in the ledger too; only logs and outputs are stored now |

---

## 8. Completed iterations

### Iteration 1, Verification core (2026-11-26)

**Result:** exit condition met. `uv run reprotrace audit fixtures/synthetic` writes a ledger and report covering all five statuses (seven synthetic claims); `uv run pytest -q` gives 145 passed.

| ID | Task | Status | Evidence |
|---|---|---|---|
| 1.1 | Project skeleton | DONE | Fresh `.venv`, `uv sync --locked`, then pytest passed; commands in `Project.md` section 8 |
| 1.2 | Record schemas | DONE | `tests/test_schemas.py` |
| 1.3 | Evidence ledger | DONE | `tests/test_ledger.py`; also detects edited and removed records |
| 1.4 | Spec freezing | DONE | `tests/test_freezing.py`; re-freezing after a run is caught in `tests/test_verdict.py` |
| 1.5 | Metric comparison | DONE | `tests/test_comparison.py` |
| 1.6 | Verdict engine | DONE | `tests/test_verdict.py` |
| 1.7 | Integrity checks | DONE | `tests/test_integrity.py`, and `claim-copied` against `claim-verified` in `tests/test_recorded_audit.py` |
| 1.8 | Evidence report | DONE | `tests/test_recorded_audit.py`; the 94.2 against 92.1 case is Result mismatch |

Eleven deliberate breakages of the rules (mutations) each made a test fail.

**Learned:** the `Project.md` section 6 order let a matching number be Verified while the method was unknown, so step 6 was tightened (Q7). Searching for a copied number has unavoidable coincidental hits (backlog).

**Left:** run evidence is synthetic; nothing has been executed in a sandbox. Integrity checks trust file times and read lists that the iteration 4 runner must record. Removing the newest ledger entries is only detectable against the head hash printed in the report.
