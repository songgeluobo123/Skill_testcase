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
- 🚧 **Analysis gate (two phases)**: produce a Test Analysis Report first → generate only after confirmation; five hard constraints — no assumptions, mandatory business-rule consultation, terminology consistency, traceable sources, explicit multi-source attribution (see `references/analysis_gate.md`)
- 🧩 **Function-point decomposition**: break requirements into atomic function points, produce test points per point (5 dimensions)
- 🎯 **Four-scenario quota**: per function point, `1 positive : ≥3 negative/boundary` and **≥1 permission case** (not logged in / no permission / cross-role escalation); happy-path-only modules are flagged as imbalanced
- 📊 **Equivalence / boundary matrix (mandatory Step 3.5)**: enumerate each field's equivalence classes and boundary points, **one item per row**, each pointing back to concrete cases; `matrix_lint.py` blocks boundary-point shortage, unconsumed classes, fabricated requirement IDs, `[assumption]` over 30%, and column shift. It is the only fuel for the density gate — without it, "6 cases" just rephrases the same test
- 🎯 **Priority model**: unified P0–P3 scale (no P4) — P0 feasibility/concept testing, P1 main-flow must-test, P2 display completeness, P3 aesthetics & compatibility; P0 is release-blocking; share thresholds are adjustable per project at checkpoint ① (see "Priority model" below)
- 🛡️ **Quality prescreen gate (13 checks)**: 10 structural checks (coverage / method linkage / no fabrication / no duplication / priority share / expected-result checkability / title & unique ID / scenario-composition quota / orphan cases) + 3 depth checks (**per-requirement density / method-consistency / requirement-level scenario quota**) — fails the gate, no release
- 🔍 **Coverage audit (reverse direction)**: review an existing case library against requirements and produce **module-level** coverage plus three gap types (G1 missing / G2 imbalanced scenarios / G3 nominal coverage); reads `.xlsx` directly (see `references/coverage_audit.md`)
- 🧪 **Strength gate (blocks on P0 by default)**: requirement-level mutation — if the requirement were implemented wrongly (off-by-one threshold / inverted boundary / dropped negation / skipped action / reworded copy), would this case go red? Emits a **zero-strength rules / zero-contribution cases** list; **P0 rules must reach 90%** (P1–P3 warn only; `--mut-gate warn` switches to report-only). Prescreen only guarantees structure; strength is covered by `scripts/mutation_audit.py` (see `references/mutation_review.md`)
- 🕳️ **Defect loop (escape-driven, non-blocking by default)**: use **real defects** as external ground truth and back-compute "why the library stayed green when this bug happened" — outputs the **escaped-defect list**, **zero-coverage modules** (0 cases but real incidents) and **7 assertion-gap classes** (numeric / verbatim text / result-state / uniqueness / negation / boundary / phenomenon) plus a regression-backfill draft. Scope is deliberately narrowed to **"misses" are auto-judgeable, "caught" only as candidates** (human agreement on auto-judged catches: 0/5), so no interception rate is claimed and `--gate` defaults to `off` (see `references/defect_loop.md`)
- 📐 **Evidence-based writing patterns**: 10 reproducible practices reverse-engineered from a real high-quality case library (1,278 cases) — split environment/precondition columns, verb whitelist, assertion-style expected results, isomorphic groups, non-functional triad (see `references/excellent_case_patterns.md`)
- 🧠 **Memory mechanism**: records historical product constraints, reused across sessions
- 📤 **Multi-format output**: Excel (10 columns), XMind, Markdown test report / test points
- 📊 **Quality scoring**: 4 dimensions (coverage / accuracy / executability / priority); each dimension must reach 90+, auto-rollback if any below

### Priority model (P0–P3, unified scale)

This skill uses a single **P0–P3** scale (**no P1–P4 system, no P4**); a case's `priority` may only be `P0` / `P1` / `P2` / `P3`. The grading basis (five-dimension scoring D1–D5 + hard rules R1–R7 + grading SOP) is defined solely in `references/priority_p0_p3.md` (the single source of truth); the table below is only an overview.

