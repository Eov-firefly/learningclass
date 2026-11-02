"""Publication figure from audited counts; no new inference or resampling."""
from pathlib import Path
import csv
import os
import tempfile
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'janus-matplotlib-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
rows=list(csv.DictReader((ROOT/'research_outputs/raw_audit_20261102/analysis/single_all_baselines.csv').open()))
lookup={(r['model'],r['policy']):r for r in rows if r['condition']=='fixed8'}
policies=['full','grammar','sequence_score','xgrammar','deterministic']
labels=['BVC','Grammar','Sequence score','XGrammar','Shortest']
plt.rcParams.update({'font.size':10.5,'pdf.fonttype':42,'ps.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,2,figsize=(7.2,3.5),sharex=True,sharey=True)
colors=['#23689B','#E49A3A','#E3E6E8']
for ax,model in zip(axes,['qwen','mistral']):
    correct=np.array([int(lookup[model,p]['correct']) for p in policies])
    wrong=np.array([int(lookup[model,p]['wrong']) for p in policies])
    n=np.array([int(lookup[model,p]['n']) for p in policies]);assert np.all(n==64)
    abstain=n-correct-wrong; assert np.all(abstain>=0)
    pos=np.arange(len(policies));left=np.zeros(len(policies))
    for values,color,label in zip([correct,wrong,abstain],colors,['Correct certified','Incorrect certified','Abstained']):
        ax.barh(pos,values,left=left,color=color,height=.64,label=label,edgecolor='white',linewidth=.6)
        left+=values
    for y,c,w in zip(pos,correct,wrong):
        ax.text(c/2,y,str(c),ha='center',va='center',color='white',fontsize=10,fontweight='bold')
        ax.text(c+w+.7,y,f'{c+w}/64',ha='left',va='center',fontsize=9.5,color='#333333')
    ax.set_yticks(pos,labels);ax.set_title('Qwen' if model=='qwen' else 'Mistral')
    ax.set_xlim(0,72);ax.set_xticks([0,16,32,48,64]);ax.set_xlabel('Requests (64 per policy)')
    ax.grid(axis='x',alpha=.16);ax.set_axisbelow(True)
axes[0].invert_yaxis()
fig.legend(*axes[0].get_legend_handles_labels(),loc='lower center',ncol=3,frameon=False,bbox_to_anchor=(.5,-.02))
fig.tight_layout(rect=(0,.07,1,1))
folder=ROOT/'figures';folder.mkdir(exist_ok=True)
fig.savefig(folder/'fixed8_outcomes.pdf',bbox_inches='tight')
fig.savefig(folder/'fixed8_outcomes.png',dpi=300,bbox_inches='tight')
print('Saved audited-count figure:',folder/'fixed8_outcomes.pdf')
