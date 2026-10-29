"""Require selected teaching images and evidence-backed, usable instructions.

These checks validate coverage and quoted text, not the truth of visual meaning.
The existing model review must still judge what the images and instructions show.
"""
import re
import unicodedata
from html.parser import HTMLParser

ROLES = ('materials', 'tools', 'guides')
VERDICTS = ('supported', 'revise', 'uncertain')
VISIBILITY = ('visible', 'not_visible', 'not_applicable')
THEMES = {
    'green': ('#164c3b', '#edf6f0'), 'red': ('#913d49', '#f7edef'),
    'blue': ('#244c78', '#edf3fa'), 'amber': ('#795019', '#faf3e7'),
    'purple': ('#654780', '#f4eff8'), 'slate': ('#354b5a', '#eff3f5'),
}


def theme_css(theme='green'):
    if not isinstance(theme, str) or theme not in THEMES:
        raise ValueError('themeはgreen・red・blue・amber・purple・slateから選んでください。')
    heading, soft = THEMES[theme]
    return f':root {{ --heading-color: {heading}; --accent-soft: {soft}; }}'
STR = {'type': 'string'}
VISUAL_SCAN = {'type': 'array', 'minItems': 3, 'maxItems': 3, 'items': {
    'type': 'object', 'required': ['role', 'status', 'finding', 'evidence_files'],
    'properties': {
        'role': {'enum': list(ROLES)},
        'status': {'enum': ['visible', 'not_visible', 'not_applicable']},
        'finding': {**STR, 'description': '確認した材料・道具・位置ガイド。なければ理由。1文。'},
        'evidence_files': {'type': 'array', 'maxItems': 6, 'items': STR},
    }}}
VISUAL_CHECKS = {'type': 'array', 'minItems': 3, 'maxItems': 3, 'items': {
    'type': 'object', 'required': ['role', 'verdict', 'observed_status', 'finding', 'evidence_files'],
    'properties': {
        'role': {'enum': list(ROLES)}, 'verdict': {'enum': list(VERDICTS)},
        'observed_status': {'enum': list(VISIBILITY), 'description': '内容案をコピーせず、元画像から再確認した有無。'},
        'finding': STR, 'evidence_files': {'type': 'array', 'maxItems': 6, 'items': STR},
    }}}
DOCUMENT_CHECK = {'type': 'object',
    'required': ['instruction_excerpt', 'completion_excerpt', 'reproducibility', 'image_usefulness'],
    'properties': {
        'instruction_excerpt': {**STR, 'description': '本文から対象・方向・位置を示す短い原文引用。不足なら空文字。'},
        'completion_excerpt': {**STR, 'description': '本文から工程の終了状態を示す短い原文引用。不足なら空文字。'},
        'reproducibility': {'enum': list(VERDICTS)},
        'image_usefulness': {'enum': list(VERDICTS)},
    }}


def role_map(entries, field):
    if not isinstance(entries, list) or len(entries) != len(ROLES):
        raise ValueError(f'{field}: materials・tools・guidesを各1件確認してください。')
    result = {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get('role') not in ROLES or entry['role'] in result:
            raise ValueError(f'{field}: roleの不足・重複・不明な値があります。')
        if not isinstance(entry.get('finding'), str) or not entry['finding'].strip():
            raise ValueError(f'{field}: 何を確認したか、または対象外の理由が必要です。')
        result[entry['role']] = entry
    return result


def files(entry, known):
    names = entry.get('evidence_files')
    if (not isinstance(names, list) or len(names) > 6
            or any(not isinstance(n, str) or n not in known for n in names)
            or len(set(names)) != len(names)):
        raise ValueError('材料・道具・位置ガイドの根拠画像は取得済みの重複のない6件以内にしてください。')
    return set(names)


def validate_visual_scan(plan, records):
    scan = role_map(plan.get('visual_requirements'), 'visual_requirements')
    known = {r['file'] for r in records}
    for entry in scan.values():
        names = files(entry, known)
        if entry.get('status') not in ('visible', 'not_visible', 'not_applicable'):
            raise ValueError('視覚情報のstatusを指定してください。')
        if (entry['status'] == 'visible') != bool(names):
            raise ValueError('visibleには掲載候補の根拠画像を指定し、映っていない場合は空配列にしてください。')
    return scan


def validate_visual_pages(requirements, page_images, pages):
    """An unrelated picture elsewhere in the PDF cannot satisfy a role."""
    if requirements is None:
        return
    scan = role_map(requirements, 'visual_requirements')
    linked = {role: set() for role in ROLES}
    for page, images in zip(pages, page_images):
        roles = page.get('visual_roles', [])
        if (not isinstance(roles, list) or any(not isinstance(r, str) or r not in ROLES for r in roles)
                or len(set(roles)) != len(roles)):
            raise ValueError('visual_rolesはmaterials・tools・guidesの重複のない配列です。')
        for role in roles:
            linked[role].update(images)
    for role, entry in scan.items():
        if entry['status'] == 'visible' and not linked[role].intersection(entry['evidence_files']):
            raise ValueError(f'{role}: 映像で確認した画像を該当ページに掲載し、visual_rolesで対応付けてください。完成写真だけでは代用できません。')


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)


