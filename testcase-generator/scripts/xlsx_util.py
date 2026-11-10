#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xlsx 打开工具：绕开 openpyxl read_only 的 dimension 陷阱。

## 为什么需要这个模块

`read_only=True` 时，openpyxl 不看真实单元格，而是读文件里 **dimension 元数据**
决定要遍历多少行。经腾讯文档 / WPS / 各类云端表格工具保存过的 xlsx，这个元数据
经常被写成 `A1:A1`（工具没回写真实范围）。

后果不是报错，是**静默读到 0 行**：

    read_only=True   -> ws.max_row = 1     -> 读到 0 条用例
    read_only=False  -> ws.max_row = 2412  -> 读到 2411 条用例

这在真实项目库上实测发生过（2411 行的正式用例库被读成空表）。而"读到空表"会被
下游解读成"这份库是空的"，进而得出"输入就绪度 0 分""覆盖率 0%"这类完全错误的结论。
**静默读空比报错危险得多——报错会让人去查，读空不会。**

## 取舍

用例库通常几百到几千行，普通模式的内存开销完全可接受（1 万行约百 MB 量级）。
用 read_only 省下的那点内存，不值得换来"静默读到空表"的风险。
因此本模块一律走普通模式。
"""


def open_workbook(path, **kw):
    """打开 xlsx，返回 Workbook。一律普通模式，不用 read_only（原因见模块 docstring）。

    缺 openpyxl 时抛 RuntimeError，由调用方决定退出码。
    """
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise RuntimeError("读取 .xlsx 需要 openpyxl（pip install openpyxl）")
    kw.setdefault("data_only", True)
    kw.pop("read_only", None)   # 显式挡掉：传了也不生效，避免"以为用了只读"
    return load_workbook(path, **kw)


def sheet_rows(ws, max_col=None):
    """把一张表读成 list[tuple]，跳过全空行。

    尾部全空的列用 max_col 截断（云工具常在右侧留一堆空列）。
    """
    out = []
    for row in ws.iter_rows(values_only=True, max_col=max_col):
        if any(v not in (None, "") for v in row):
            out.append(row)
    return out
