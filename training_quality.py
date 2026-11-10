"""Check usable training structure locally, inside the existing submission gate.

Page/excerpt/source bindings are mechanical checks. The existing video reviewer
still judges meaning, fictional-case labels, examples and photograph usefulness.
"""
import re
from editorial_quality import body_text, normalized

VERSION = 'training-workbook-v1'
TEXT = {'type': 'string', 'minLength': 4, 'maxLength': 300}
PAGE = {'type': 'integer', 'minimum': 1, 'maximum': 24}
REFS = {'type': 'array', 'minItems': 1, 'maxItems': 12, 'items': {'type':'string'}}
ANCHOR = {'type':'object', 'required':['page','excerpt','source_units'],
          'properties':{'page':PAGE,'excerpt':TEXT,'source_units':REFS}}
TRAINING_PLAN_SCHEMA = {
    'type':'object',
    'description':'研修資料のみ必須。本文の短い原文とページで、学習・演習・解答の実在と分離を検査する。',
    'required':['learning_goals','overview','examples','questions','practice','application'],
    'properties':{
        'learning_goals':ANCHOR, 'overview':ANCHOR,
        'examples':{'type':'array','minItems':1,'maxItems':8,'items':ANCHOR},
        'questions':{'type':'array','minItems':1,'maxItems':8,'items':{
            'type':'object','required':['id','question_page','question_excerpt','answer_page','answer_excerpt','source_units'],
            'properties':{'id':{'type':'string'},'question_page':PAGE,'question_excerpt':TEXT,
                          'answer_page':PAGE,'answer_excerpt':TEXT,'source_units':REFS}}},
        'practice':{'type':'object',
            'required':['page','scenario_excerpt','fiction_notice_excerpt','task_excerpt','answer_page','answer_excerpt','source_units'],
            'properties':{'page':PAGE,'scenario_excerpt':TEXT,'fiction_notice_excerpt':TEXT,'task_excerpt':TEXT,
                          'answer_page':PAGE,'answer_excerpt':TEXT,'source_units':REFS}},
        'application':{'type':'object','required':['page','instruction_excerpt','prompts'],
            'properties':{'page':PAGE,'instruction_excerpt':TEXT,
                          'prompts':{'type':'array','minItems':2,'maxItems':5,'items':TEXT}}},
    },
}

TRAINING_GUIDANCE = '''研修は「動画を詳しく再掲する資料」で終わらず、理解して実務へ持ち帰る教材にする。
学習目標と全体像→要点・判断の関係・実際の例文や動作→確認問題と応用練習→別ページの解答・解説→適用時の確認欄、を基本に内容に合わせて構成する。
見出しは伝えたい意味を示す。講義の順をなぞるだけでなく、判断の分岐・比較・理由を理解に役立つ場合だけ図解する。源泉にない判断基準や因果は作らない。
具体例は動画にある表現・事例・動作を使い、必要な条件と出典を付ける。十分な内容がなければ捏造せず不足を伝える。
確認問題と解答は必ず別ページ。すべての設問ページの後に解答を置き、問題ページに答えを併記しない。設問の数は学習内容に合わせ1～8問とし、水増ししない。
学んだ考え方を使う応用練習を1つ置く。架空の場面を教材として作成したことを本文で明記し、実際の動画の出来事と混同させない。場面と問い、後の解答ページに進め方の例を載せる。架空の場面から原因・権限・交換可否・期限などを決めつけない。
持ち帰り欄では適用先で確認する項目を2～5個用意し、担当者と相談・記入するよう案内する。動画にない職場のルールや記入欄の答えは創作しない。社内研修以外なら、その学習内容の適用先に合わせる。
写真は実際の例文・重要な表示・操作の変化の理解や照合に役立つものを選ぶ。同じ話者や似たスライドを枚数のために繰り返さない。比較や変化を示す2～3枚は対応を明示して並べる。操作・材料・道具・位置ガイドの既存の必須写真を削らない。
compose_documentにはtraining_planを同時に提出する。各excerptは該当ページにある短い原文、pageは1始まり、source_unitsは内容案の実在id。同じ説明を長く二重に書かない。学習目標・全体像・examplesは{page,excerpt,source_units}。
questionsは{id,question_page,question_excerpt,answer_page,answer_excerpt,source_units}。practiceは{page,scenario_excerpt,fiction_notice_excerpt,task_excerpt,answer_page,answer_excerpt,source_units}。applicationは{page,instruction_excerpt,prompts:[本文に実在する記入項目]}。
revise_pagesでこれらの原文やページを変更するときはtraining_plan全体も更新する。metadataを本文の代わりにせず、実際の紙面と一致させる。'''

TRAINING_REVIEW_GUIDANCE = '''【研修資料の追加確認】
training_planと実際の本文を照らし、具体例・確認問題・解答・応用練習の進め方が動画の説明や条件に基づいているか確認する。
応用練習は教材用の架空の場面であることが読者に伝わるか確認する。動画の実際の出来事と混同する表示、根拠のない正解、勝手に決めた職場の権限・期限・ルールはcoverage_gapsに挙げる。
問題ページに解答が紛れ込まず、解答と理由を後のページで確認できるか、持ち帰り欄が未確認の社内ルールの断定になっていないかも確認する。
写真は例文・重要表示・動作の理解に役立つか見る。似た話者画像やスライドの重複はsuggestionsへ、重要な根拠写真の欠落や説明との食い違いはcoverage_gapsへ記録する。写真の枚数だけで良否を決めない。'''


def editor_system(base, purpose):
    return base + '\n\n【研修教材の追加条件】\n' + TRAINING_GUIDANCE if purpose == 'training' else base


