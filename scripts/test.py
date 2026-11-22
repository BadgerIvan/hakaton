"""Portable test entry point. Each app runs separately to isolate its `app` package."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--unit',action='store_true',help='No DB, Qdrant or models required')
    mode.add_argument('--integration',action='store_true',help='Real PostgreSQL/Qdrant suites only')
    parser.add_argument('--coverage',action='store_true')
    parser.add_argument('--no-frontend',action='store_true')
    args=parser.parse_args()
    if not args.unit:
        missing=[name for name in ('TEST_DATABASE_URL','TEST_QDRANT_URL') if not os.getenv(name)]
        if missing: parser.error('Set dedicated test endpoints: '+', '.join(missing)+'; use --unit for offline tests')
    report=ROOT/'reports';report.mkdir(exist_ok=True)
    env={**os.environ,'PYTHONPATH':str(ROOT/'services/common')+os.pathsep+os.environ.get('PYTHONPATH','')}
    targets=[('common',ROOT/'services/common'),('auth',ROOT/'services/auth_service'),
             ('backend',ROOT/'services/backend_service'),('rag',ROOT/'services/rag_service'),
             ('parser',ROOT/'parse_service')]
    failures=[]
    for name,cwd in targets:
        if args.integration and name in ('common','parser'):continue
        command=[sys.executable,'-m','pytest','tests','-q','--junitxml='+str(report/(name+'.xml'))]
        if args.unit: command+=['-m','not integration']
        elif args.integration:command+=['-m','integration']
        if args.coverage:
            source='partner_observability' if name=='common' else 'app'
            command+=['--cov='+source,'--cov-branch','--cov-report=term-missing',
                      '--cov-report=xml:'+str(report/(name+'-coverage.xml'))]
        print('Running '+name,flush=True)
        if subprocess.run(command,cwd=cwd,env=env).returncode:failures.append(name)
    if not args.integration and not args.no_frontend:
        npm=shutil.which('npm')
        if not npm:raise SystemExit('npm is required; install Node 22+ or use --no-frontend')
        commands = (['run','test:types'], ['run','test:unit'], ['run','test:components','--','--coverage'], ['run','build']) if args.coverage else (['test'], ['run','build'])
        for arguments in commands:
            if subprocess.run([npm,*arguments],cwd=ROOT/'frontend',env=env).returncode:failures.append('frontend '+' '.join(arguments))
    if failures:raise SystemExit('Failed: '+', '.join(failures))
    print('All requested checks passed. XML reports: reports/')

if __name__=='__main__':main()
