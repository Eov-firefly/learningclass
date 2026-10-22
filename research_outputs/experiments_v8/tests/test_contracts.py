import unittest
from janus_v8.contracts import parse,score,wrapper_balanced,EntropyGate,allowed_choices
from janus_v8.stats import paired_binary,paired_bootstrap


class Contracts(unittest.TestCase):
    def test_eos_and_cap_certificates(self):
        self.assertIsNone(parse('#### 42','numeric',eos=False))
        self.assertEqual(parse('#### 42','numeric',eos=True),'42')
        self.assertEqual(parse('#### 42\n','numeric',eos=False),'42')

    def test_number_and_choices(self):
        self.assertTrue(score('#### +42.0\n','numeric','42')['correct'])
        for text in ['#### 1e3\n','#### 1,000\n','#### 42 kg\n']:
            self.assertIsNone(parse(text,'numeric'))
        self.assertIsNone(parse('#### E\n','choice','ABCD'))
        self.assertEqual(allowed_choices('Use an answer using ABCD. '),'ABCD')

    def test_transient_validity(self):
        prefix='\\[\n#### 42\n'
        full=prefix+'\\]'
        self.assertEqual(parse(prefix,'numeric'),'42')
        self.assertIsNone(parse(full,'numeric',eos=True))
        self.assertIsNone(parse(prefix,'numeric',contract='closure_balanced'))
        self.assertEqual(parse(full,'numeric',contract='closure_balanced'),'42')

    def test_premature_wrong_answer(self):
        first='#### 41\n'
        full=first+'Correction\n#### 42\n'
        self.assertFalse(score(first,'numeric','42')['correct'])
        self.assertTrue(score(full,'numeric','42')['correct'])

    def test_wrapper_heuristic(self):
        self.assertFalse(wrapper_balanced('```text\n#### 42\n'))
        self.assertTrue(wrapper_balanced('```text\n#### 42\n```'))
        self.assertFalse(wrapper_balanced('\\begin{a}\\end{b}'))

    def test_entropy_index_and_minimum(self):
        gate=EntropyGate(threshold=.01,window=5,min_steps=21)
        for t in range(1,21):self.assertFalse(gate.update(t,2.0))
        self.assertTrue(gate.update(21,2.0))
        gate=EntropyGate(threshold=.01,window=5,min_steps=1)
        for t in range(1,6):self.assertFalse(gate.update(t,2.0))
        self.assertTrue(gate.update(6,2.0))

    def test_paired_intervals(self):
        u=[False]*600;c=[True]*14+[False]*586
        ci=paired_binary(c,u,alpha=.0125)
        self.assertEqual((ci['wins'],ci['losses']),(14,0))
        self.assertAlmostEqual(ci['lo']*100,.03,places=2)
        self.assertAlmostEqual(ci['hi']*100,4.57,places=2)
        self.assertEqual(paired_bootstrap([0,0,0])['hi'],0)


if __name__=='__main__':unittest.main()
