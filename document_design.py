"""Purpose/style decisions and local, evidence-linked visual components.

No AI or network calls. Formal source checks do not prove semantic correctness;
the existing final document review must also read labels, conditions and claims.
"""
import copy
import math
import re
from html import escape
from document_options import normalize_modes, PRESENTATION_MODES

VERSION = 'adaptive-design-v3'
VISUAL_SCHEMA = {'type': 'array', 'maxItems': 16, 'items': {
    'type': 'object', 'required': ['id', 'type', 'title', 'condition', 'items'],
    'properties': {
        'id': {'type': 'string'},
        'type': {'enum': ['bar', 'comparison', 'flow', 'metrics']},
        'title': {'type': 'string'}, 'condition': {'type': 'string'},
        'unit': {'enum': ['percent', 'count']},
        'measure': {'enum': ['intention', 'observed', 'speaker_claim']},
        'items': {'type': 'array', 'minItems': 2, 'maxItems': 8, 'items': {
            'type': 'object', 'required': ['label', 'text', 'source_unit', 'excerpt'],
            'properties': {'label': {'type': 'string'}, 'text': {'type': 'string'},
                'source_unit': {'type': 'string'}, 'excerpt': {'type': 'string'},
                'value': {'type': 'number'}}}}}}}


def select_design(plan, purpose='auto', design='auto', visual_density='auto', presentation_modes=()):
    modes = normalize_modes(presentation_modes)
    kind = plan['kind']
    resolved = purpose if purpose != 'auto' else {'procedure': 'procedure', 'lecture': 'seminar', 'mixed': 'mixed'}[kind]
    style = 'editorial' if design == 'visual' else design if design != 'auto' else ('plain' if resolved == 'procedure' else 'editorial')
    density = 'more' if design == 'visual' and visual_density == 'auto' else visual_density
    return {'version': VERSION, 'requested_purpose': purpose, 'purpose': resolved,
            'video_kind': kind, 'requested_design': design, 'design': style,
            'requested_visual_density': visual_density, 'visual_density': density,
            'presentation_modes': list(modes),
            'selection_basis': 'user' if purpose != 'auto' else 'video_kind',
            'sections_adapt_to_content': True,
            'content_led_page_plan': style == 'editorial',
            'rendered_page_self_review': style == 'editorial'}


def editorial_brief(selection):
    purpose = selection['purpose']
    structure = {
        'procedure': '準備と向きの基準→順序どおりの操作・写真・完了状態→仕上がり確認。難しい動作に紙面を割く。',
        'seminar': '全体像→論点と根拠→事例→結論。ページごとに中心メッセージを一つ定める。',
        'training': '学習目標→説明・実演→注意と応用→振り返り問題と回答。架空の社内ルールを追加しない。',
        'mixed': '講演・解説と実演を章ごとに分ける。操作の部分だけ順番と完了状態を説明する。',
    }[purpose]
    return {'presentation_selection': selection, 'structure_guidance': structure,
            'arrangement_guidance': [PRESENTATION_MODES[mode] for mode in normalize_modes(selection.get('presentation_modes', ()))],
            'style_guidance': ('デザイン重視。見出し・重要数値・引用・配色・余白にメリハリをつける。ページの主役を決め、内容に応じて段組みと大小・配置を変える。図解を増やすこと自体を目的にしない。'
                               if selection['design'] in {'visual', 'editorial'} else
                               '静かな配色・明確な見出し・整った余白で整理する。図解の量は独立した設定に従う。内容・条件・必要な中間操作は維持する。'),
            'visual_density_guidance': {'auto': '理解に役立つ箇所だけ図表を使う。', 'more': '理解に役立つ図表を優先し、重複を避ける。', 'fewer': '文章・写真・表を中心に、必要な図だけ残す。'}[selection.get('visual_density', 'auto')],
            'note_policy': '重要条件は数値・操作のすぐ近く、その他の補足は短い注記へ。確認文を各ページで反復しない。',
            'page_design_workflow': '読者の目的と内容の関係から紙面を設計し、design_planをcompose_documentに一緒に提出。全ページの実画像を見てdesign_reviewをapprove_documentに記録する。追加のAI呼び出し・設計専用ツールは不要。部品の一覧を順番に埋めない。' if selection['design'] == 'editorial' else '内容に合った読みやすい構成を選ぶ。'}


