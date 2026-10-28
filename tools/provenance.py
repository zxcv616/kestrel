"""Bind test reports to the exact source tree checked before a verification run."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def source_hashes(root=ROOT):
    paths=[]
    for folder in ('fsw','ground','tests','tools','dashboard','.github','docs'):
        paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo'))
    paths.extend(root/p for p in ('CMakeLists.txt','docs/requirements.md','docs/design.md','docs/icd.md'))
    return {str(p.relative_to(root)):digest(p) for p in sorted(paths) if p.is_file()}
def verify(path,reports,root=ROOT):
    record=json.loads(path.read_text())
    if record.get('sourceHashes')!=source_hashes(root):raise ValueError('Verification source tree differs from tested source')
    if not reports:raise ValueError('No reports supplied for provenance verification')
    for report in reports:
        if record.get('reports',{}).get(report.name)!=digest(report):raise ValueError('Report is missing or changed: '+str(report))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['start','finish']);p.add_argument('path',type=Path);p.add_argument('--junit',type=Path,action='append',default=[]);a=p.parse_args()
    if a.action=='start':
        commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True)
        data={'sourceHashes':source_hashes(),'commit':commit.stdout.strip() if commit.returncode==0 else None}
    else:
        data=json.loads(a.path.read_text())
        if data['sourceHashes']!=source_hashes():raise SystemExit('Source changed during verification; run checks again')
        if not a.junit:raise SystemExit('No reports to bind')
        data['reports']={p.name:digest(p) for p in a.junit}
    a.path.parent.mkdir(parents=True,exist_ok=True);a.path.write_text(json.dumps(data,indent=2)+'\n')
if __name__=='__main__':main()
