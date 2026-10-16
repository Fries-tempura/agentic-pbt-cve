#!/bin/bash
R=/Users/auderyliu/Documents/NTU/project/agentic-pbt-main
cd "$R"
nclaude() { ps aux | grep -c '[c]laude --output-format'; }
LIST=$(cat "$1")                      # 一次性读进变量,不再让循环占用 stdin
FROM=${2:-1}; TO=${3:-1}; MAXJ=${4:-8}
for rep in $(seq "$FROM" "$TO"); do
  while IFS=$'\t' read -r name mod venv ckt cve; do
    [ -z "$name" ] && continue
    [ "$rep" -eq 1 ] && w="runs/$name" || w="runs/${name}_r${rep}"
    [ -s "$w/claude_result.json" ] && continue
    while [ "$(nclaude)" -ge "$MAXJ" ]; do sleep 10; done
    mkdir -p "$w/.claude/commands" && cp hypo.md "$w/.claude/commands/hypo.md"
    nohup bash runs/go.sh "$w" "$mod" "envs/$venv" "$R/dataset/checkouts/$ckt" >/dev/null 2>&1 &
    sleep 3
  done <<< "$LIST"
done
while [ "$(nclaude)" -gt 0 ]; do sleep 15; done
echo "完成"
