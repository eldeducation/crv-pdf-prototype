"""Content-led page planning and recorded visual self-review.

These gates check coverage/bindings, not whether a design is beautiful. The
editor must actually inspect the rendered pages; no extra model stage is added.
"""
import re
from html.parser import HTMLParser

TEXT = {'type': 'string'}
DESIGN_PLAN_SCHEMA = {'type': 'object', 'required': ['reader_goal', 'visual_direction', 'pages'],
    'properties': {'reader_goal': TEXT, 'visual_direction': TEXT,
        'pages': {'type': 'array', 'minItems': 1, 'maxItems': 24, 'items': {
            'type': 'object', 'required': ['page', 'message', 'layout', 'focus_excerpt', 'rationale', 'source_units'],
            'properties': {'page': {'type': 'integer', 'minimum': 1}, 'message': TEXT,
                'layout': TEXT, 'focus_excerpt': TEXT, 'rationale': TEXT,
                'source_units': {'type': 'array', 'minItems': 1, 'maxItems': 80, 'items': TEXT}}}}}}
ASSESSMENT = {'type': 'object', 'required': ['verdict', 'finding'],
    'properties': {'verdict': {'enum': ['supported', 'revise']}, 'finding': TEXT}}
DESIGN_REVIEW_SCHEMA = {'type': 'object', 'required': ['pages', 'document'],
    'properties': {'document': ASSESSMENT,
        'pages': {'type': 'array', 'minItems': 1, 'maxItems': 24, 'items': {
            'type': 'object', 'required': ['page', 'preview', 'observed_excerpt', 'hierarchy', 'readability', 'composition', 'visual_integrity'],
            'properties': {'page': {'type': 'integer', 'minimum': 1}, 'preview': TEXT,
                'observed_excerpt': TEXT, **{k: ASSESSMENT for k in (
                    'hierarchy', 'readability', 'composition', 'visual_integrity')}}}}}}


class _Text(HTMLParser):
    def __init__(self, markup):
        super().__init__(); self.parts = []; self.feed(markup)
    def handle_data(self, value):
        self.parts.append(value)


def normalized(value):
    return re.sub(r'\s+', '', value)


def body_text(page):
    return normalized(' '.join(_Text(page['html']).parts))


def _text(value, name, limit=500):
    if not isinstance(value, str) or not 4 <= len(value.strip()) <= limit:
        raise ValueError(f'{name}を4～{limit}文字で具体的に記録してください。')


def _pages(records, count, name):
    if not isinstance(records, list) or len(records) != count:
        raise ValueError(f'{name}は全{count}ページ分が必要です。')
    numbers = [r.get('page') for r in records if isinstance(r, dict)]
    if any(type(i) is not int for i in numbers) or sorted(numbers) != list(range(1, count+1)):
        raise ValueError(f'{name}のページ番号に重複・欠落があります。')
    return sorted(records, key=lambda r: r['page'])


def validate_design_plan(document, plan):
    design = document.get('design_plan')
    if not isinstance(design, dict):
        raise ValueError('デザイン重視ではdesign_planで内容から紙面を設計してください。別のAI呼び出しは不要です。')
    _text(design.get('reader_goal'), '読者の目的')
    _text(design.get('visual_direction'), '配色・文字・余白の方針')
    known = {u['id'] for u in plan['units']}
    for record, page in zip(_pages(design.get('pages'), len(document['pages']), '紙面設計'), document['pages']):
        for key in ('message', 'layout', 'focus_excerpt', 'rationale'):
            _text(record.get(key), '紙面設計の'+key)
        if normalized(record['focus_excerpt']) not in body_text(page):
            raise ValueError(f'{record["page"]}ページ: focus_excerptは実際の本文・見出しから引用してください。')
        refs = record.get('source_units')
        if not isinstance(refs, list) or not refs or any(not isinstance(i, str) or i not in known for i in refs):
            raise ValueError('紙面設計のsource_unitsに内容案のidを指定してください。')
        assigned = page.get('source_units', [])
        if assigned and not set(refs) <= set(assigned):
            raise ValueError('紙面設計と実際のページのsource_unitsが一致しません。')
    return design


def validate_design_review(review, document, qa):
    if not isinstance(review, dict):
        raise ValueError('デザイン重視では全ページの完成画像を見てdesign_reviewを記録してください。')
    approved = True
    def assess(value):
        nonlocal approved
        if not isinstance(value, dict) or value.get('verdict') not in ('supported', 'revise'):
            raise ValueError('紙面の各観点をsupported/reviseで判定してください。')
        _text(value.get('finding'), '紙面で観察した内容')
        approved = approved and value['verdict'] == 'supported'
    assess(review.get('document'))
    previews = qa.get('previews', [])
    for record in _pages(review.get('pages'), len(document['pages']), '紙面確認'):
        i = record['page']-1
        if i >= len(previews) or record.get('preview') != previews[i]:
            raise ValueError('紙面確認には、そのページの今回のプレビューを指定してください。')
        _text(record.get('observed_excerpt'), '紙面の引用')
        if normalized(record['observed_excerpt']) not in body_text(document['pages'][i]):
            raise ValueError('紙面のobserved_excerptは、そのページに実在する本文から引用してください。')
        for key in ('hierarchy', 'readability', 'composition', 'visual_integrity'):
            assess(record.get(key))
    if not approved:
        raise ValueError('紙面確認にreviseが残っています。指摘したページを修正して再提出してください。')
    return review
