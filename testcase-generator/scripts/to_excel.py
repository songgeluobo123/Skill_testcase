#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
to_excel.py — 将结构化测试用例 JSON 转换为 Excel（Step 6 主产物，替代 test-case-export）

10 列（默认）：用例编号 | 测试模块 | 用例名称 | 优先级 | 测试类型 | 前置条件 | 测试步骤 | 预期结果 | 适用阶段 | 设计方法
11 列（--with-environment，"双前置列"实证模式）：在「前置条件」前插入「测试环境」列
11 列（--with-remark，"场景展开"模式）：在末尾追加「备注」列（用于范围性用例逐项展开子场景操作）
（列定义见 references/output_format.md；双前置列实证依据见 references/excellent_case_patterns.md 做法 1）

用法：
  python to_excel.py test_cases.json -o "test_output/v1.11 功能测试用例.xlsx"
  python to_excel.py test_cases.json -o out.xlsx --with-environment    # 测试环境/前置条件分离
  python to_excel.py test_cases.json -o out.xlsx --with-remark         # 末尾增加「备注」列
  python to_excel.py test_cases.json -o out.xlsx --with-environment --with-remark
  python to_excel.py --emit-template "模板.xlsx"        # 仅生成空白模板（含表头与示例行）
  python to_excel.py --emit-template "模板.xlsx" --with-environment

输入 JSON 字段（每条用例）：
  module, name(可选), priority(P0-P3), precondition, steps, expected,
  environment(可选, 仅供 --with-environment), test_data(可选), coverage_rule(可选),
  design_method(可选, 列表或字符串), test_type(可选, 测试类型), stage(可选, 适用阶段),
  id(可选, 作为用例编号), remark(可选, 仅供 --with-remark)

依赖：openpyxl
"""

import argparse
import json
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

COLUMNS = ["用例编号", "测试模块", "用例名称", "优先级", "测试类型", "前置条件", "测试步骤", "预期结果", "适用阶段", "设计方法"]
COLUMNS_WITH_ENV = COLUMNS[:5] + ["测试环境"] + COLUMNS[5:]
COLUMN_REMARK = "备注"
COLUMN_DEFECT = "关联缺陷"
WIDTHS = [10, 16, 24, 8, 12, 34, 42, 42, 10, 24]
WIDTHS_WITH_ENV = WIDTHS[:5] + [36] + WIDTHS[5:]
WIDTH_REMARK = 60
WIDTH_DEFECT = 28
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


def defect_to_str(v):
    """关联缺陷：字符串原样；数组用「；」拼接；空值留空。"""
    if not v:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple)):
        return "；".join(str(x) for x in v if str(x).strip())
    return str(v)


def case_row(c, seq, with_env=False, with_remark=False, with_defect=False):
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
        c.get("precondition", ""),
        c.get("steps", ""),
        c.get("expected", ""),
        c.get("stage") or "功能测试",
        dm_to_str(c.get("design_method")),
    ]
    row = core + (env if with_env else []) + tail
    if with_remark:
        row = row + [c.get("remark", "")]
    if with_defect:
        row = row + [defect_to_str(c.get("defect"))]
    return row


def build_workbook(cases, with_env=False, with_remark=False, with_defect=False):
    wb = Workbook()
    ws = wb.active
    ws.title = "功能测试用例"
    header_fill = PatternFill("solid", fgColor="305496")
    header_font = Font(bold=True, color="FFFFFF")
    wrap = Alignment(vertical="top", wrap_text=True)
    cols = ((COLUMNS_WITH_ENV if with_env else COLUMNS)
            + ([COLUMN_REMARK] if with_remark else [])
            + ([COLUMN_DEFECT] if with_defect else []))
    ws.append(cols)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = wrap
    for i, c in enumerate(cases, 1):
        ws.append(case_row(c, i, with_env, with_remark, with_defect))
    widths = ((WIDTHS_WITH_ENV if with_env else WIDTHS)
              + ([WIDTH_REMARK] if with_remark else [])
              + ([WIDTH_DEFECT] if with_defect else []))
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = wrap
    return wb


def main():
    ap = argparse.ArgumentParser(
        description="测试用例 JSON → Excel（默认 10 列；--with-environment 插入测试环境列；"
                    "--with-remark 追加备注列；--with-defect 追加关联缺陷列，可叠加）")
    ap.add_argument("input", nargs="?", help="用例 JSON 文件路径")
    ap.add_argument("-o", "--output", required=False, help="输出 .xlsx 路径")
    ap.add_argument("--emit-template", metavar="PATH", help="仅生成空白模板到指定路径")
    ap.add_argument("--with-environment", action="store_true",
                    help="输出 11 列：在「前置条件」前增加「测试环境」列（双前置列实证模式）")
    ap.add_argument("--with-remark", action="store_true",
                    help="在末尾追加「备注」列（范围性用例逐项展开子场景操作用）")
    ap.add_argument("--with-defect", action="store_true",
                    help="在末尾追加「关联缺陷」列（Step 6.5 缺陷反哺后回填；可与前两个参数叠加）")
    ap.add_argument("--with-rtm", metavar="REQUIREMENTS",
                    help="在第二个 sheet 追加「需求追溯」矩阵（需 requirements.json）")
    args = ap.parse_args()

    if not HAS_OPENPYXL:
        print("[错误] 缺少依赖 openpyxl，无法导出 Excel。装法: pip install openpyxl",
              file=sys.stderr)
        print("       （退出码 4 = 环境缺依赖。既不是参数错，也不是数据不达标，"
              "别去改用例或改参数）", file=sys.stderr)
        return 4

    if args.emit_template:
        wb = Workbook()
        ws = wb.active
        ws.title = "功能测试用例"
        cols = ((COLUMNS_WITH_ENV if args.with_environment else COLUMNS)
                + ([COLUMN_REMARK] if args.with_remark else [])
                + ([COLUMN_DEFECT] if args.with_defect else []))
        ws.append(cols)
        from openpyxl.styles import Font, PatternFill, Alignment
        fill = PatternFill("solid", fgColor="305496")
        font = Font(bold=True, color="FFFFFF")
        for cell in ws[1]:
            cell.fill = fill
            cell.font = font
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        sample_core = ["TC-001", "示例模块", "正确密码登录", "P1", "功能测试"]
        sample_env = ["1.手机连接可用网络\n2.滑板车设备上电"]
        sample_tail = ["1. 用户已注册\n2. 网络正常",
                       "1. 输入手机号\n2. 输入密码\n3. 点击登录", "1. 接受输入\n2. 掩码显示\n3. 跳转首页",
                       "功能测试", "场景法 / 等价类划分"]
        sample = sample_core + (sample_env if args.with_environment else []) + sample_tail
        if args.with_remark:
            sample = sample + ["【场景展开·2 项】…"]
        if args.with_defect:
            sample = sample + ["BUG-1234567（已修复）"]
        ws.append(sample)
        widths = ((WIDTHS_WITH_ENV if args.with_environment else WIDTHS)
                  + ([WIDTH_REMARK] if args.with_remark else [])
                  + ([WIDTH_DEFECT] if args.with_defect else []))
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[chr(64 + i)].width = w
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

    wb = build_workbook(cases, args.with_environment, args.with_remark, args.with_defect)
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
    ncol = (len(COLUMNS) + (1 if args.with_environment else 0)
            + (1 if args.with_remark else 0) + (1 if args.with_defect else 0))
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
