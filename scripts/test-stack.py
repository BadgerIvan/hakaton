"""Build/run an isolated Docker test project; preserve logs/reports and clean up."""
import argparse
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--keep',action='store_true',help='Keep the test containers for debugging')
args=parser.parse_args()
reports=root/'reports';reports.mkdir(exist_ok=True)
compose=['docker','compose','-f','compose.test.yaml']
result=1
try:
    result=subprocess.run([*compose,'up','--build','--abort-on-container-exit','--exit-code-from','tests'],cwd=root).returncode
finally:
    with (reports/'test-stack.log').open('w') as log:
        subprocess.run([*compose,'logs','--no-color'],cwd=root,stdout=log,stderr=subprocess.STDOUT)
    if not args.keep:subprocess.run([*compose,'down','--volumes','--remove-orphans'],cwd=root)
raise SystemExit(result)
