#!/bin/bash
# 串行跑,一次一个。撞上限就等 10 分钟重试,最多重试 6 次。
#   bash runs/serial.sh               -> hypo 基线,第 2..5 次重复
#   bash runs/serial.sh hypo_v2 1 5   -> hypo_v2 消融,第 1..5 次,写进 runs/<name>_v2_rN
R=/Users/auderyliu/Documents/NTU/project/agentic-pbt-main
cd "$R"
CMD="${1:-hypo}"; FROM="${2:-2}"; TO="${3:-5}"
# 两版的产物必须分开存放,否则 v2 会覆盖已经跑完的 85 次基线。
SUF=""; [ "$CMD" != "hypo" ] && SUF="_v2"
LIST=$(cat runs/samples.tsv)
for rep in $(seq "$FROM" "$TO"); do
  while IFS=$'\t' read -r name mod venv ckt cve; do
    [ -z "$name" ] && continue
    w="runs/${name}${SUF}_r${rep}"
    [ -s "$w/claude_result.json" ] && continue
    for try in 1 2 3 4 5 6; do
      mkdir -p "$w"
      bash runs/go.sh "$w" "$mod" "envs/$venv" "$R/dataset/checkouts/$ckt" "$CMD" >/dev/null 2>&1
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
