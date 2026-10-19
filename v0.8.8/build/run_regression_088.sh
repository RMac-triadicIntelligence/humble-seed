#!/bin/bash
# v0.8.8 regression (not scored). Run after the scored harness has finished.
S=/tmp/claude-0/-home-claude/e5241810-d4d8-50e2-8494-4b1204f90c6a/scratchpad
H=$S/hs088
cd $H
python3 -I regression_chatgpt_round6_on_v0_8_8.py > REGRESSION_chatgpt_round6_probes_on_v0_8_8.txt 2>&1; echo "r6 exit $?"
python3 -I regression_chatgpt_round5_on_v0_8_8.py > REGRESSION_chatgpt_round5_probes_on_v0_8_8.txt 2>&1; echo "r5 exit $?"
python3 -I regression_chatgpt_round4_adapted.py humble_seed_v0_8_8_candidate.py > REGRESSION_chatgpt_round4_probes_on_v0_8_8.txt 2>&1; echo "r4 exit $?"
(cd $S/lin088 && for p in probe7_merge.py probe7_m5_r10.py; do echo "===== $p"; python3 -I $p; done) > REGRESSION_lineage_probes_v0_8_8.txt 2>&1; echo "lineage exit $?"
for who in chatgpt grok; do
  (cd $H/regression_round7/$who && timeout 900 python3 -I claims_battery_${who}_on_v0_8_8.py > TABLE_on_v0_8_8.txt 2>&1; echo "round7 $who battery exit $?")
done
timeout 300 python3 -I regression_round7/author_repro_round7_on_v0_8_8.py > regression_round7/AUTHOR_REPRO_round7_on_v0_8_8.txt 2>&1; echo "round7 author repro exit $?"
for iv in 0.005 0.000001; do
  timeout 300 python3 -I regression_round7/author_repro_round7_natural_on_v0_8_8.py $iv 15 > regression_round7/AUTHOR_REPRO_round7_natural_${iv}_on_v0_8_8.txt 2>&1; echo "natural $iv exit $?"
done
(cd $H/regression_round8/chatgpt_claims && timeout 900 python3 -I claims_battery_chatgpt_on_v0_8_8.py > TABLE_on_v0_8_8.txt 2>&1; echo "round8 chatgpt battery exit $?")
(cd $H/regression_round8/grok_claims && timeout 900 python3 -I claims_battery_grok_on_v0_8_8.py > TABLE_on_v0_8_8.txt 2>&1; echo "round8 grok battery exit $?")
timeout 300 python3 -I regression_round8/author_repro_round8_on_v0_8_8.py > regression_round8/AUTHOR_REPRO_round8_on_v0_8_8.json 2>&1; echo "round8 author repro exit $?"
find $H $S/lin088 -name __pycache__ -type d -prune -exec rm -rf {} +