class StepBindings(HTMLParser):
    """Read actual HTML ownership; page metadata alone cannot place a photo."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.blocks = [], []
        self.active = None
        self.unbound_references = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if 'data-step-units' in values:
            ids = (values['data-step-units'] or '').split()
            if tag not in ('section', 'div') or not ids or len(ids) != len(set(ids)):
                raise ValueError('data-step-unitsはsection/divに重複のない工程idを指定してください。')
            if self.active is not None:
                raise ValueError('工程ブロックを入れ子にしないでください。')
            self.active = {'ids': set(ids), 'images': set(), 'references': set(), 'text': [], 'headings': 0}
            self.blocks.append(self.active)
            self.active['depth'] = len(self.stack)
        if self.active is not None:
            if tag in ('h2', 'h3'):
                self.active['headings'] += 1
            if tag == 'img':
                self.active['images'].add(values.get('src', ''))
        if tag == 'span' and 'data-source-unit' in values:
            target = self.active['references'] if self.active is not None else self.unbound_references
            target.add(values['data-source-unit'])
        if tag not in ('img', 'br', 'hr'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in ('img', 'br', 'hr'):
            return
        if self.stack:
            self.stack.pop()
        if self.active is not None and len(self.stack) == self.active['depth']:
            self.active = None

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in ('img', 'br', 'hr'):
            self.handle_endtag(tag)

    def handle_data(self, data):
        if self.active is not None:
            self.active['text'].append(data)


def step_bindings(pages):
    parsers = []
    for page in pages:
        parser = StepBindings()
        parser.feed(page['html'])
        parser.close()
        parsers.append(parser)
    return parsers


def validate_step_bindings(pages, units, records, parsed=None):
    """Cheap structural/time checks; visual interpretation stays with the reviewer."""
    known = {u['id']: u for u in units}
    actions = {i for i, u in known.items() if u['type'] == 'action'}
    times = {r['file']: r['seconds'] for r in records}
    images = {i: set() for i in actions}
    for page, parser in zip(pages, parsed if parsed is not None else step_bindings(pages)):
        if parser.unbound_references & actions:
            raise ValueError('操作の説明と写真をsection data-step-units="工程id"でまとめてください。')
        for block in parser.blocks:
            ids = block['ids']
            if not ids.issubset(known):
                raise ValueError('data-step-unitsに内容案にない工程idがあります。')
            if not ids.issubset(set(page.get('source_units', []))):
                raise ValueError('工程ブロックのidをページのsource_unitsにも指定してください。')
            if block['references'] != ids:
                raise ValueError('工程ブロック内のdata-source-unitとdata-step-unitsを一致させてください。')
            if block['headings'] > 1:
                raise ValueError('異なる工程見出しを同じ工程ブロックに入れないでください。')
            for name in block['images']:
                if name not in times or not any(known[i]['start'] <= times[name] <= known[i]['end'] for i in ids):
                    raise ValueError(f'{" ".join(sorted(ids))}: 工程外の写真 {name} があります。対応する工程ブロックへ移してください。')
            for identity in ids & actions:
                unit = known[identity]
                own = {n for n in block['images'] if unit['start'] <= times[n] <= unit['end']}
                if not own:
                    raise ValueError(f'{identity}: 説明と同じ工程ブロックに対応する写真が必要です。')
                images[identity].update(own)
    for identity in actions:
        required = 2 if known[identity]['risk'] in ('orientation', 'layers', 'fine_motion') else 1
        if len({times[n] for n in images[identity]}) < required:
            raise ValueError(f'{identity}: source_unitsだけでは不十分です。工程ブロック内に操作を示す写真を{required}時刻以上掲載してください。')
    return images


def normalized(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value))


def document_text(document, identity=None):
    if identity is not None:
        parts = [text for parser in step_bindings(document['pages']) for block in parser.blocks
                 if identity in block['ids'] for text in block['text']]
        return normalized(' '.join(parts))
    parser = Text()
    for page in document['pages']:
        parser.feed(page['html'])
    return normalized(' '.join(parser.parts))


def validate_presentation_review(plan, review, records, document=None):
    scan = validate_visual_scan(plan, records)
    checks = role_map(review.get('visual_checks'), 'visual_checks')
    known = {r['file'] for r in records}
    approved = True
    for role, check in checks.items():
        names = files(check, known)
        observed = check.get('observed_status')
        if observed not in VISIBILITY:
            raise ValueError('observed_statusで元映像の材料・道具・位置ガイドの有無を再確認してください。')
        if observed == 'visible' and not names:
            raise ValueError('元映像でvisibleと確認した視覚情報には候補画像が必要です。')
        if check.get('verdict') not in VERDICTS:
            raise ValueError('視覚情報の確認結果を指定してください。')
        if check['verdict'] == 'supported' and scan[role]['status'] == 'visible':
            if not names.intersection(scan[role]['evidence_files']):
                raise ValueError(f'{role}: 確認した掲載候補画像を根拠に含めてください。')
            if observed != 'visible':
                check['verdict'] = 'uncertain'
        if document is not None and observed == 'visible':
            # Catch a guide discovered by the final reviewer even if planning missed it.
            present = any(role in p.get('visual_roles', []) and names.intersection(
                re.findall(r'<img\b[^>]*\bsrc\s*=\s*[\"\']([^\"\']+)', p['html'], re.I)) for p in document['pages'])
            if not present:
                check['verdict'] = 'revise'
        approved &= check['verdict'] == 'supported'
    if document is None:
        return approved
    parsed = step_bindings(document['pages'])
    validate_step_bindings(document['pages'], plan['units'], records, parsed)
    texts = {}
    for parser in parsed:
        for block in parser.blocks:
            for identity in block['ids']:
                texts.setdefault(identity, []).extend(block['text'])
    units = {u['id']: u for u in plan['units']}
    for check in review['unit_checks']:
        if units[check['id']]['type'] != 'action':
            continue
        text = normalized(' '.join(texts.get(check['id'], [])))
        detail = check.get('document_check')
        if not isinstance(detail, dict):
            raise ValueError(f"{check['id']}: document_checkで本文の操作指示・終了状態・写真を確認してください。")
        for field in ('reproducibility', 'image_usefulness'):
            if detail.get(field) not in VERDICTS:
                raise ValueError('本文の再現性と写真の有用性を個別に判定してください。')
        for field in ('instruction_excerpt', 'completion_excerpt'):
            quote = detail.get(field)
            if not isinstance(quote, str) or len(quote) > 500:
                raise ValueError('操作指示と終了状態の引用は500文字以内の文字列です。')
            if quote.strip() and normalized(quote) not in text:
                raise ValueError('引用した操作指示・終了状態がHTML本文にありません。内容案から補わないでください。')
        # Incomplete text cannot pass even when the overall verdict says supported.
        usable = (detail['reproducibility'] == 'supported'
                  and bool(detail['instruction_excerpt'].strip()) and bool(detail['completion_excerpt'].strip()))
        if not usable or detail['image_usefulness'] != 'supported':
            check['verdict'] = ('uncertain' if check['verdict'] != 'revise'
                                and 'uncertain' in (detail['reproducibility'], detail['image_usefulness']) else 'revise')
            approved = False
    return approved
