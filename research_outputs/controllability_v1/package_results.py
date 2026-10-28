"""Archive a finished control analysis, with hashes; no weights are included."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

def main():
    p=argparse.ArgumentParser();p.add_argument('--analysis',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    checks=a.analysis/'checks.json'
    if not checks.exists():raise ValueError('Missing checks.json; retain failed-run logs separately')
    if a.out.exists():raise FileExistsError('Choose a new output archive name')
    files=[f for f in a.analysis.rglob('*') if f.is_file() and f.resolve()!=a.out.resolve()]
    manifest=dict(status=json.loads(checks.read_text())['status'],
       scope='control reanalysis only; original raw archive must also be retained',
       files={str(f.relative_to(a.analysis)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files)})
    with zipfile.ZipFile(a.out,'x',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(files):z.write(f,Path('control_analysis')/f.relative_to(a.analysis))
        z.writestr('RESULT_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(str(a.out))

if __name__=='__main__':main()
