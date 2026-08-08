# testcase-generator · Test Case Generation Skill

> A WorkBuddy skill that turns a PRD / UI design image / XMind requirements into executable test cases (10-column Excel as the main artifact).

[中文文档](README.md)

---

## 1. What this skill solves

Writing test cases by hand hits three recurring problems: **incomplete requirement understanding, scattered use of test-design methods, and inconsistent output format.** This skill breaks the three apart with a *6-step workflow + 6 black-box methods + a quality prescreen gate*:

- **Help the AI understand requirements** — supports three inputs (PRD text, UI design image via multimodal reading, XMind requirements) and auto-extracts a "requirement rule list."
- **Help the AI apply the right methods** — Equivalence Partitioning, Boundary Value Analysis, Scenario Method, State Transition, Decision Table, Orthogonal Array, applied in order by scenario.
- **Keep output uniform** — a fixed 10-column Excel template + naming/format negative constraints so cases are import-ready.

## 2. Features

- 📥 **Multi-source input**: PRD (`.md`/`.txt`), UI screenshots (multimodal), XMind (`.xmind` parsing)
- 🧩 **Function-point decomposition**: break requirements into atomic function points, produce test points per point (5 dimensions)
- 🎯 **Priority model**: P0–P3 (safety-critical contexts auto-escalate P0 share)
- 🛡️ **Quality prescreen gate**: coverage / method linkage / no fabrication / no duplication / priority share — fails the gate, no release
- 🧠 **Memory mechanism**: records historical product constraints, reused across sessions
- 📤 **Multi-format output**: Excel (10 columns), XMind, Markdown test report / test points
- 📊 **Quality scoring**: 4 dimensions (coverage / accuracy / executability / priority); auto-rollback below threshold

## 3. Directory structure & layering

```
testcase-generator/
├── SKILL.md                 # Skill main instructions (6-step workflow + resource index; control plane)
├── README.md                # Chinese documentation
├── README.en.md             # English documentation
├── LICENSE                  # MIT
├── references/              # Methodology & specs (14 files; organized by layer below, physically flat)
│   ├── case_design.md        # ★ sole authority for case authoring: design principles + 4-field spec + type mapping + priority + granularity
│   ├── naming_rules.md       # 7 hard naming red-lines
│   ├── output_format.md      # 10-column Excel container definition + JSON field mapping
│   ├── xmind_output.md       # XMind output format spec
│   ├── function_points.md    # Function-point definition & decomposition (how to design)
│   ├── test_methods.md       # 6 black-box methods explained + ordered stacking
│   ├── testpoint_checklist.md# Test-point 5-dimension checklist + coverage list
│   ├── multimodal.md         # Multimodal UI reading (image → cases)
│   ├── priority_p0_p3.md     # P0–P3 grading strategy (priority)
│   ├── data_rules.md         # Data-rule mapping library (test-data validation)
│   ├── quality_standards.md  # 4 quality standards + 0–100 scoring rubric
│   ├── quality_prescreen.md  # Quality prescreen 6 gates & thresholds
│   ├── workflow.md           # Quality-assurance overview (prescreen/score/memory gates + accelerators)
│   └── memory_mechanism.md   # Memory mechanism
└── scripts/                 # Executable scripts (9, Python 3.13)
    ├── extract_requirements.py  # Stage1 extract requirement rule list
    ├── map_coverage.py          # Case ↔ requirement coverage mapping
    ├── prescreen.py             # Quality prescreen gate
    ├── score_testcases.py       # Quality scoring
    ├── to_excel.py              # Export 10-column Excel (`--emit-template` for blank template)
    ├── to_xmind.py              # Export XMind
    ├── read_xmind.py            # Parse XMind input
    ├── read_ui_image.py         # Multimodal UI screenshot reading
    └── memory_io.py             # Memory read/write
```

### Layering (responsibilities & boundaries)

| Layer | Files | Boundary |
|---|---|---|
| **Control plane** | `SKILL.md` | 6-step orchestration + resource index; holds no detailed spec |
| **B. Case authoring** | `case_design.md` (authority), `naming_rules.md`, `output_format.md`, `xmind_output.md` | Defines "how a case is written": field rules, naming red-lines, Excel/XMind containers |
| **A. Methodology** | `function_points.md`, `test_methods.md`, `testpoint_checklist.md`, `multimodal.md` | Defines "how to design" (decompose / methods / test points / reading) |
| **C. Priority** | `priority_p0_p3.md` | P0–P3 grading (sole priority authority) |
| **D. Data rules** | `data_rules.md` | Test-data validation mapping only |
| **E. Quality** | `quality_standards.md`, `quality_prescreen.md`, `workflow.md`, `memory_mechanism.md` | Defines "how to verify": standards/scoring, prescreen gates, mechanism overview, memory |

> **Boundary rule: each rule is defined exactly once (single source of truth).** `case_design.md` is the sole authority for case authoring; the priority model lives only in `priority_p0_p3.md` (P0–P3, sole authority); the scoring rubric lives only in `quality_standards.md`; data validation only in `data_rules.md`. Cross-references use "see xxx" instead of copying rules.

## 4. 6-step workflow

| Step | Name | Artifact |
|---|---|---|
| ① | Requirement deep analysis | `requirements.json` / `requirement_rules.json` / `requirements.md` |
| ② | Function-point decomposition | Atomic function-point list (page/module dimension) |
| ③ | Test-point analysis | Test-point Markdown (5-dimension coverage) |
| ④ | Template confirmation | 10-column Excel template + naming/priority convention |
| ⑤ | Case design | Structured case JSON (`coverage_rule` / `design_method` / `priority`) |
| ⑥ | Case output | 10-column Excel + XMind + test report + quality score |

## 5. Excel 10-column template

| # | Column | Notes |
|---|---|---|
| 1 | Case ID | Auto `TC-001`… (uses `id` from JSON when present) |
| 2 | Module | `module` |
| 3 | Case Name | `name` |
| 4 | Priority | `priority`, P0–P3 |
| 5 | Test Type | `test_type` (functional / exception / boundary / interface / compatibility / performance …) |
| 6 | Precondition | `precondition` |
| 7 | Steps | `steps` |
| 8 | Expected Result | `expected` |
| 9 | Stage | `stage` (quality-traceability column) |
| 10 | Design Method | `design_method` (quality-traceability column) |

## 6. Quick start (run the pipeline locally)

```bash
# 0. venv (needs Pillow, openpyxl)
python -m venv venv && venv/Scripts/pip install Pillow openpyxl

# 1. extract requirement rule list
python scripts/extract_requirements.py path/to/PRD.md -o ./out

# 2. design cases (produce test_cases.json with coverage_rule etc.)

# 3. coverage mapping
python scripts/map_coverage.py ./out/test_cases.json ./out/requirements.json -o ./out/test_cases_mapped.json

# 4. quality prescreen gate (lists gaps if it fails)
python scripts/prescreen.py ./out/test_cases_mapped.json \
    --requirement-rules ./out/requirement_rules.json --coverage-min 0.95

# 5. export 10-column Excel
python scripts/to_excel.py ./out/test_cases_final.json -o cases.xlsx

# 6. quality scoring (<70 triggers rollback)
python scripts/score_testcases.py ./out/test_cases_final.json
```

## 7. Dependencies

- Python ≥ 3.8 (3.13 recommended)
- `Pillow` (multimodal UI reading), `openpyxl` (Excel export) — install as needed per script

## 8. License

MIT — see [LICENSE](LICENSE).
