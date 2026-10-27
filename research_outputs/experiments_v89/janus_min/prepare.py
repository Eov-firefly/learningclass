"""One-time prefetch and provenance, before launching four model replicas."""
import argparse
import hashlib
import json
from pathlib import Path
from .spec import MODEL_SPECS

def main():
    p=argparse.ArgumentParser();p.add_argument('--download',action='store_true')
    p.add_argument('--qwen-path',type=Path);p.add_argument('--mistral-path',type=Path)
    p.add_argument('--hash-weights',action='store_true');p.add_argument('--output',type=Path,default=Path('model_manifest.json'))
    a=p.parse_args();report={}
    for name,spec in MODEL_SPECS.items():
        local=getattr(a,name+'_path')
        if local is None:
            from huggingface_hub import snapshot_download
            local=Path(snapshot_download(repo_id=spec['id'],revision=spec['revision'],local_files_only=not a.download,
               allow_patterns=['*.json','*.model','*.tiktoken','*.safetensors','tokenizer*','vocab*','merges*'],max_workers=4))
        files={}
        for f in sorted(local.rglob('*')):
            if not f.is_file() or '.cache' in f.parts:continue
            if f.suffix not in {'.json','.model','.tiktoken','.safetensors','.txt'}:continue
            item={'bytes':f.stat().st_size}
            if a.hash_weights or f.suffix!='.safetensors':
                h=hashlib.sha256()
                with f.open('rb') as stream:
                    for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
                item['sha256']=h.hexdigest()
            files[str(f.relative_to(local))]=item
        if not files or not any(n.endswith('.safetensors') for n in files):raise RuntimeError('No safetensors weights at '+str(local))
        report[name]={'spec':spec,'local_path':str(local.resolve()),'hash_weights':a.hash_weights,'files':files}
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({name:r['local_path'] for name,r in report.items()},indent=2))

if __name__=='__main__':main()
