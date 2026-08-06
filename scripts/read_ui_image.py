#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
read_ui_image.py — 多模态读图骨架（UI 设计稿 → 元素抽取结构）

本脚本负责「机械准备」：校验图片、读取尺寸、输出一份元素抽取骨架 JSON，
供 Agent 用多模态视觉能力填充（识别页面元素 / 输入框 / 按钮 / 状态文案）。
读图本身的「理解」由 Agent 的视觉能力完成（与 references/multimodal.md 映射一致）。

输出骨架 schema（Agent 读取图片后填充 detected 列表）：
{
  "image": "<path>",
  "size": {"w":, "h":},
  "schema": "multimodal.ui_element_v1",
  "detected": [
     {"type":"input|button|text|state|nav", "label":"", "loc":"", "constraint":"", "notes":""}
  ],
  "note": "Agent 用视觉读取图片后，按 multimodal.md 映射生成表单验证/交互/等价类/边界值用例"
}

用法：
  python read_ui_image.py ui.png -o ui_elements.json
"""

import argparse
import json
import os
import sys

VALID = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")


def get_size(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            return {"w": im.width, "h": im.height}
    except Exception:
        return {"w": None, "h": None}


def main():
    ap = argparse.ArgumentParser(description="多模态读图骨架生成器")
    ap.add_argument("image", help="UI 设计稿图片路径")
    ap.add_argument("-o", "--out", help="输出骨架 JSON 路径")
    args = ap.parse_args()

    if not os.path.isfile(args.image):
        print(f"[错误] 找不到图片: {args.image}", file=sys.stderr)
        return 2
    if not args.image.lower().endswith(VALID):
        print(f"[错误] 不支持的图片格式（支持 {VALID}）", file=sys.stderr)
        return 2

    size = get_size(args.image)
    skeleton = {
        "image": os.path.abspath(args.image),
        "size": size,
        "schema": "multimodal.ui_element_v1",
        "detected": [],
        "note": ("Agent 用视觉读取本图，按 references/multimodal.md 映射生成用例："
                 "UI 元素→表单验证/交互用例；流程图→场景流用例；规则表→等价类/边界值用例。"
                 "无法确认的规则标注 [假设]。"),
    }
    out = args.out or (os.path.splitext(args.image)[0] + "_elements.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(skeleton, f, ensure_ascii=False, indent=2)
    print(f"[✓] 读图骨架已生成：{out}")
    print(f"    图片尺寸：{size}（Agent 请使用视觉能力读取图片并填充 detected 字段）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
