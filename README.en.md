# Skills · WorkBuddy Test Skill Collection

This repository is a **collection of WorkBuddy testing skills**. Each skill lives in its own same-named subdirectory, usable standalone or chained into a full case-lifecycle pipeline: *generate → sort → deep-dive → audit → test plan*.

| Skill | Description |
|---|---|
| [`testcase-generator/`](testcase-generator/) | Turns a PRD / UI design image / XMind requirements into executable test cases (10-column Excel as the main artifact). Includes the analysis gate (STOP & ASK), 9-check quality prescreen, module-level coverage audit, mutation-strength gate, and defect-feedback loop |
| [`test-case-sorter/`](test-case-sorter/) | Orders test cases by business flow: five-layer model + six-level decision rules, restoring an execution-ready sequence (zero change to content or format) |
| [`testcase-module-deepdive/`](testcase-module-deepdive/) | Deep quality review of a **single module** with two safe batches: Batch A (fill gaps / harden weak expectations — additive only) → Batch B (dedupe / merge / rename — confirmed separately), always dry-run → confirm → apply → gates → read-back |
| [`testcase-triclass-audit/`](testcase-triclass-audit/) | Audits the "device model" column (shared / landscape-specific / portrait-specific) against the V2.1 tri-classification theory, detecting misclassification and cross-class duplicate copies |
| [`test-plan-generator/`](test-plan-generator/) | Generates a test plan Word document from the standard template: copy template → fill placeholders → save as `<Product> <Version> Test Plan.docx` (template never modified) |

Each skill's full specification lives in its `SKILL.md` (control plane) and `README.md`.

Release history: [CHANGELOG.md](CHANGELOG.md). 中文: [README.md](README.md)

---

## Directory convention

```
<skill-name>/
├── SKILL.md        # Control plane: workflow orchestration + resource index
├── README.md       # Skill documentation (optional)
├── references/     # Methodology & specs (single source of truth per rule)
└── scripts/        # Executable scripts (Python 3.13; stdlib + openpyxl/Pillow)
```

## Which skill when

| Stage | Skill |
|---|---|
| Have requirements, need cases from scratch | `testcase-generator` |
| Cases exist but order is unexecutable | `test-case-sorter` |
| One module is low quality and needs rework | `testcase-module-deepdive` |
| Case library spans devices and classification drifted | `testcase-triclass-audit` |
| Cases are ready, need a test plan deliverable | `test-plan-generator` |

## License

MIT by default. Per-skill `LICENSE` takes precedence.
