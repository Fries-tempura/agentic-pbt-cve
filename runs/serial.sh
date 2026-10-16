#!/bin/bash
# 串行跑,一次一个。撞上限就等 10 分钟重试,最多重试 6 次。
R=/Users/auderyliu/Documents/NTU/project/agentic-pbt-main
cd "$R"
LIST=$(cat runs/samples.tsv)
for rep in 2 3 4 5; do
  while IFS=$'\t' read -r name mod venv ckt cve; do
    [ -z "$name" ] && continue
    w="runs/${name}_r${rep}"
    [ -s "$w/claude_result.json" ] && continue
    for try in 1 2 3 4 5 6; do
      mkdir -p "$w/.claude/commands" && cp hypo.md "$w/.claude/commands/hypo.md"
      bash runs/go.sh "$w" "$mod" "envs/$venv" "$R/dataset/checkouts/$ckt" >/dev/null 2>&1
      if grep -q "session limit" "$w/claude_result.json" 2>/dev/null; then
        echo "[$(date +%H:%M)] $w 撞上限,等 10 分钟 (第 $try 次)"
        rm -f "$w/claude_result.json"; sleep 600
      else
        echo "[$(date +%H:%M)] ✓ $w"; break
      fi
    done
  done <<< "$LIST"
done
echo "全部完成"
