"""Package raw outputs without including model weights or the HF cache."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('JANUS_results.zip'))
    p.add_argument('--model-manifest',type=Path,default=Path('model_manifest.json'))
    a=p.parse_args()
    if not a.run.is_dir():raise FileNotFoundError(a.run)
    if (a.run/'launch.lock').exists():raise RuntimeError('Stop the run before collecting a consistent archive')
    if a.output.exists():raise FileExistsError('Choose a new archive name: '+str(a.output))
    files=[f for f in a.run.rglob('*') if f.is_file() and f.resolve()!=a.output.resolve()]
    checks=a.run/'analysis/checks.json'
    report=dict(status=json.loads(checks.read_text())['status'] if checks.exists() else 'PARTIAL',
      files={str(f.relative_to(a.run)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files)},
      includes_model_manifest=a.model_manifest.exists(),note='raw records and logs retained including failed requests; no model weights')
    with zipfile.ZipFile(a.output,'x',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(files):z.write(f,Path('run')/f.relative_to(a.run))
        if a.model_manifest.exists():z.write(a.model_manifest,'model_manifest.json')
        z.writestr('RESULT_MANIFEST.json',json.dumps(report,indent=2)+'\n')
    print(str(a.output))

if __name__=='__main__':main()
