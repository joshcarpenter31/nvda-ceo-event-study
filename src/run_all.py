"""Run the pipeline on the frozen dataset in data/.

    python src/run_all.py           # reproduce the published results
    python src/run_all.py --fetch   # re-download prices first (results may change)
"""
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

steps = ["event_study", "robustness", "synthetic_control", "charts", "hero_chart"]
if "--fetch" in sys.argv:
    steps.insert(0, "fetch_data")

for step in steps:
    print(f"\n===== {step} =====")
    runpy.run_path(str(HERE / f"{step}.py"), run_name="__main__")
