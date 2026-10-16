#!/bin/bash
# 复刻 run.py 的调用方式,有两处刻意偏离,见 dataset/EXPERIMENT.md:
#  1. < /dev/null  —— claude -p 在非 TTY 下会读 stdin,批量脚本的文件重定向
#     会被它当成 prompt 的一部分吞进去(曾污染 49 次运行)
#  2. bypassPermissions —— run.py 用 acceptEdits + Bash(python:*) 白名单,但 agent
#     常写 `cd DIR; bin/python ...` 这类复合命令,匹配不上而被静默拒绝,
#     整次运行作废却不报错。目录范围仍由 cwd 与 --add-dir 限定。
#  3. 第五个参数选 prompt 版本(hypo / hypo_v2)。prompt 以 worker 本地 slash
#     command 的形式提供,每次运行前从根目录重新拷贝:改了一份跑了另一份的话,
#     消融实验会变成在比较两个说不清的东西。
WORKER="$1"; TARGET="$2"; VENV="$3"; EXTRA="$4"; CMD="${5:-hypo}"
ROOT=/Users/auderyliu/Documents/NTU/project/agentic-pbt-main
[ -f "$ROOT/$CMD.md" ] || { echo "no prompt file $ROOT/$CMD.md" >&2; exit 1; }
mkdir -p "$ROOT/$WORKER/.claude/commands"
cp "$ROOT/$CMD.md" "$ROOT/$WORKER/.claude/commands/$CMD.md"
export VIRTUAL_ENV="$ROOT/$VENV"
export PATH="$ROOT/$VENV/bin:$PATH"
export PYTHON="$ROOT/$VENV/bin/python3"
unset PYTHONHOME
cd "$ROOT/$WORKER" || exit 1
claude --output-format json -p "/$CMD $TARGET" \
  --allowedTools "Bash(python:*)" "Bash(pytest:*)" "Bash(python3:*)" \
     "Bash(*/bin/python:*)" "Bash(*/bin/pytest:*)" "Bash(ls:*)" "Bash(grep:*)" \
     "Edit(*.py)" "Edit(*.md)" "Write(*.py)" "Write(*.md)" \
     "Update(*.py)" "Update(*.md)" "TodoWrite" "Todo" "WebFetch" \
  --add-dir "$ROOT/$VENV" --add-dir "$EXTRA" \
  --permission-mode bypassPermissions --model opus \
  < /dev/null > claude_result.json 2> claude_err.txt
echo "exit=$? -> $ROOT/$WORKER/claude_result.json"
