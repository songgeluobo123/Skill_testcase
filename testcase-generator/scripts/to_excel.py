#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试用例 JSON → Excel 导出。

v1.11.5 起默认输出 **15 列（优秀库对齐表头）**：

15 列（默认）：用例编号 | 顶级功能模块 | 功能模块 | 设备型号 | 测试用例标题 | 测试优先级 |
              测试类型 | APP版本类型 | 测试环境 | 前置条件 | 测试步骤 | 预期结果 |
              实际结果 | 测试数据 | 备注

- 「测试环境」与「备注」内置在 15 列中（双前置列 / 场景展开不再需要开关）；
- 「实际结果」留给执行阶段回填，生成时恒为空；
- 「顶级功能模块 / 设备型号 / APP版本类型」读 JSON 的 `top_module / device / app_version`
  字段，无则分别留空 / 缺省「公共」/ 留空；
- `--legacy` 回到旧 10 列（兼容既有项目约定），旧变体 `--with-environment / --with-remark`
  仅在 legacy 模式下生效；`--with-defect` 两模式通用（追加「关联缺陷」列）；
- `--with-rtm` 与表头无关，照旧在第二个 sheet 追加需求追溯矩阵。

（列定义见 references/output_format.md；双前置列实证依据见 references/excellent_case_patterns.md 做法 1）

用法：
  python to_excel.py test_cases.json -o out.xlsx                    # 默认 15 列
  python to_excel.py test_cases.json -o out.xlsx --with-defect      # 16 列（+关联缺陷）
  python to_excel.py test_cases.json -o out.xlsx --legacy           # 旧 10 列
  python to_excel.py --emit-template 模板.xlsx                       # 空白模板（15 列）

输入 JSON 字段：id, module, top_module(可选), device(可选), name(或 title), priority,
  test_type(可选), app_version(可选), environment(可选), precondition, steps, expected,
  stage(可选), design_method(可选, 列表或字符串), test_data(可选), remark(可选),
  actual(可选, 执行后回填), defect(可选)

