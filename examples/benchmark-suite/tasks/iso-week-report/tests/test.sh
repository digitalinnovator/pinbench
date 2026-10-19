#!/bin/bash
# Hidden tests: Harbor copies /tests in only after the agent finishes.
cd /app
python -m pytest -q -p no:cacheprovider /tests/test_solution.py -rA
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
