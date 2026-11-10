# Skills · WorkBuddy Test Skill Collection

This repository is a **collection of WorkBuddy testing skills**. Each skill lives in its own same-named subdirectory and can be used standalone.

| Skill | Description |
|---|---|
| [`testcase-generator/`](testcase-generator/) | Turns a PRD / UI design image / XMind requirements into executable test cases (10-column Excel as the main artifact). Includes the analysis gate (STOP & ASK), **14-check quality prescreen**, equivalence/boundary matrix gate, module-level coverage audit, mutation-strength gate, and defect-feedback loop |
| [`test-case-sorter/`](test-case-sorter/) | Orders test cases by business flow: five-layer model + six-level decision rules, restoring an execution-ready sequence (zero change to content or format) |

Each skill's full specification lives in its `SKILL.md` (control plane) and `README.md`.

Release history: [CHANGELOG.md](CHANGELOG.md). 中文: [README.md](README.md)

---

## Directory convention

```
<skill-name>/
├── SKILL.md        # Control plane: workflow orchestration + resource index
├── README.md       # Skill documentation (optional)
├── references/     # Methodology & specs (single source of truth per rule)
├── scripts/        # Executable scripts (Python 3.13; stdlib + openpyxl/Pillow)
└── tests/          # Regression (`python tests/run_all.py`, path-independent)
```

## Repo-level tools (`tools/`)

| Tool | Purpose |
|---|---|
| `tools/skill_selfcheck.py` | **Consistency self-check**: references / index / counts / item counts / rule counts / CLI flags / numbering continuity / field contract / deprecated wording — 14 categories (A–N). `--skill` points it at another copy of the same skill |
| `tools/sync_skill_to_repo.py` | **Local → repo sync**: compares and writes skill by skill; dry-run by default, `--apply` to write, `--prune` to delete extras. Normalizes text to LF |

Both are **path-independent**: the repo root is inferred from the script location (`tools/`'s parent); the local skill dir defaults to `~/.workbuddy/skills` and can be overridden with `TC_REPO` / `TC_SKILL` / `WB_SKILLS`.

```bash
python tools/skill_selfcheck.py          # 0 ERROR required
python tools/sync_skill_to_repo.py       # dry-run
python tools/sync_skill_to_repo.py --apply
```

## Reports (`docs/`)

| File | Content |
|---|---|
| `docs/整体自检报告_20261109.md` | Full self-check + feasibility assessment (**2026-11-09 snapshot**; 3 defects fixed in 1.9.3, P0/P1/P2 suggestions landed in 1.9.4) |
| `docs/真库校准报告_20261110.md` | Calibration against a real project library (1669 executed cases; **2026-11-10 snapshot**, corresponding to 1.9.5) |

> Both are **point-in-time snapshots**, not the current state. For current behavior, trust `CHANGELOG.md` and the docs inside each skill.

## Which skill when

| Stage | Skill |
|---|---|
| Have requirements, need cases from scratch | `testcase-generator` |
| Cases exist but order is unexecutable | `test-case-sorter` |

> Module-level deep-dive, tri-classification audit, and test-plan authoring are not published in this repository; they are maintained per project.

## License

MIT by default. Per-skill `LICENSE` takes precedence.