| Level | Scope | Execution requirement | Suggested share |
|---|---|---|---|
| **P0** 🔴 | Feasibility/concept testing: landscape main-flow features, portrait-to-landscape functional equivalence, cross-end integration (release-blocking) | Run every build; 100% pass required to release | 10%~15% |
| **P1** 🟠 | Main-flow must-test: step-by-step main-flow features (per landscape UI flowchart), equivalence classes incl. exception scenarios, landscape layout & adaptation, AI data accuracy, device monitoring sensitivity, data security | Covered in every main test round (SIT / regression core) | 25%~35% |
| **P2** 🔵 | Display completeness: landscape UI renders completely; basic features not on the main flow (controls not occluded or overflowing) | Covered in normal iterations; optional in regression | 35%~45% |
| **P3** ⚪ | Aesthetics & compatibility: UI correctness and layout aesthetics, post-rotation layout, landscape responsiveness, Android/iOS version compatibility, certification-standard performance | Covered in full rounds or on demand; not a release gate | 10%~20% |

**Execution order (coverage grows with priority)**: smoke = P0 → main test SIT = P0+P1 → regression = P0+P1+sampled P2 → full / exploratory = P0~P3.

> Shares are enforced by `scripts/prescreen.py` (P0 default 10%~15%, P2 default 35%~45%); any out-of-range share triggers a re-prioritization rollback. Safety-critical projects can raise the P0 share at **checkpoint ①** (e.g. 40%~60%, see `references/quality_prescreen.md`); the memory mechanism reuses that preference across sessions.

## 3. Directory structure & layering

```
testcase-generator/
├── SKILL.md                 # Skill main instructions (6-step workflow + resource index; control plane)
├── README.md                # Chinese documentation
├── README.en.md             # English documentation
├── LICENSE                  # MIT
├── references/              # Methodology & specs (20 files; organized by layer below, physically flat)
│   ├── analysis_gate.md      # ★ analysis gate & hard constraints (two phases + STOP & ASK + H1–H5)
│   ├── case_design.md        # ★ sole authority for case authoring: design principles + 4-field spec + type mapping + priority + granularity
│   ├── naming_rules.md       # 7 hard naming red-lines + case-ID convention (TC-{module}-{seq})
│   ├── output_format.md      # 10-column Excel container definition + JSON field mapping
│   ├── xmind_output.md       # XMind output format spec
│   ├── function_points.md    # Function-point definition & decomposition (how to design)
│   ├── test_methods.md       # 6 black-box methods explained + ordered stacking
│   ├── testpoint_checklist.md# Test-point 5-dimension checklist + coverage list
│   ├── equivalence_matrix.md # ★ Equivalence/boundary matrix (mandatory Step 3.5 artifact, one item per row)
│   ├── multimodal.md         # Multimodal UI reading (image → cases)
│   ├── excellent_case_patterns.md # ★ evidence-based patterns (10 practices + self-check + anti-patterns)
│   ├── priority_p0_p3.md     # P0–P3 grading strategy (priority)
│   ├── data_rules.md         # Data-rule mapping library (test-data validation)
│   ├── quality_standards.md  # 4 quality standards + 0–100 scoring rubric
│   ├── quality_prescreen.md  # Quality prescreen 13 gates & thresholds
│   ├── coverage_audit.md     # ★ coverage audit (reverse): module drill-down + G1/G2/G3 gaps
│   ├── mutation_review.md    # ★ strength gate (P0 blocking): requirement-level mutation + killer_pattern spec
│   ├── defect_loop.md        # ★Defect loop (real-defect layer): escape gap G4 + gap classes + backfill order
│   ├── workflow.md           # Quality-assurance overview (five gates + one retrospective + accelerators)
│   └── memory_mechanism.md   # Memory mechanism
└── scripts/                 # Executable scripts (16, Python 3.13/3.14)
    ├── extract_requirements.py  # Step1 extract requirement rule list
    ├── map_coverage.py          # Case ↔ requirement coverage mapping
    ├── prescreen.py             # Quality prescreen gate (13 checks)
    ├── matrix_lint.py           # Step 3.5 matrix lint (boundary count / unconsumed classes / column shift)
    ├── coverage_audit.py        # Coverage audit (module drill-down + gap report)
    ├── mutation_audit.py        # Strength audit (requirement-level mutation, experimental, warn by default)
    ├── score_testcases.py       # Quality scoring
    ├── to_excel.py              # Export 10-column Excel (`--emit-template` for blank template; `--with-environment`/`--with-remark`/`--with-defect` stack to 11–13 columns)
    ├── defect_audit.py          # Defect loop (escaped list / zero-coverage modules / gap backfill, non-blocking)
    ├── selftest_defect.py       # Offline self-test for defect_audit (17 assertions)
    ├── to_xmind.py              # Export XMind
    ├── read_xmind.py            # Parse XMind input
    ├── read_ui_image.py         # Multimodal UI screenshot reading
    └── memory_io.py             # Memory read/write
```

