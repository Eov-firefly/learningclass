"""Build the journal-neutral manuscripts and synchronized Markdown views."""
from pathlib import Path
import json,re,shutil,subprocess

ROOT=Path(__file__).resolve().parents[2]
BUILD=Path(__file__).resolve().parent/'build'


def run(cmd,log,cwd=BUILD):
    result=subprocess.run(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    log.write_text('\n'.join(line.rstrip() for line in result.stdout.splitlines()).rstrip()+'\n')
    if result.returncode:raise RuntimeError(f'{cmd[0]} failed; see {log}')


def markdown(stem):
    source=(ROOT/(stem+'.tex')).read_text()
    aux=(BUILD/(stem+'.aux')).read_text()
    labels=dict(re.findall(r'\\newlabel\{([^}]+)\}\{\{([^}]+)\}',aux))
    source=re.sub(r'\\caption\{([^}]+)\}\\label\{([^}]+)\}',
        lambda m:r'\caption{'+('Figure ' if m[2].startswith('fig:') else 'Table ')+labels.get(m[2],'')+'. '+m[1]+'}',source)
    source=re.sub(r'\\ref\{([^}]+)\}',lambda m:labels[m[1]],source)
    source=re.sub(r'\\paragraph\{([^}]+)\}',lambda m:r'\noindent\textbf{'+m[1]+'}',source)
    replacements={}
    def text_cell(value):
        return value.strip().replace(r'\%','%').replace(r'\&','&')
    def table(block):
        content=block[0]
        caption=re.search(r'\\caption\{([^}]+)\}',content)[1]
        data=[]
        for line in content.splitlines():
            if '&' in line and line.rstrip().endswith(r'\\'):
                data.append([text_cell(c) for c in line.rstrip()[:-2].split('&')])
        head=data.pop(0)
        if data and data[0]==head:data.pop(0)
        value='**'+text_cell(caption)+'**\n\n'
        value+='| '+' | '.join(head)+' |\n| '+' | '.join(['---']*len(head))+' |\n'
        value+='\n'.join('| '+' | '.join(row)+' |' for row in data)
        key='JANUSBLOCK'+str(len(replacements));replacements[key]=value
        return '\n\n'+key+'\n\n'
    source=re.sub(r'\\begin\{longtable\}.*?\\end\{longtable\}',table,source,flags=re.S)
    def figure(block):
        content=block[0];caption=re.search(r'\\caption\{([^}]+)\}',content)[1]
        image=re.search(r'\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}',content)[1].replace('.pdf','.png')
        key='JANUSBLOCK'+str(len(replacements));replacements[key]='![Audited fixed8 outcomes]('+image+')\n\n**'+caption+'**'
        return '\n\n'+key+'\n\n'
    source=re.sub(r'\\begin\{figure\}.*?\\end\{figure\}',figure,source,flags=re.S)
    counts={'proposition':0,'corollary':0}
    def theorem(m):
        name=m[1];counts[name]+=1
        return r'\textbf{'+name.title()+' '+str(counts[name])+(' ('+m[2]+')' if m[2] else '')+'.}'
    source=re.sub(r'\\begin\{(proposition|corollary)\}(?:\[([^]]+)\])?',theorem,source)
    source=re.sub(r'\\end\{(?:proposition|corollary)\}','',source)
    source=source.replace(r'\begin{proof}',r'\textit{Proof.}').replace(r'\end{proof}',r'\(\square\)')
    source=re.sub(r'\\label\{[^}]+\}','',source)
    temporary=BUILD/(stem+'-markdown.tex');temporary.write_text(source)
    target=BUILD/(stem+'-body.md')
    run(['pandoc',str(temporary),'-f','latex','-t','gfm','--wrap=none','--shift-heading-level-by=1',
         '--citeproc','--bibliography',str(ROOT/'references.bib'),'-M','reference-section-title=References',
         '-o',str(target)],BUILD/(stem+'-pandoc.log'),cwd=ROOT)
    body=target.read_text().replace('figures/fixed8_outcomes.pdf','figures/fixed8_outcomes.png')
    for key,value in replacements.items():body=body.replace(key,value)
    metadata=json.loads((Path(__file__).parent/'submission_metadata.json').read_text())
    title=metadata['title'] if stem=='main' else 'Supplementary material: Budget-viable commitment'
    front='**Authors:** '+', '.join(metadata['authors'])+'\n\n'+metadata['affiliation']+'\n\n'
    front+='**Correspondence:** '+metadata['corresponding_author']['email']+'\n\n'
    if stem=='main':
        abstract=re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',source,re.S)[1].replace(r'\singlespacing','').strip()
        front+='## Abstract\n\n'+abstract+'\n\n'
    path=ROOT/('manuscript.md' if stem=='main' else 'supplementary.md')
    path.write_text('\n'.join(line.rstrip() for line in ('# '+title+'\n\n'+front+body).splitlines()).rstrip()+'\n')


def main():
    BUILD.mkdir(parents=True,exist_ok=True)
    (BUILD/'figures').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'figures/fixed8_outcomes.pdf',BUILD/'figures/fixed8_outcomes.pdf')
    shutil.copyfile(ROOT/'references.bib',BUILD/'references.bib')
    report={}
    for stem in ['main','supplementary']:
        for previous in BUILD.glob(stem+'-pass*.stdout'):previous.unlink()
        shutil.copyfile(ROOT/(stem+'.tex'),BUILD/(stem+'.tex'))
        run(['pdflatex','-interaction=nonstopmode','-halt-on-error',stem+'.tex'],BUILD/(stem+'-pass1.stdout'))
        run(['bibtex',stem],BUILD/(stem+'-bibtex.stdout'))
        for i in [2,3]:
            run(['pdflatex','-interaction=nonstopmode','-halt-on-error',stem+'.tex'],BUILD/(stem+f'-pass{i}.stdout'))
        log=(BUILD/(stem+'.log')).read_text()
        if 'Label(s) may have changed' in log:
            run(['pdflatex','-interaction=nonstopmode','-halt-on-error',stem+'.tex'],BUILD/(stem+'-pass4.stdout'))
            log=(BUILD/(stem+'.log')).read_text()
        if re.search(r'undefined|multiply defined|^!',log,re.I|re.M):
            raise RuntimeError('Unresolved typesetting/citation/reference issue in '+stem+'.log')
        (BUILD/(stem+'.log')).write_text('\n'.join(line.rstrip() for line in log.splitlines()).rstrip()+'\n')
        shutil.copyfile(BUILD/(stem+'.pdf'),ROOT/(stem+'.pdf'))
        markdown(stem)
        info=subprocess.check_output(['pdfinfo',str(ROOT/(stem+'.pdf'))],text=True)
        report[stem]=dict(pages=int(re.search(r'^Pages:\s+(\d+)',info,re.M)[1]),
                         overfull=log.count('Overfull'),underfull=log.count('Underfull'),
                         undefined_references=False)
    (BUILD/'build_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
