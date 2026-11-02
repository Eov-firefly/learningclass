"""CPU checks of audit boundaries and the conditional greedy preservation claim."""
import hashlib
import itertools
import random
import unittest
from audit_raw import distance_trace
from historical_contracts_frozen import score


def greedy(paths, budget, filtered):
    output=[]
    for _ in range(budget+1):
        compatible=[p for p in paths if p[:len(output)]==output]
        if any(len(p)==len(output) for p in compatible):return output, True
        if len(output)==budget:return output, False
        allowed={p[len(output)] for p in compatible}
        if filtered:
            allowed={v for v in allowed if any(p[len(output)]==v and len(p)<=budget for p in compatible)}
        if not allowed:return output, False
        # A fixed history-dependent score and global tie-break, shared by both policies.
        def rank(v):return (int(hashlib.sha256(str((output,v)).encode()).hexdigest(),16),-v)
        output.append(max(allowed,key=rank))


class AuditTests(unittest.TestCase):
    def test_dead_entry_excludes_initial_infeasibility(self):
        d=distance_trace([[1,2],[1,3,4,5]],[1,3,4],3,3)
        self.assertEqual((d['first_dead_step'],d['calls_after_dead'],d['entered_dead_after_feasible']),(2,1,1))
        d=distance_trace([[1,2]],[1],1,1)
        self.assertEqual((d['first_dead_step'],d['entered_dead_after_feasible']),(0,0))

    def test_illegal_prefix_is_not_a_legal_dead_end(self):
        d=distance_trace([[1,2]],[9],2,1)
        self.assertEqual(d['first_language_escape_step'],1)
        self.assertIsNone(d['first_dead_step'])

    def test_frozen_marker_contract_does_not_drift(self):
        text='\\[\n   #### 1000\n\\]'
        self.assertFalse(score(text,'numeric','1000',eos=True,contract='closure_tolerant')['valid'])
        self.assertTrue(score('#### 1000\n','numeric','1000',contract='strict')['correct'])
        self.assertFalse(score('#### .5\n','numeric','.5',contract='strict')['valid'])

    def test_greedy_preservation_over_finite_languages(self):
        pool=[list(p) for n in range(1,5) for p in itertools.product(range(3),repeat=n)]
        rng=random.Random(20261102);successful=0;feasible=0
        for _ in range(500):
            paths=rng.sample(pool,rng.randint(1,8));budget=rng.randint(0,5)
            g,gs=greedy(paths,budget,False);f,fs=greedy(paths,budget,True)
            if min(map(len,paths))<=budget:feasible+=1;self.assertTrue(fs)
            if gs:successful+=1;self.assertTrue(fs);self.assertEqual(f,g)
        self.assertGreater(successful,100);self.assertGreater(feasible,100)


if __name__=='__main__':unittest.main()