def reviewer_system(base, purpose):
    return base + '\n\n' + TRAINING_REVIEW_GUIDANCE if purpose == 'training' else base


def validate_training_plan(document, plan):
    training = document.get('training_plan')
    if not isinstance(training, dict):
        raise ValueError('研修資料ではtraining_planが必要です。学習目標・全体像・具体例・別ページの問題と解答・応用練習・持ち帰り欄を本文に作り、対応を記録してください。')
    pages = document['pages']
    bodies = [body_text(page) for page in pages]
    known = {u['id'] for u in plan['units']}
    problems = []

    def page_number(value, label):
        if type(value) is not int or not 1 <= value <= len(pages):
            problems.append(f'{label}: 実在するページ番号を指定してください。')
            return None
        return value

    def excerpt(value, page, label):
        if not isinstance(value, str) or not 4 <= len(value.strip()) <= 300:
            problems.append(f'{label}: 本文の短い原文を4～300文字で引用してください。')
        elif page and normalized(value) not in bodies[page-1]:
            problems.append(f'{label}: 引用「{value[:40]}」が{page}ページの本文にありません。')

    def references(value, page_numbers, label):
        if (not isinstance(value, list) or not 1 <= len(value) <= 12
                or any(not isinstance(i,str) or i not in known for i in value)):
            problems.append(f'{label}: 内容案の実在するsource_unitsを1～12件指定してください。')
        else:
            for number in page_numbers:
                if number and not set(value) <= set(pages[number-1].get('source_units', [])):
                    problems.append(f'{label}: {number}ページのsource_unitsと一致させてください。')

    def anchor(record, label):
        if not isinstance(record, dict):
            problems.append(f'{label}: ページ・本文の原文・source_unitsを記録してください。')
            return None
        number = page_number(record.get('page'),label)
        excerpt(record.get('excerpt'),number,label)
        references(record.get('source_units'),[number],label)
        return number

    goals = anchor(training.get('learning_goals'),'学習目標')
    overview = anchor(training.get('overview'),'全体像')
    examples = training.get('examples')
    example_pages = []
    if not isinstance(examples,list) or not 1 <= len(examples) <= 8:
        problems.append('具体例を1～8件、本文の原文と出典に対応付けてください。')
    else:
        example_pages = [anchor(value,'具体例') for value in examples]

    questions = training.get('questions')
    question_pages, answer_pages, answers, ids = [], [], [], set()
    if not isinstance(questions,list) or not 1 <= len(questions) <= 8:
        problems.append('確認問題と解答を1～8件、別ページに対応付けてください。')
        questions = []
    for question in questions:
        if not isinstance(question,dict):
            problems.append('確認問題はオブジェクトで記録してください。'); continue
        identity = question.get('id')
        if not isinstance(identity,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',identity) or identity in ids:
            problems.append('確認問題のidを空欄・重複のない英数字で指定してください。')
        else:
            ids.add(identity)
        q = page_number(question.get('question_page'),'問題')
        a = page_number(question.get('answer_page'),'解答')
        excerpt(question.get('question_excerpt'),q,'問題')
        excerpt(question.get('answer_excerpt'),a,'解答')
        references(question.get('source_units'),[q,a],'問題と解答')
        if q: question_pages.append(q)
        if a: answer_pages.append(a)
        answers.append(question.get('answer_excerpt'))

    practice = training.get('practice')
    if not isinstance(practice,dict):
        problems.append('教材用の架空の応用練習・その明記・問い・後のページの進め方を用意してください。')
    else:
        p = page_number(practice.get('page'),'応用練習')
        a = page_number(practice.get('answer_page'),'応用練習の解説')
        for key in ('scenario_excerpt','fiction_notice_excerpt','task_excerpt'):
            excerpt(practice.get(key),p,'応用練習の'+key)
        excerpt(practice.get('answer_excerpt'),a,'応用練習の解説')
        references(practice.get('source_units'),[p,a],'応用練習')
        if p: question_pages.append(p)
        if a: answer_pages.append(a)
        answers.append(practice.get('answer_excerpt'))

    if question_pages and answer_pages:
        if min(answer_pages) <= max(question_pages):
            problems.append('問題と解答は別ページにし、応用練習を含む全設問ページの後に解答を置いてください。')
        for number in set(question_pages):
            if any(isinstance(answer,str) and len(answer.strip()) >= 4 and normalized(answer) in bodies[number-1] for answer in answers):
                problems.append(f'{number}ページ: 問題ページに解答の原文が併記されています。解答ページへ分離してください。')
        for label,number in [('学習目標',goals),('全体像',overview)]+[('具体例',n) for n in example_pages]:
            if number and number > min(question_pages):
                problems.append(f'{label}は確認問題より先に説明してください。')

    application = training.get('application')
    if not isinstance(application,dict):
        problems.append('実務・適用先へ持ち帰る確認欄を用意してください。')
    else:
        a = page_number(application.get('page'),'持ち帰り欄')
        excerpt(application.get('instruction_excerpt'),a,'持ち帰り欄の相談・記入案内')
        prompts = application.get('prompts')
        if not isinstance(prompts,list) or not 2 <= len(prompts) <= 5:
            problems.append('持ち帰り欄には実際に相談・記入する確認項目を2～5個用意してください。')
        else:
            for value in prompts: excerpt(value,a,'持ち帰り欄の記入項目')
        if a and answer_pages and a < max(answer_pages):
            problems.append('持ち帰り欄は解答・解説と同じページか、その後に置いてください。')
    if problems:
        raise ValueError('\n'.join(dict.fromkeys(problems)))
    return training
