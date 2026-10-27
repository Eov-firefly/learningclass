"""Build the main research draft and the separate historical supplement."""
from pathlib import Path
import re
import subprocess

root=Path(__file__).resolve().parent
for source,target in [('manuscript.md','main'),('historical_supplement.md','historical_supplement')]:
    title,body=(root/source).read_text().split('\n',1)
    subprocess.run(['pandoc','--from=markdown+tex_math_dollars','--to=latex','--standalone',
        '--shift-heading-level-by=-1','--metadata','title='+title.lstrip('# '),
        '--include-in-header=header.tex','--variable=documentclass:article',
        '--variable=fontsize:12pt','--variable=papersize:a4',f'--output={target}.tex'],
        input=body,text=True,cwd=root,check=True)
    tex=(root/f'{target}.tex').read_text()
    tex=re.sub(r'\\texttt\{([0-9a-f]{40,64})\}',lambda m:r'\texttt{\seqsplit{'+m[1]+'}}',tex)
    (root/f'{target}.tex').write_text(tex)
    for i in range(2):
        with (root/f'{target}-compile-pass{i+1}.log').open('w') as log:
            subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error',f'{target}.tex'],
                cwd=root,stdout=log,stderr=subprocess.STDOUT,check=True)