DESIGN_CSS = '''
.visual-block { margin: 3mm 0 4mm; break-inside: avoid; }
.visual-block h3 { margin: 0 0 2.5mm; }
.visual-note { font-size: 8pt; line-height: 1.6; color: #53685e; margin: 2mm 0; }
.viz-bar-row { display: grid; grid-template-columns: 42% 1fr 13%; gap: 3mm; align-items: center; margin: 2mm 0; font-size: 9pt; }
.viz-bar-track { background: #e6ede8; height: 4mm; }
.viz-bar-fill { background: var(--heading-color); height: 4mm; }
.viz-bar-number { font-weight: bold; text-align: right; }
.viz-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 4mm; }
.viz-grid .viz-item { border: .3mm solid #dce4df; padding: 3mm; }
.viz-metrics { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 3mm; }
.viz-metrics .viz-item { padding: 3mm; background: var(--accent-soft); }
.viz-metrics strong { display: block; color: var(--heading-color); font-size: 18pt; line-height: 1.4; }
.viz-item p { margin: 1.5mm 0 0; }
.viz-flow { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 3mm; padding-left: 6mm; }
.viz-flow li { padding: 3mm; background: var(--accent-soft); }
'''


def style_css(design):
    if design == 'plain':
        return DESIGN_CSS + '''
h1,h2 { letter-spacing: .01em; } .card { border-radius: 0; }
.callout { background: #f5f7f5; border-left-width: .7mm; }
.stat { font-size: 25pt; color: var(--heading-color); }
.viz-metrics strong { font-size: 16pt; }
'''
    return DESIGN_CSS + '''
h1 { font-size: 29pt; } h2 { font-size: 22pt; letter-spacing: .02em; }
.eyebrow { font-weight: bold; letter-spacing: .08em; color: var(--heading-color); }
.lead { font-size: 14pt; } .stat { font-size: 34pt; color: var(--heading-color); }
.card { background: var(--accent-soft); border-radius: 1.5mm; }
blockquote { font-weight: bold; color: var(--heading-color); }
.section-index { font-size: 28pt; line-height: 1.2; color: var(--heading-color); font-weight: bold; }
.pullquote { border-left: 1.2mm solid var(--heading-color); padding: 3mm 4mm; margin: 4mm 0; font-size: 16pt; line-height: 1.5; font-weight: bold; }
.feature { background: var(--accent-soft); padding: 4mm 5mm; margin: 4mm 0; }
'''


