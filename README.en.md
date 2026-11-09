# Skills · WorkBuddy Test Skill Collection

This repository is a **collection of WorkBuddy testing skills**. Each skill lives in its own same-named subdirectory and can be used standalone.

| Skill | Description |
|---|---|
| [`testcase-generator/`](testcase-generator/) | Turns a PRD / UI design image / XMind requirements into executable test cases (10-column Excel as the main artifact). Includes the analysis gate (STOP & ASK), 9-check quality prescreen, module-level coverage audit, mutation-strength gate, and defect-feedback loop |
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
└── scripts/        # Executable scripts (Python 3.13; stdlib + openpyxl/Pillow)
```

## Which skill when

| Stage | Skill |
|---|---|
| Have requirements, need cases from scratch | `testcase-generator` |
| Cases exist but order is unexecutable | `test-case-sorter` |

> Module-level deep-dive, tri-classification audit, and test-plan authoring are not published in this repository; they are maintained per project.

## License

MIT by default. Per-skill `LICENSE` takes precedence.
