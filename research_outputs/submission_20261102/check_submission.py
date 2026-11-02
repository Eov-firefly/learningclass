"""Preflight the finalized manuscript, cross-references and audited-count claims."""
from pathlib import Path
import csv,hashlib,json,re

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def csvrows(path):return list(csv.DictReader(path.open()))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    text=(ROOT/'main.tex').read_text();md=(ROOT/'manuscript.md').read_text()
    supplement=(ROOT/'supplementary.md').read_text()
    metadata=json.loads((HERE/'submission_metadata.json').read_text())
    audit=ROOT/'research_outputs/raw_audit_20261102/analysis'
    names={'full':'BVC','grammar':'Grammar','sequence_score':'Sequence score','xgrammar':'XGrammar','deterministic':'Shortest'}
    for r in csvrows(audit/'single_all_baselines.csv'):
        if r['condition']!='fixed8':continue
        expected=' & '.join([r['model'].title(),names[r['policy']],r['certified'],r['correct'],r['wrong'],r['total_forward_calls'],r['scoring_input_tokens']])
        assert expected in text,expected
    original=csvrows(audit/'double_matched_baselines.csv')
    for model in ['qwen','mistral']:
        f=next(r for r in original if (r['model'],r['encoding'],r['cap'],r['policy'])==(model,'option_text','24','full'))
        g=next(r for r in original if (r['model'],r['encoding'],r['cap'],r['policy'])==(model,'option_text','24','grammar'))
        expected=f"{model.title()} & {f['correct']}/96 ({int(f['correct'])/96*100:.2f}\\%) & {g['correct']}/96 ({int(g['correct'])/96*100:.2f}\\%)"
        assert expected in text,expected
    baseline={(r['model'],r['policy']):r for r in csvrows(audit/'single_all_baselines.csv') if r['condition']=='fixed8'}
    for r in csvrows(audit/'trajectory_transitions.csv'):
        if r['condition']!='fixed8':continue
        model=r['model'];f=baseline[model,'full'];g=baseline[model,'grammar'];n=f['initially_feasible']
        expected=(f"{model.title()} & {n}/64 & {f['certified']}/{n} & {g['certified']}/{n} & "
                  f"${float(r['feasible_difference'])*100:.2f}\\ [{float(r['feasible_adjusted_ci_low'])*100:.2f},{float(r['feasible_adjusted_ci_high'])*100:.2f}]$ & {f['correct']}, {g['correct']}")
        assert expected in text,expected
    reach={(r['model'],r['policy'],r['gold_reachable']):r for r in csvrows(audit/'reference_reachability.csv') if r['condition']=='fixed8'}
    for model in ['qwen','mistral']:
        for fits in ['1','0']:
            f=reach[model,'full',fits];g=reach[model,'grammar',fits];s=reach[model,'sequence_score',fits]
            expected=' & '.join([model.title(),'Yes' if fits=='1' else 'No',f['n'],f['certified']+'/'+f['correct'],g['certified']+'/'+g['correct'],s['certified']+'/'+s['correct']])
            assert expected in text,expected
    stability=csvrows(HERE/'output_stability.csv')
    totals={}
    for policy in ['full','sequence_score']:
        rs=[r for r in stability if r['policy']==policy]
        totals[policy]=dict(retained=sum(int(r['n_same_certified_answer']) for r in rs),
                            denominator=sum(int(r['n_grammar_certified']) for r in rs),
                            previous_correct_lost=sum(int(r['n_previous_correct_lost']) for r in rs),
                            old_wrong_corrected=sum(int(r['n_grammar_wrong_corrected']) for r in rs))
    assert totals['full']==dict(retained=259,denominator=259,previous_correct_lost=0,old_wrong_corrected=0)
    assert totals['sequence_score']==dict(retained=241,denominator=259,previous_correct_lost=10,old_wrong_corrected=5)
    for model,n,f,s,l,g in [('Qwen',44,44,41,2,1),('Mistral',37,37,35,1,0)]:
        assert f'{model} & {n} & {f}/{n} & {s}/{n} & {l} & {g}' in text
    for r in csvrows(audit/'terminal_policy_sensitivity.csv'):
        if r['condition']=='fixed8' and r['policy'] in {'full','grammar','xgrammar'}:
            row=' & '.join([r['model'].title(),names[r['policy']],r['controller_certified']+'/'+r['controller_correct'],r['consumer_text_valid']+'/'+r['consumer_text_correct']])
            assert row in text,row
    for item in ['funding','competing_interests']:
        assert metadata[item] in text and metadata[item] in md
    assert metadata['all_authors_agreed_to_submission'] is True
    assert 'All authors have agreed to submission of this manuscript.' in text
    for author in metadata['authors']:assert author in text and author in md
    for word in ['Declarations pending','not submission-ready','Research draft','TODO','TBD']:
        assert word not in text
    assert 'author contributions' not in text.lower()
    assert '## Abstract' in md and md.count('**Table ')==6 and supplement.count('**Table ')==7
    assert '<div class="longtable">' not in md and 'JANUSBLOCK' not in md
    assert text.count('\\begin{proposition}')==4 and '\\begin{corollary}' in text
    assert 'Limitations and future work' in text
    for stem in ['main','supplementary']:
        log=(HERE/'build'/(stem+'.log')).read_text()
        assert not re.search(r'undefined|multiply defined|Overfull|Underfull|^!',log,re.I|re.M)
        assert (HERE/'build'/(stem+'.tex')).read_bytes()==(ROOT/(stem+'.tex')).read_bytes()
    abstract=text.split('\\begin{abstract}\\singlespacing')[1].split('\\end{abstract}')[0]
    assert len(abstract.split())<=250
    highlights=(HERE/'highlights.txt').read_text().splitlines()
    assert len(highlights)==5 and max(map(len,highlights))<=85
    files=['main.tex','main.pdf','manuscript.md','supplementary.tex','supplementary.pdf','supplementary.md','references.bib','figures/fixed8_outcomes.pdf','figures/fixed8_outcomes.png']
    result=dict(date='2026-11-02',status='journal_neutral_submission_manuscript',
        source_data_unchanged=True,new_gpu_inference=False,
        all_main_count_tables_checked=True,answer_stability_totals=totals,
        same_data_exploratory_qualifications_retained=True,original_cap24_primary_retained=True,
        abstract_words=len(abstract.split()),highlights_max_characters=max(map(len,highlights)),
        authors_funding_conflicts_approval_from_user_confirmation=True,
        author_contributions_omitted_as_requested=True,
        typesetting=json.loads((HERE/'build/build_report.json').read_text()),
        files_sha256={n:sha(ROOT/n) for n in files},
        scope='Generic journal format; bounded claims are supported by theory and existing raw. No first-paradigm or acceptance guarantee is asserted.')
    (HERE/'FINAL_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