def _text(value, limit=500, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise ValueError('図表の見出し・説明・出典を短い文字列で指定してください。')
    return value


def render_visual(spec, units, language='ja'):
    identity = spec.get('id', '')
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', identity):
        raise ValueError('図表idは英小文字から始まる40字以内です。')
    kind = spec.get('type')
    if kind not in {'bar', 'comparison', 'flow', 'metrics'}:
        raise ValueError('対応していない図表です。')
    title = _text(spec.get('title'), 160)
    condition = _text(spec.get('condition'), 500, empty=kind not in {'bar', 'metrics'})
    items = spec.get('items')
    if not isinstance(items, list) or not 2 <= len(items) <= 8:
        raise ValueError('図表の項目数は2～8です。')
    refs, values = [], []
    for item in items:
        _text(item.get('label'), 120); _text(item.get('text'), 500)
        unit = units.get(item.get('source_unit'))
        quote = _text(item.get('excerpt'), 800)
        # Excerpts must exist in the accepted source plan, not a new quote invented
        # only for the figure. Meaning and label binding are checked by the reviewer.
        if not unit or quote not in unit['explanation']:
            raise ValueError('図表のexcerptは、指定した内容案のexplanationから原文を引用してください。')
        refs.append(unit['id'])
        if kind == 'bar':
            value = item.get('value')
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('棒グラフは有限の0以上の数値が必要です。')
            if not any(float(n) == value for n in re.findall(r'(?<![\d.])\d+(?:\.\d+)?(?![\d.])', quote)):
                raise ValueError('棒グラフの数値が出典の引用にありません。')
            values.append(value)
        elif 'value' in item:
            raise ValueError('valueは棒グラフでのみ使用します。他の図表は出典の値をtextに記載してください。')
        if kind == 'metrics':
            numbers = re.findall(r'\d+(?:\.\d+)?', item['label']+' '+item['text'])
            quoted = re.findall(r'\d+(?:\.\d+)?', quote)
            if any(n not in quoted for n in numbers):
                raise ValueError('数値カードの値を出典の引用と一致させてください。')
    if kind == 'bar':
        if spec.get('unit') not in {'percent', 'count'} or spec.get('measure') not in {'intention', 'observed', 'speaker_claim'}:
            raise ValueError('棒グラフの単位と意向・実績・話者の説明の区別が必要です。')
        if spec['unit'] == 'percent' and max(values) > 100:
            raise ValueError('割合の棒グラフは0～100%で指定してください。')
        ceiling = 100 if spec['unit'] == 'percent' else max(max(values), 1)
        suffix = '%' if spec['unit'] == 'percent' else ''
        rows = []
        for item, value in zip(items, values):
            rows.append(f'<div class="viz-bar-row"><span>{escape(item["label"])}<br><small>{escape(item["text"])}</small></span><div class="viz-bar-track"><div class="viz-bar-fill" style="width:{value/ceiling*100:.4f}%"></div></div><span class="viz-bar-number">{value:g}{suffix}</span></div>')
        labels = {'intention': ('回答意向', 'Reported intentions'), 'observed': ('実績', 'Observed results'), 'speaker_claim': ('話者が紹介した数値', 'Figures reported by the speaker')}
        condition = labels[spec['measure']][language == 'en'] + ' / ' + condition
        body = ''.join(rows)
    else:
        blocks = [f'<strong>{escape(i["label"])}</strong><p>{escape(i["text"])}</p>' for i in items]
        if kind == 'flow':
            body = '<ol class="viz-flow">' + ''.join('<li>'+s+'</li>' for s in blocks) + '</ol>'
        else:
            body = f'<div class="{"viz-grid" if kind == "comparison" else "viz-metrics"}">' + ''.join('<div class="viz-item">'+s+'</div>' for s in blocks) + '</div>'
    refs = list(dict.fromkeys(refs))
    markup = '<div class="visual-block"><h3>'+escape(title)+'</h3>'+body+'<p class="visual-note">'+escape(condition)+'</p>'+''.join(f'<span data-source-unit="{escape(u)}"></span>' for u in refs)+'</div>'
    def md(text): return text.replace('|', '\\|').replace('\n', ' ')
    markdown = '\n\n### '+title+'\n\n'
    for item in items:
        value = (f' — {item["value"]:g}'+('%' if spec['unit']=='percent' else '')) if kind == 'bar' else ''
        markdown += '- **'+md(item['label'])+'**'+value+'：'+md(item['text'])+'\n'
    markdown += '\n'+condition+'\n\n'
    return markup, markdown, refs


def materialize_visuals(document, plan, language='ja'):
    doc = copy.deepcopy(document)
    specs = doc.get('visuals', [])
    if not isinstance(specs, list) or len(specs) > 16:
        raise ValueError('図表は16件以内です。')
    units = {u['id']: u for u in plan['units']}
    seen = set()
    for spec in specs:
        markup, markdown, refs = render_visual(spec, units, language)
        identity = spec['id']
        if identity in seen: raise ValueError('図表idが重複しています。')
        seen.add(identity)
        marker = f'<!-- visual:{identity} -->'
        pages = [p for p in doc['pages'] if marker in p['html']]
        if len(pages) != 1 or pages[0]['html'].count(marker) != 1 or doc['markdown'].count(marker) != 1:
            raise ValueError('各図表の<!-- visual:id -->をPDFとMarkdownに1回ずつ配置してください。')
        page = pages[0]
        if not set(refs) <= set(page.get('source_units', [])):
            raise ValueError('図表の出典idを同じページのsource_unitsにも記録してください。')
        page['html'] = page['html'].replace(marker, markup)
        doc['markdown'] = doc['markdown'].replace(marker, markdown)
    if any(re.search(r'<!--\s*visual:', p['html']) for p in doc['pages']) or re.search(r'<!--\s*visual:', doc['markdown']):
        raise ValueError('定義されていない図表のプレースホルダーがあります。')
    return doc
