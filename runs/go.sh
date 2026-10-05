#!/bin/bash
# 复刻 run.py 的调用方式
WORKER="$1"; TARGET="$2"; VENV="$3"; EXTRA="$4"
ROOT=/Users/auderyliu/Documents/NTU/project/agentic-pbt-main
export VIRTUAL_ENV="$ROOT/$VENV"
export PATH="$ROOT/$VENV/bin:$PATH"
export PYTHON="$ROOT/$VENV/bin/python3"
unset PYTHONHOME
cd "$ROOT/$WORKER" || exit 1
claude --output-format json -p "/hypo $TARGET" \
  --allowedTools "Bash(python:*)" "Bash(pytest:*)" \
     "Edit(*.py)" "Edit(*.md)" "Write(*.py)" "Write(*.md)" \
     "Update(*.py)" "Update(*.md)" "Todo" "WebFetch" \
  --add-dir "$ROOT/$VENV" --add-dir "$EXTRA" \
  --permission-mode acceptEdits --model opus \
  > claude_result.json 2> claude_err.txt
echo "exit=$? -> $ROOT/$WORKER/claude_result.json"
