"""Synthetic workbook regressions, no video download or AI API calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace

from PIL import Image
import pipeline
from document_design import editorial_brief, select_design
from manual_client import validate_schema
from render_test_support import require_renderer
from training_quality import TRAINING_PLAN_SCHEMA, validate_training_plan, editor_system, reviewer_system
from content_quality import ContentQuality, DOCUMENT_REVIEWER


def fixture():
    refs = ['c01']
    def page(markup):
        return {'html':markup+'<span data-source-unit="c01"></span>', 'source_units':refs[:]}
    doc = {'title':'確認してから対応する', 'summary':'合成した研修テスト用資料', 'css':'', 'pages':[
        page('<h1>確認してから対応する</h1><p>学習目標は対応前に確認する理由を説明できること。</p>'
             '<p>確認してから対応へ進む流れです。</p><p>例文は「状況を確認させてください」です。</p>'
             '<figure><img src="assets/frame_001.jpg"><figcaption>説明を確認する合成画像</figcaption></figure>'),
        page('<h2>確認問題と応用練習</h2><p>Q1 対応する前に何を確かめますか。</p>'
             '<p>教材用に作成した架空の場面です。</p><p>相談を受けましたが内容が不明です。</p>'
             '<p>最初にどう話すか考えてください。</p>'),
        page('<h2>解答と理由</h2><p>A1 状況を聞き、相手と認識を合わせます。</p>'
             '<p>練習では内容を尋ねてから対応を考えます。</p>'),
        page('<h2>実務への持ち帰り</h2><p>適用先の担当者と相談して記入してください。</p>'
             '<p>相談する担当者は誰ですか。</p><p>判断できる範囲はどこですか。</p><p>＿＿＿＿＿＿＿＿</p>'
             '<div class="wrapup"><p class="label">まとめ</p><h2>対応の前に確認する</h2><ol>'
             '<li>対応する前に状況を確かめる。</li><li>相手と認識を合わせてから対応を考える。</li>'
             '<li>判断できる範囲は担当者と相談する。</li></ol></div>')],
        'training_plan':{
            'learning_goals':{'page':1,'excerpt':'学習目標は対応前に確認する理由を説明できること。','source_units':refs[:] },
            'overview':{'page':1,'excerpt':'確認してから対応へ進む流れです。','source_units':refs[:]},
            'examples':[{'page':1,'excerpt':'例文は「状況を確認させてください」です。','source_units':refs[:]}],
            'questions':[{'id':'q1','question_page':2,'question_excerpt':'Q1 対応する前に何を確かめますか。',
                          'answer_page':3,'answer_excerpt':'A1 状況を聞き、相手と認識を合わせます。','source_units':refs[:]}],
            'practice':{'page':2,'scenario_excerpt':'相談を受けましたが内容が不明です。',
                        'fiction_notice_excerpt':'教材用に作成した架空の場面です。','task_excerpt':'最初にどう話すか考えてください。',
                        'answer_page':3,'answer_excerpt':'練習では内容を尋ねてから対応を考えます。','source_units':refs[:]},
            'application':{'page':4,'instruction_excerpt':'適用先の担当者と相談して記入してください。',
                           'prompts':['相談する担当者は誰ですか。','判断できる範囲はどこですか。']}}}
    plan = {'kind':'lecture','overview':'合成したテスト内容','units':[{'id':'c01','type':'claim','start':0,'end':10,
             'explanation':'対応の前に状況を確認する。','evidence_files':['assets/frame_001.jpg']}],
            'visual_requirements':[{'role':r,'status':'not_applicable','finding':'合成した講義テスト','evidence_files':[]}
                                   for r in ('materials','tools','guides')]}
    return doc,plan


class StructureTests(unittest.TestCase):
    def setUp(self):
        self.doc,self.plan = fixture()

    def test_complete_workbook_and_manual_schema_pass(self):
        validate_schema(self.doc['training_plan'],TRAINING_PLAN_SCHEMA)
        self.assertEqual(validate_training_plan(self.doc,self.plan),self.doc['training_plan'])

    def test_side_by_side_answers_are_rejected(self):
        q = self.doc['training_plan']['questions'][0]
        q['answer_page'] = q['question_page']
        self.doc['pages'][1]['html'] += '<p>'+q['answer_excerpt']+'</p>'
        with self.assertRaisesRegex(ValueError,'別ページ'):validate_training_plan(self.doc,self.plan)

    def test_answer_leak_on_another_question_page_is_rejected(self):
        q = self.doc['training_plan']['questions'][0]
        self.doc['pages'][1]['html'] += '<p>'+q['answer_excerpt']+'</p>'
        with self.assertRaisesRegex(ValueError,'併記'):validate_training_plan(self.doc,self.plan)

    def test_metadata_does_not_substitute_for_real_body(self):
        self.doc['pages'][1]['html'] = '<h2>確認問題だけ</h2>'
        with self.assertRaises(ValueError) as result:validate_training_plan(self.doc,self.plan)
        self.assertIn('問題',str(result.exception))
        self.assertIn('fiction_notice_excerpt',str(result.exception))

    def test_missing_practice_and_application_are_reported_together(self):
        del self.doc['training_plan']['practice'];del self.doc['training_plan']['application']
        with self.assertRaises(ValueError) as result:validate_training_plan(self.doc,self.plan)
        self.assertIn('応用練習',str(result.exception));self.assertIn('確認欄',str(result.exception))

    def test_unknown_sources_wrong_assignment_and_boolean_pages_are_rejected(self):
        for change in ('unknown','page_assignment','boolean'):
            doc=copy.deepcopy(self.doc)
            if change=='unknown':doc['training_plan']['questions'][0]['source_units']=['made_up']
            elif change=='page_assignment':doc['pages'][2]['source_units']=[]
            else:doc['training_plan']['learning_goals']['page']=True
            with self.subTest(change=change),self.assertRaises(ValueError):validate_training_plan(doc,self.plan)

    def test_answer_before_later_exercise_and_duplicate_ids_are_rejected(self):
        q=self.doc['training_plan']['questions'][0]
        self.doc['training_plan']['questions'].append(copy.deepcopy(q))
        self.doc['training_plan']['practice']['page']=3
        with self.assertRaises(ValueError) as result:validate_training_plan(self.doc,self.plan)
        self.assertIn('重複',str(result.exception));self.assertIn('全設問',str(result.exception))

    def test_partial_revision_must_update_changed_excerpt(self):
        changed=pipeline.revised_draft(self.doc,{'pages':[{'page':3,'html':self.doc['pages'][2]['html'].replace('状況を聞き','状況を丁寧に聞き')}]})
        with self.assertRaises(ValueError):validate_training_plan(changed,self.plan)
        metadata=copy.deepcopy(changed['training_plan'])
        metadata['questions'][0]['answer_excerpt']='A1 状況を丁寧に聞き、相手と認識を合わせます。'
        fixed=pipeline.revised_draft(changed,{'pages':[{'page':3,'html':changed['pages'][2]['html']}],'training_plan':metadata})
        validate_training_plan(fixed,self.plan)
        self.assertEqual(fixed['pages'][0],self.doc['pages'][0])

    def test_training_guidance_not_applied_to_other_purposes(self):
        for purpose in ('auto','seminar','procedure'):
            self.assertNotIn('training_guidance',editorial_brief(select_design(self.plan,purpose,'editorial')))
        self.assertIn('training_guidance',editorial_brief(select_design(self.plan,'training','editorial')))
        for purpose in ('auto','seminar','procedure'):
            self.assertEqual(editor_system('original editor',purpose),'original editor')
            self.assertEqual(reviewer_system('original reviewer',purpose),'original reviewer')
        self.assertIn('training_plan',editor_system('original editor','training'))

    def test_existing_review_receives_training_bindings_without_an_extra_session(self):
        review=ContentQuality.__new__(ContentQuality)
        review.plan=self.plan
        review.config=SimpleNamespace(efficient=False)
        review.notify=lambda _:None
        review.save=lambda *_:None
        review.evidence_content=lambda **_:[]
        review.session=Mock(return_value={'approved':True})
        doc={**self.doc,'presentation':{'purpose':'training'}}
        review.review_document(doc,1)
        self.assertEqual(review.session.call_count,1)
        args=review.session.call_args.args
        submitted=json.loads(args[1][0]['text'])['document']
        self.assertEqual(submitted['training_plan'],doc['training_plan'])
        self.assertIn('架空',args[2])
        review.session.reset_mock()
        review.review_document({**self.doc,'presentation':{'purpose':'seminar'}},1)
        args=review.session.call_args.args
        self.assertEqual(args[2],DOCUMENT_REVIEWER)
        self.assertNotIn('training_plan',json.loads(args[1][0]['text'])['document'])


class BuildAndRenderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name)
        assets=self.out/'assets';assets.mkdir();Image.new('RGB',(1280,720),'#34607a').save(assets/'frame_001.jpg')
        self.evidence=pipeline.Evidence.__new__(pipeline.Evidence)
        self.evidence.out,self.evidence.assets,self.evidence.source=self.out,assets.resolve(),'upload.mp4'
        self.evidence.records=[{'file':'assets/frame_001.jpg','seconds':5}]
        self.doc,self.plan=fixture()

    def tearDown(self):self.temp.cleanup()

    def build(self,doc,purpose='training'):
        return pipeline.build_document(copy.deepcopy(doc),self.plan,{'purpose':purpose,'design':'plain'},self.evidence,'ja')

    def test_training_gate_is_active_for_every_design_and_other_purposes_keep_working(self):
        missing=copy.deepcopy(self.doc);del missing['training_plan']
        with self.assertRaisesRegex(pipeline.PrototypeError,'training_plan'):self.build(missing)
        self.build(missing,'seminar')
        built,_=self.build(self.doc)
        self.assertEqual(built['training_plan'],self.doc['training_plan'])

    def test_full_pdf_render_keeps_exercises_answers_and_image(self):
        require_renderer(self)
        doc,markup=self.build(self.doc)
        (self.out/'document.html').write_text(markup,encoding='utf-8')
        qa=pipeline.check_pages(self.out,doc)
        self.assertEqual(qa['errors'],[])
        from pypdf import PdfReader
        pages=PdfReader(self.out/'document.pdf').pages
        self.assertEqual(len(pages),4)
        self.assertIn('Q1',pages[1].extract_text())
        self.assertNotIn('A1',pages[1].extract_text())
        self.assertIn('A1',pages[2].extract_text())
        self.assertIn('架空',pages[1].extract_text())
        self.assertTrue(pages[0].images)
        self.assertIn('教材用に作成した架空の場面です。',doc['markdown'])


if __name__=='__main__':unittest.main()
