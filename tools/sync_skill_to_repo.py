"""把本地 WorkBuddy 技能目录同步到 Skills 仓库克隆（多技能集合）。

- 逐个技能同步：本地 ~/.workbuddy/skills/<name>/ → 仓库 Skills/<name>/
- 忽略 __pycache__ / *.pyc；文本统一 LF，避免 CRLF 噪声
- 仓库独有文件默认**不删**（如 LICENSE、仓库级 .gitattributes），只在报告里列出
- 需要删仓库冗余文件时显式加 --prune
用法:
  python sync_skill_to_repo.py                 # dry-run（默认，只看差异）
  python sync_skill_to_repo.py --apply         # 真正写入
  python sync_skill_to_repo.py --apply --prune # 同时删除仓库冗余文件
"""
import os
import shutil
import sys

# 路径无关：仓库根本身就从脚本位置推断（tools/ 的上级）。
# 本地技能目录默认 ~/.workbuddy/skills，可用 WB_SKILLS 覆盖（换机器/换用户时不必改代码）。
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.environ.get("TC_REPO") or os.path.dirname(_HERE)
LOCAL_ROOT = os.environ.get("WB_SKILLS") or os.path.join(
    os.path.expanduser("~"), ".workbuddy", "skills")

# 仓库收录的测试技能清单（新增技能加到此处即可）
SKILLS = [
    "testcase-generator",
    "test-case-sorter",
]

IGNORE_DIRS = {"__pycache__", ".git"}
TEXT_EXT = {".md", ".py", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini"}
# 仓库侧独有但属正常（本地技能目录没有），永不删除
KEEP_NAMES = {"LICENSE", "LICENSE.md", ".gitattributes", ".gitignore"}

apply = "--apply" in sys.argv
prune = "--prune" in sys.argv


def walk(root):
    out = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fn in filenames:
            if fn.endswith(".pyc"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root).replace("\\", "/")
            out.add(rel)
    return out


def same(a, b, rel):
    ext = os.path.splitext(rel)[1].lower()
    if ext in TEXT_EXT:
        try:
            ta = open(a, encoding="utf-8").read().replace("\r\n", "\n")
            tb = open(b, encoding="utf-8").read().replace("\r\n", "\n")
            return ta == tb
        except UnicodeDecodeError:
            pass
    return open(a, "rb").read() == open(b, "rb").read()


def write(a, b, rel):
    os.makedirs(os.path.dirname(b), exist_ok=True)
    ext = os.path.splitext(rel)[1].lower()
    if ext in TEXT_EXT:
        data = open(a, encoding="utf-8").read().replace("\r\n", "\n")
        with open(b, "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
    else:
        shutil.copy2(a, b)


total_add = total_copy = total_del = 0
for skill in SKILLS:
    src, dst = os.path.join(LOCAL_ROOT, skill), os.path.join(REPO_ROOT, skill)
    if not os.path.isdir(src):
        print(f"[跳过] 本地无该技能: {skill}")
        continue
    s, d = walk(src), walk(dst) if os.path.isdir(dst) else set()

    to_add = sorted(s - d)
    extra = sorted(d - s)
    to_del = [r for r in extra
              if os.path.basename(r) not in KEEP_NAMES] if prune else []
    kept = [r for r in extra if r not in to_del]
    changed = [r for r in sorted(s & d) if not same(os.path.join(src, r), os.path.join(dst, r), r)]

    print(f"== {skill}: 本地 {len(s)} / 仓库 {len(d)}")
    for label, items in (("新增", to_add), ("覆盖", changed), ("删除", to_del), ("仓库保留", kept)):
        if items:
            print(f"   {label}({len(items)}): {items if len(items) <= 12 else items[:12] + ['...']}")
    if not (to_add or changed or to_del):
        print("   无变化 ✓")

    total_add += len(to_add)
    total_copy += len(changed)
    total_del += len(to_del)

    if not apply:
        continue
    for rel in to_del:
        os.remove(os.path.join(dst, rel))
        print("   DEL ", rel)
    for rel in to_add + changed:
        write(os.path.join(src, rel), os.path.join(dst, rel), rel)
        print("   COPY", rel)

print()
if apply:
    print(f"同步完成：新增 {total_add} / 覆盖 {total_copy} / 删除 {total_del}")
else:
    print(f"[dry-run] 待新增 {total_add} / 待覆盖 {total_copy} / 待删除 {total_del}"
          f" —— 加 --apply 才会写入")
