"""Bounded, checkpointed validation recovery; all clients are fake, no AI fees."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from checkpoints import Checkpoint
from content_quality import (ContentQuality, PLAN_TOOL, SubmissionRepairLimit,
                             pending_submission_error, research_only_checkpoint, text_block)
from pipeline import Config, inherit_resume_budget
from usage_guard import BudgetStop


def call(name, payload=None, identity='t'):
    return [{'type':'tool_use','id':identity,'name':name,'input':payload or {}}]


class FakeClient:
    def __init__(self, responses):
        self.responses=list(responses)
        self.calls=[]
        self.seen_tools=[]

    def send(self, messages, tools, system):
        self.seen_tools.append([t['name'] for t in tools])
        response=self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        self.calls.append({'usage':{'cost_usd':0}})
        return copy.deepcopy(response)


class SubmissionRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.out=Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def make(self, responses, resume=False):
        config=Config(resume=resume, budget_usd=3.85)
        evidence=SimpleNamespace(out=self.out,source='https://www.youtube.com/watch?v=fixture',
                                 records=[],extra_count=0,inspect_calls=0)
        def inspect(payload):
            evidence.inspect_calls+=1
            return []
        evidence.inspect=inspect
        evidence.inspect_interval=inspect
        client=FakeClient(responses)
        quality=ContentQuality(evidence,client,config,lambda m:None,
                               {'name':'inspect_frames','input_schema':{'type':'object'}},'')
        quality.research=SimpleNamespace(used=True,execute=lambda *a:[])
        return quality

    def saved_rejection(self, *, inspector=False):
        name='inspect_frames' if inspector else PLAN_TOOL['name']
        messages=[{'role':'user','content':[text_block('fixture')]},
                  {'role':'assistant','content':call(name,{'ok':False})},
                  {'role':'user','content':[{'type':'tool_result','tool_use_id':'t','is_error':True,'content':'根拠画像の時刻が区間外'}]}]
        Checkpoint(self.out,'content_plan',{'system':'system','content':[text_block('fixture')],'tool':PLAN_TOOL}).save(messages=messages,round=6)

    @staticmethod
    def validate(value):
        if not value.get('ok'):
            raise ValueError('根拠画像の時刻が区間外')
        return value

    def run_session(self,q):
        return q.session('content_plan',[text_block('fixture')],'system',PLAN_TOOL,self.validate)

    def test_last_rejected_submission_gets_a_repair_after_normal_turns(self):
        q=self.make([call('inspect_frames')]*4 + [call(PLAN_TOOL['name'],{'ok':False})]*2 + [call(PLAN_TOOL['name'],{'ok':True})])
        self.assertTrue(self.run_session(q)['ok'])
        self.assertEqual(len(q.client.calls),7)
        self.assertEqual(q.evidence.inspect_calls,4)
        self.assertTrue(all(t==q.client.seen_tools[0] for t in q.client.seen_tools))
        self.assertEqual(q.config.budget_usd,3.85)
        self.assertEqual(q.config.max_api_calls,12)

    def test_legacy_checkpoint_continues_from_the_failed_submission(self):
        self.saved_rejection()
        q=self.make([call(PLAN_TOOL['name'],{'ok':True})],resume=True)
        self.assertTrue(self.run_session(q)['ok'])
        self.assertEqual(len(q.client.calls),1)

    def test_two_failed_repairs_are_not_reset_by_another_resume(self):
        self.saved_rejection()
        q=self.make([call(PLAN_TOOL['name'],{'ok':False})]*2,resume=True)
        with self.assertRaises(SubmissionRepairLimit) as caught:
            self.run_session(q)
        self.assertEqual(caught.exception.code,'round_limit')
        self.assertEqual(len(q.client.calls),2)
        state=json.loads((self.out/'quality-progress.json').read_text(encoding='utf-8'))
        self.assertEqual(state['validation_repairs_used'],2)
        q=self.make([],resume=True)
        with self.assertRaises(SubmissionRepairLimit):self.run_session(q)
        self.assertEqual(q.client.calls,[])

    def test_extra_repair_does_not_fetch_new_frames(self):
        self.saved_rejection()
        q=self.make([call('inspect_interval'),call(PLAN_TOOL['name'],{'ok':True})],resume=True)
        self.assertTrue(self.run_session(q)['ok'])
        self.assertEqual(q.evidence.inspect_calls,0)
        self.assertTrue(any('追加取得の枠は終了' in e['error'] for e in q.events))

    def test_extra_repair_cannot_search_the_web(self):
        self.saved_rejection()
        q=self.make([call('search_web'),call(PLAN_TOOL['name'],{'ok':True})],resume=True)
        def forbidden(*args):raise AssertionError('A repair must not perform more research')
        q.research.execute=forbidden
        self.assertTrue(self.run_session(q)['ok'])
        self.assertTrue(any('追加調査の枠は終了' in e['error'] for e in q.events))

    def test_inspector_error_does_not_unlock_extra_submission_turns(self):
        self.saved_rejection(inspector=True)
        q=self.make([],resume=True)
        with self.assertRaises(ValueError):self.run_session(q)
        self.assertEqual(q.client.calls,[])

    def test_budget_stop_propagates_without_consuming_a_repair(self):
        self.saved_rejection()
        q=self.make([BudgetStop('budget',code='budget')],resume=True)
        with self.assertRaises(BudgetStop):self.run_session(q)
        self.assertEqual(q.client.calls,[])
        saved=Checkpoint(self.out,'content_plan',{'system':'system','content':[text_block('fixture')],'tool':PLAN_TOOL}).load()
        self.assertEqual(saved['validation_repairs_used'],0)
        q=self.make([call(PLAN_TOOL['name'],{'ok':True})],resume=True)
        self.assertTrue(self.run_session(q)['ok'])

    def test_a_valid_first_submission_does_not_make_repair_calls(self):
        q=self.make([call(PLAN_TOOL['name'],{'ok':True})])
        self.assertTrue(self.run_session(q)['ok'])
        self.assertEqual(len(q.client.calls),1)

    def test_unrelated_tool_errors_are_not_legacy_validation_errors(self):
        self.assertIsNone(pending_submission_error([],PLAN_TOOL['name']))
        self.saved_rejection(inspector=True)
        saved=Checkpoint(self.out,'content_plan',{'system':'system','content':[text_block('fixture')],'tool':PLAN_TOOL}).load()
        self.assertIsNone(pending_submission_error(saved['messages'],PLAN_TOOL['name']))

    def test_mixed_inspection_and_submission_does_not_unlock_legacy_repairs(self):
        messages=[{'role':'assistant','content':call('inspect_frames')+call(PLAN_TOOL['name'],identity='s')},
                  {'role':'user','content':[{'type':'tool_result','tool_use_id':'s','is_error':True,'content':'submit separately'}]}]
        self.assertIsNone(pending_submission_error(messages,PLAN_TOOL['name']))

    def test_appended_research_reuses_only_a_matching_pending_conversation(self):
        original=[text_block({'request':'same source and task'}),text_block({'external_sources_untrusted':[], 'queries_used':0,'page_attempts':0})]
        current=[original[0],text_block({'external_sources_untrusted':[{'id':'s1'}], 'queries_used':1,'page_attempts':1})]
        cp=Checkpoint(self.out,'content_plan',{'system':'system','content':original,'tool':PLAN_TOOL})
        cp.save(messages=[{'role':'user','content':original}],round=6)
        continued=research_only_checkpoint(self.out,'content_plan',current,'system',PLAN_TOOL)
        self.assertIsNotNone(continued)
        self.assertEqual(continued[1]['round'],6)
        self.assertIsNone(research_only_checkpoint(self.out,'content_plan',current,'changed system',PLAN_TOOL))
        changed=[text_block({'request':'different task'}),current[1]]
        self.assertIsNone(research_only_checkpoint(self.out,'content_plan',changed,'system',PLAN_TOOL))
        cp.save(result={'ok':True},messages=[{'role':'user','content':original}])
        self.assertIsNone(research_only_checkpoint(self.out,'content_plan',current,'system',PLAN_TOOL))


class PlanValidationTests(unittest.TestCase):
    def make(self):
        q=ContentQuality.__new__(ContentQuality)
        q.evidence=SimpleNamespace(duration=200,records=[{'file':'assets/a.jpg','seconds':109.11},
                                                      {'file':'assets/b.jpg','seconds':161.16}])
        q.config=Config(external_research=False)
        q.research=SimpleNamespace(facts=lambda units:[])
        return q

    @staticmethod
    def plan():
        return {'kind':'lecture','overview':'講義','visual_requirements':[
                    {'role':r,'status':'not_applicable','finding':'対象外','evidence_files':[]}
                    for r in ['materials','tools','guides']],
                'units':[{'id':'u03','type':'claim','title':'要点','explanation':'説明','start':138,'end':165.3,
                          'risk':'none','evidence_files':['assets/a.jpg','assets/b.jpg']}]}

    def test_missing_preparation_image_and_wrong_timestamps_are_reported_together(self):
        q=self.make(); plan=self.plan(); original=copy.deepcopy(plan)
        plan['visual_requirements'][0]['status']='visible'
        plan['visual_requirements'][1]['status']='visible'
        with self.assertRaises(ValueError) as caught:q.validate_plan(plan)
        text=str(caught.exception)
        self.assertIn('visual_requirements',text)
        self.assertIn('materials:',text)
        self.assertIn('tools:',text)
        self.assertIn('u03:',text)
        self.assertIn('109.11',text)
        self.assertEqual(plan['units'],original['units'])

    def test_outside_timestamps_are_not_automatically_widened_to_pass(self):
        q=self.make(); plan=self.plan()
        with self.assertRaises(ValueError):q.validate_plan(plan)
        self.assertEqual(plan['units'][0]['start'],138)
        plan['units'][0]['start']=108
        accepted=q.validate_plan(plan)
        self.assertEqual(accepted['units'][0]['evidence_files'],['assets/a.jpg','assets/b.jpg'])


class ResumeCostTests(unittest.TestCase):
    def test_automatic_resume_keeps_the_previous_total_ceiling(self):
        config=Config(resume=True)
        inherit_resume_budget(config,{'budget_usd':3.85})
        self.assertEqual(config.budget_usd,3.85)

    def test_explicit_lower_ceiling_is_not_overwritten(self):
        config=Config(resume=True,budget_usd=1)
        inherit_resume_budget(config,{'budget_usd':3.85})
        self.assertEqual(config.budget_usd,1)


if __name__=='__main__':unittest.main()