### Layering (responsibilities & boundaries)

| Layer | Files | Boundary |
|---|---|---|
| **Control plane** | `SKILL.md` | 6-step orchestration + resource index; holds no detailed spec |
| **F. Process gate** | `analysis_gate.md` | Defines "when generation may start": two phases (analysis → confirmation → generation), report template, hard constraints H1–H5 |
| **B. Case authoring** | `case_design.md` (authority), `naming_rules.md`, `output_format.md`, `xmind_output.md`, `excellent_case_patterns.md` (evidence layer) | Defines "how a case is written": field rules, naming red-lines, Excel/XMind containers, proven patterns & anti-patterns |
| **A. Methodology** | `function_points.md`, `test_methods.md`, `testpoint_checklist.md`, `multimodal.md` | Defines "how to design" (decompose / methods / test points / reading) |
| **C. Priority** | `priority_p0_p3.md` | P0–P3 grading (sole priority authority) |
| **D. Data rules** | `data_rules.md` | Test-data validation mapping only |
| **E. Quality** | `quality_standards.md`, `quality_prescreen.md`, `coverage_audit.md`, `mutation_review.md` (strength gate), `defect_loop.md` (defect loop), `workflow.md`, `memory_mechanism.md` | Defines "how to verify": standards/scoring, prescreen gates, coverage audit (module drill-down), strength audit (requirement-level mutation), defect loop (real-incident reconciliation), mechanism overview, memory |

> **Boundary rule: each rule is defined exactly once (single source of truth).** `case_design.md` is the sole authority for case authoring; the priority model lives only in `priority_p0_p3.md` (P0–P3, sole authority); the scoring rubric lives only in `quality_standards.md`; data validation only in `data_rules.md`. Cross-references use "see xxx" instead of copying rules.

## 4. 6-step workflow

| Step | Name | Artifact |
|---|---|---|
| ① | Requirement deep analysis | `requirements.json` / `requirement_rules.json` / `requirements.md` + **Test Analysis Report** (🚧 STOP & ASK: continue only after confirmation) |
| ② | Function-point decomposition | Atomic function-point list (page/module dimension) |
| ③ | Test-point analysis | Test-point Markdown (5-dimension coverage + four-scenario quota) |
| ④ | Template confirmation | 10-column Excel template + naming/priority convention |
| ⑤ | Case design | Structured case JSON (`coverage_rule` / `design_method` / `priority`) |
| ⑥ | Case output | 10-column Excel + XMind + test report + quality score + optional coverage-audit report |
| ⑥.5 | Defect loop (optional; release wrap-up / legacy library) | Defect Loop Report + escaped-defect list + gap backfill draft (**non-blocking**) |

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

# 4. quality prescreen gate (13 checks; the 3 depth gates default to warn)
python scripts/prescreen.py ./out/test_cases_mapped.json \
    --requirement-rules ./out/requirement_rules.json --coverage-min 0.95

# 4b. coverage audit: module drill-down + three gap types (optional; first arg may be an .xlsx library)
python scripts/coverage_audit.py ./out/test_cases_mapped.json ./out/requirements.json \
    -o ./out/coverage-report.md

# 5. export 10-column Excel
python scripts/to_excel.py ./out/test_cases_final.json -o cases.xlsx

# 6. quality scoring (each dimension must be ≥ 90, rollback if any below)
python scripts/score_testcases.py ./out/test_cases_final.json

# 7. defect loop (optional: release wrap-up / legacy library; skipped when no defect data)
python scripts/defect_audit.py bugs.json cases.xlsx \
    --module-map ./out/module_map.json --layer 3 -o ./out/defect_loop_report.md \
    --emit-backfill ./out/regression_backfill.json
```

## 7. Dependencies

- Python ≥ 3.8 (3.13 recommended)
- `Pillow` (multimodal UI reading), `openpyxl` (Excel export) — install as needed per script

## 8. License

MIT — see [LICENSE](LICENSE).
