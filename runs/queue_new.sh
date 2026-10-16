#!/bin/bash
R=/Users/auderyliu/Documents/NTU/project/agentic-pbt-main
cd "$R"
nclaude() { ps aux | grep -c '[c]laude --output-format'; }
while IFS=$'\t' read -r name mod venv ckt cve; do
  [ -z "$name" ] && continue
  w="runs/$name"
  [ -s "$w/claude_result.json" ] && continue
  while [ "$(nclaude)" -ge 9 ]; do sleep 20; done
  mkdir -p "$w/.claude/commands" && cp hypo.md "$w/.claude/commands/hypo.md"
  nohup bash runs/go.sh "$w" "$mod" "envs/$venv" "$R/dataset/checkouts/$ckt" >/dev/null 2>&1 &
  echo "启动 $name"
  sleep 10
done < runs/samples_new.tsv
wait
echo "新样本全部完成"
