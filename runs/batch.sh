#!/bin/bash
# 批量重复跑。用法: batch.sh <起始轮> <结束轮> <并发数>
R=/Users/auderyliu/Documents/NTU/project/agentic-pbt-main
FROM=${1:-2}; TO=${2:-5}; MAXJ=${3:-8}
cd "$R"
jobs_running() { jobs -rp | wc -l | tr -d ' '; }
for rep in $(seq "$FROM" "$TO"); do
  while IFS=$'\t' read -r name mod venv ckt cve; do
    [ -z "$name" ] && continue
    w="runs/${name}_r${rep}"
    [ -s "$w/claude_result.json" ] && continue        # 已跑过就跳过
    while [ "$(jobs_running)" -ge "$MAXJ" ]; do sleep 5; done
    mkdir -p "$w/.claude/commands" && cp hypo.md "$w/.claude/commands/hypo.md"
    bash runs/go.sh "$w" "$mod" "envs/$venv" "$R/dataset/checkouts/$ckt" >/dev/null 2>&1 &
  done < runs/samples.tsv
done
wait
echo "全部完成"
