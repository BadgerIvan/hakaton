"""Run auth/backend tests using TEST_DATABASE_URL (PostgreSQL) and frontend checks."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
if not os.getenv('TEST_DATABASE_URL'):
    raise SystemExit('Set TEST_DATABASE_URL to PostgreSQL first; tests create and remove their own schemas.')
for service in ('auth_service', 'backend_service'):
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                   cwd=root / 'services' / service, check=True)
npm = shutil.which('npm')
if not npm:
    raise SystemExit('npm was not found')
for arguments in (['test'], ['run', 'build']):
    subprocess.run([npm, *arguments], cwd=root / 'frontend', check=True)
