#!/usr/bin/env bash
# Paired piloted games: the same deck, pods and seeds, Jev vs a Claude executor.
#   bash research/run_executor_games.sh <deck.txt> <out-dir> "<challenger flags>"
# In a cloud session, don't detach this with nohup: a detached process doesn't keep the container alive, and
# the first such run died with the container 3 minutes in. Run it as a tracked background task (2-hour cap),
# so split long runs into chunks (e.g. --games 4 with --seed 1, then --seed 2) and set EDH_FORGE_SLOTS=4.
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
