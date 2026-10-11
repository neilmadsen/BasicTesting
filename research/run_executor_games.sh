#!/usr/bin/env bash
# Paired piloted games: the same deck, pods and seeds, Jev vs a Claude executor. Runs detached:
#   nohup bash research/run_executor_games.sh <deck.txt> <out-dir> "<challenger flags>" > <log> 2>&1 &
# e.g. "--executor haiku --game-log". Both arms use the current pilot code and strategist every turn.
set -u
DECK=$1; OUT=$2; FLAGS=${3:-"--executor haiku"}
mkdir -p "$OUT"
COMMON="--bracket 3 --games 8 --pilot jev --strategist claude-cli --strategist-every 1 --log-state --clock 2700 --workers 2"
./edh sim "$DECK" $COMMON --out "$OUT/jev" > "$OUT/jev.log" 2>&1 &
sleep 120   # the first run rebuilds the pilot jar if the Java changed; don't race it
./edh sim "$DECK" $COMMON $FLAGS --out "$OUT/challenger" > "$OUT/challenger.log" 2>&1 &
wait
echo "PAIRED GAMES DONE"