依赖：openpyxl
"""

import argparse
import json
import re
import sys

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    HAS_OPENPYXL = True
except ImportError:
    # 不在 import 期退出：那样连 --help 都看不了（早期就是这么坏的，
    # 还顺手把"缺依赖"报成 exit 2 = 参数错）。改为入库一个标志，
    # 由 main() 在做实事之前拒绝，并返回 4（环境缺依赖）。
    Workbook = Font = Alignment = PatternFill = None
    HAS_OPENPYXL = False

# ---------- v1.11.5：默认 15 列（优秀库对齐表头） ----------
COLUMNS = ["用例编号", "顶级功能模块", "功能模块", "设备型号", "测试用例标题", "测试优先级",
           "测试类型", "APP版本类型", "测试环境", "前置条件", "测试步骤", "预期结果",
           "实际结果", "测试数据", "备注"]
WIDTHS = [13, 13, 16, 10, 28, 9, 13, 14, 34, 34, 42, 42, 10, 16, 50]
COLUMN_DEFECT = "关联缺陷"
WIDTH_DEFECT = 28

# ---------- 旧 10 列（--legacy 兼容既有项目约定） ----------
LEGACY_COLUMNS = ["用例编号", "测试模块", "用例名称", "优先级", "测试类型", "前置条件",
                  "测试步骤", "预期结果", "适用阶段", "设计方法"]
LEGACY_WITH_ENV = LEGACY_COLUMNS[:5] + ["测试环境"] + LEGACY_COLUMNS[5:]
LEGACY_WIDTHS = [10, 16, 24, 8, 12, 34, 42, 42, 10, 24]
LEGACY_WIDTHS_ENV = LEGACY_WIDTHS[:5] + [36] + LEGACY_WIDTHS[5:]
WIDTH_REMARK = 60

PRIORITY_SET = {"P0", "P1", "P2", "P3"}


def load_cases(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "cases" in data:
        return data["cases"]
    if isinstance(data, list):
        return data
    raise ValueError("输入需为用例数组，或含 'cases' 键的对象")


def normalize_priority(p):
    return (p or "").strip().upper()


def dm_to_str(dm):
    if not dm:
        return ""
    if isinstance(dm, str):
        return dm
    return " / ".join(dm)


STEP_SPLIT_RE = re.compile(r"(?<!\d)(\d{1,2})\s*([.、．])(?!\d)")


def split_inline_steps(text):
    """把「1. 甲2. 乙3. 丙」拆成每步一行（导出层兜底规范化）。

    只拆**编号递增**的序列（1→2→3…），避免误伤版本号（v1.2.3）、小数（3.8-4.4）、
    日期（2025.03）——它们要么不匹配正则（点后接数字），要么编号不递增。
    已有换行的行逐行处理；单编号行原样返回。

    为什么在导出层做：预审 8b 管「生成时写对」，这里管「导出的表一定是对的」——
    使用者打开 Excel 时看到的就是分行结果，不用回头改 JSON。
    """
    if not text:
        return text
    out_lines = []
    for line in str(text).split("\n"):
        marks = list(STEP_SPLIT_RE.finditer(line))
        if len(marks) < 2:
            out_lines.append(line)
            continue
        nums = [int(m.group(1)) for m in marks]
        if not all(b == a + 1 for a, b in zip(nums, nums[1:])):
            out_lines.append(line)          # 编号不递增：可能是引用/手误，不拆
            continue
        seg, last = [], 0
        for m in marks:
            seg.append(line[last:m.start()])
            last = m.start()
        seg.append(line[last:])
        out_lines.extend(x.strip() for x in seg if x.strip())
    return "\n".join(out_lines)


def td_to_str(v):
    """测试数据：dict 逐对换行 `键=值`；数组「；」拼接；其余原样。"""
    if not v:
        return ""
    if isinstance(v, dict):
        return "\n".join(f"{k}={x}" for k, x in v.items())
    if isinstance(v, (list, tuple)):
        return "；".join(str(x) for x in v if str(x).strip())
    return str(v)


def defect_to_str(v):
    """关联缺陷：字符串原样；数组用「；」拼接；空值留空。"""
    if not v:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        return "；".join(str(x) for x in v if str(x).strip())
    return str(v)


def case_row15(c, seq, split=True):
    """15 列行：顶级功能模块/设备型号/APP版本类型/实际结果为新增位，缺省规则见文件头。"""
    cid = c.get("id") or f"TC-{seq:03d}"
    return [
        cid,
        c.get("top_module", ""),
        c.get("module", "未分类"),
        c.get("device", "公共"),
        c.get("name") or c.get("title") or "",
        normalize_priority(c.get("priority")),
        c.get("test_type") or "功能测试",
        c.get("app_version", ""),
        c.get("environment", ""),
        split_inline_steps(c.get("precondition", "")) if split else c.get("precondition", ""),
        split_inline_steps(c.get("steps", "")) if split else c.get("steps", ""),
        split_inline_steps(c.get("expected", "")) if split else c.get("expected", ""),
        c.get("actual", ""),
        td_to_str(c.get("test_data")),
        c.get("remark", ""),
    ]


def case_row_legacy(c, seq, with_env=False, with_remark=False, with_defect=False, split=True):
    cid = c.get("id") or f"TC-{seq:03d}"
    core = [
        cid,
        c.get("module", "未分类"),
        c.get("name") or c.get("title") or "",
        normalize_priority(c.get("priority")),
        c.get("test_type") or "功能测试",
    ]
    env = [c.get("environment", "")]
    tail = [
        split_inline_steps(c.get("precondition", "")) if split else c.get("precondition", ""),
        split_inline_steps(c.get("steps", "")) if split else c.get("steps", ""),
        split_inline_steps(c.get("expected", "")) if split else c.get("expected", ""),
        c.get("stage") or "功能测试",
        dm_to_str(c.get("design_method")),
    ]
    row = core + (env if with_env else []) + tail
    if with_remark:
        row = row + [c.get("remark", "")]
    if with_defect:
        row = row + [defect_to_str(c.get("defect"))]
    return row


def _style_header(ws):
    header_fill = PatternFill("solid", fgColor="305496")
    header_font = Font(bold=True, color="FFFFFF")
    wrap = Alignment(vertical="top", wrap_text=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = wrap
    return wrap


def _set_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w


def build_workbook(cases, legacy=False, with_env=False, with_remark=False,
                   with_defect=False, split=True):
    wb = Workbook()
    ws = wb.active
    ws.title = "功能测试用例"
    if legacy:
        cols = ((LEGACY_WITH_ENV if with_env else LEGACY_COLUMNS)
                + ([("备注")] if with_remark else [])
                + ([COLUMN_DEFECT] if with_defect else []))
        widths = ((LEGACY_WIDTHS_ENV if with_env else LEGACY_WIDTHS)
                  + ([WIDTH_REMARK] if with_remark else [])
                  + ([WIDTH_DEFECT] if with_defect else []))
        ws.append(cols)
        wrap = _style_header(ws)
        for i, c in enumerate(cases, 1):
            ws.append(case_row_legacy(c, i, with_env, with_remark, with_defect, split))
        _set_widths(ws, widths)
    else:
        cols = COLUMNS + ([COLUMN_DEFECT] if with_defect else [])
        widths = WIDTHS + ([WIDTH_DEFECT] if with_defect else [])
        ws.append(cols)
        wrap = _style_header(ws)
        for i, c in enumerate(cases, 1):
            row = case_row15(c, i, split)
            if with_defect:
                row = row + [defect_to_str(c.get("defect"))]
            ws.append(row)
        _set_widths(ws, widths)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = wrap
    return wb


def main():
    ap = argparse.ArgumentParser(
        description="测试用例 JSON → Excel（默认 15 列优秀库对齐表头；--legacy 回旧 10 列；"
                    "--with-defect 追加关联缺陷列；--with-rtm 追加需求追溯 sheet）")
    ap.add_argument("input", nargs="?", help="用例 JSON 文件路径")
    ap.add_argument("-o", "--output", required=False, help="输出 .xlsx 路径")
    ap.add_argument("--emit-template", metavar="PATH", help="仅生成空白模板到指定路径")
    ap.add_argument("--legacy", action="store_true",
                    help="输出旧 10 列（兼容既有项目约定）；默认 15 列优秀库对齐表头")
    ap.add_argument("--with-environment", action="store_true",
                    help="[仅 --legacy] 旧 10 列模式插入「测试环境」列（15 列默认已内置）")
    ap.add_argument("--with-remark", action="store_true",
                    help="[仅 --legacy] 旧 10 列模式追加「备注」列（15 列默认已内置）")
    ap.add_argument("--with-defect", action="store_true",
                    help="追加「关联缺陷」列（Step 6.5 缺陷反哺后回填）")
    ap.add_argument("--no-split-steps", action="store_true",
                    help="关闭导出层的编号步骤自动拆分（默认开启：按递增编号把"
                         "「1.甲2.乙」拆成多行；v1.12.2 起为默认）")
    ap.add_argument("--with-rtm", metavar="REQUIREMENTS",
                    help="在第二个 sheet 追加「需求追溯」矩阵（需 requirements.json）")
    args = ap.parse_args()

    if not HAS_OPENPYXL:
        print("[错误] 缺少依赖 openpyxl，无法导出 Excel。装法: pip install openpyxl",
              file=sys.stderr)
        print("       （退出码 4 = 环境缺依赖。既不是参数错，也不是数据不达标，"
              "别去改用例或改参数）", file=sys.stderr)
        return 4

    legacy = args.legacy
    if not legacy and (args.with_environment or args.with_remark):
        print("[提示] 15 列默认表头已内置「测试环境」「备注」列，"
              "--with-environment / --with-remark 仅在 --legacy 模式下生效（本次忽略）。",
              file=sys.stderr)

    if args.emit_template:
        wb = Workbook()
        ws = wb.active
        ws.title = "功能测试用例"
        if legacy:
            cols = ((LEGACY_WITH_ENV if args.with_environment else LEGACY_COLUMNS)
                    + ([("备注")] if args.with_remark else [])
                    + ([COLUMN_DEFECT] if args.with_defect else []))
            widths = ((LEGACY_WIDTHS_ENV if args.with_environment else LEGACY_WIDTHS)
                      + ([WIDTH_REMARK] if args.with_remark else [])
                      + ([WIDTH_DEFECT] if args.with_defect else []))
            sample = ["TC-001", "示例模块", "正确密码登录", "P1", "功能测试"]
            if args.with_environment:
                sample += ["1.手机连接可用网络\n2.滑板车设备上电"]
            sample += ["1. 用户已注册\n2. 网络正常",
                       "1. 输入手机号\n2. 输入密码\n3. 点击登录",
                       "1. 接受输入\n2. 掩码显示\n3. 跳转首页",
                       "功能测试", "场景法 / 等价类划分"]
            if args.with_remark:
                sample += ["【场景展开·2 项】…"]
        else:
            cols = COLUMNS + ([COLUMN_DEFECT] if args.with_defect else [])
            widths = WIDTHS + ([WIDTH_DEFECT] if args.with_defect else [])
            sample = ["TC-001", "APP", "APP-启动", "公共", "点击图标能正常进入启动界面",
                      "P1", "界面交互测试", "国内版本, 国外版本",
                      "1.手机连接可用网络", "1. App 已安装",
                      "1. 点击 APP 图标", "1. 应能进入 APP 启动界面",
                      "", "账号=test01", ""]
            if args.with_defect:
                sample += ["BUG-1234567（已修复）"]
        ws.append(cols)
        from openpyxl.styles import Font, PatternFill, Alignment
        _fill = PatternFill("solid", fgColor="305496")
        _font = Font(bold=True, color="FFFFFF")
        for cell in ws[1]:
            cell.fill = _fill
            cell.font = _font
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.append(sample)
        _set_widths(ws, widths)
        wb.save(args.emit_template)
        print(f"[✓] 已生成模板: {args.emit_template}（{len(cols)} 列）")
        return 0

    if not args.input or not args.output:
        print("[错误] 需提供 input 与 -o（或使用 --emit-template）", file=sys.stderr)
        return 2

    try:
        cases = load_cases(args.input)
    except Exception as e:
        print(f"[错误] 读取用例失败: {e}", file=sys.stderr)
        return 2

    bad = [c.get("id", "?") for c in cases if normalize_priority(c.get("priority")) not in PRIORITY_SET]
    if bad:
        print(f"[警告] 以下用例优先级非法（应为 P0-P3）: {bad[:10]}", file=sys.stderr)

    wb = build_workbook(cases, legacy=legacy, with_env=args.with_environment,
                        with_remark=args.with_remark, with_defect=args.with_defect,
                        split=not args.no_split_steps)
    if args.with_rtm:
        try:
            import coverage_audit
            rules = coverage_audit.load_rules(args.with_rtm)
            rtm = coverage_audit.build_rtm(cases, rules)
            coverage_audit.append_rtm_sheet(wb, rtm)
            print(f"[✓] 需求追溯 sheet 已追加（全覆盖 {rtm['summary']['full']} / "
                  f"部分 {rtm['summary']['partial']} / 未覆盖 {rtm['summary']['uncovered']} / "
                  f"孤儿 {rtm['summary']['orphans']}）")
        except Exception as e:
            print(f"[警告] 需求追溯 sheet 生成失败: {e}", file=sys.stderr)
    wb.save(args.output)
    if legacy:
        ncol = (len(LEGACY_COLUMNS) + (1 if args.with_environment else 0)
                + (1 if args.with_remark else 0) + (1 if args.with_defect else 0))
    else:
        ncol = len(COLUMNS) + (1 if args.with_defect else 0)
    print(f"[✓] 已生成 Excel: {args.output}（{len(cases)} 条用例，{ncol} 列）")
    return 0


if __name__ == "__main__":
    # 退出码：0=通过 / 1=不达标 / 2=输入·参数错误 / 3=脚本自身崩溃 / 4=环境缺依赖。
    # 3 必须与 1 分开：早期未捕获异常统一表现为 exit 1，会被误读成
    # "数据不达标"，让人对着不存在的质量问题返工。
    # 4 必须与 2 分开：缺 openpyxl 报成 2 时，调用方会去改参数而不是装包。
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        print("\n[内部错误] to_excel.py 自身崩溃（exit 3），不是数据不达标。", file=sys.stderr)
        print("请把下面的堆栈连同输入样例一起报给技能维护者：", file=sys.stderr)
        traceback.print_exc()
        sys.exit(3)
