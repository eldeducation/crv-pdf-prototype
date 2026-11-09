"""Editable Markdown generated from the submitted page HTML.

The editor used to write the whole document twice (pages and Markdown), which
took about a third of every submission and let the two drift apart. The PDF is
rendered from the pages only, so generating Markdown from those same pages
keeps it identical in content without changing the PDF.
"""
import re
from html.parser import HTMLParser

BREAK = ' '   # placeholder for <br> until the line is written

HEADINGS = {'h1': '# ', 'h2': '## ', 'h3': '### ', 'h4': '#### ', 'h5': '#### ', 'h6': '#### '}
BLOCKS = {'p', 'div', 'section', 'article', 'header', 'footer', 'main', 'aside', 'figure', 'figcaption',
          'blockquote', 'ul', 'ol', 'li', 'table', 'tr', 'dl', 'dt', 'dd', 'hr', *HEADINGS}
SAFE_LINK = re.compile(r'^https://[^\s"<>]+$')


def _inline_marker(tag):
    return {'strong': '**', 'b': '**', 'mark': '**', 'em': '*', 'i': '*', 'code': '`'}.get(tag)


class _Converter(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.text = [], ''
        self.prefix = ''            # heading / list / quote prefix for the current block
        self.lists, self.quote = [], 0
        self.skip = 0               # inside svg/style/script
        self.table, self.row, self.cell = None, None, None
        self.links = []
        self.label_open = False
        # Kit components (Q&A, tiles, POINT, summary label, big quote) read better in
        # Markdown with their own forms than as generic blocks.
        self.kit_stack = []         # (tag, classes, end action) of open elements
        self.skip_text = 0          # decorative labels/arrows whose text is dropped
        self.capture = None         # text of a label that becomes the next block's lead
        self.pending_lead = ''

    def inside(self, name):
        return any(name in classes for _, classes, _ in self.kit_stack)

    def kit_start(self, tag, classes):
        """Handle kit classes; returns the action to run when the element ends."""
        if 'arrow' in classes or (tag == 'small' and (self.inside('q') or self.inside('a'))):
            self.skip_text += 1
            return 'unskip'
        if ('label' in classes and self.inside('tldr')) or ('tag' in classes and self.inside('point')):
            self.blank()
            self.capture = []
            return 'lead'
        if 'q' in classes and self.inside('qa'):
            self.blank()
            self.pending_lead = '**Q.** '
        elif 'a' in classes and self.inside('qa'):
            self.blank()
            self.pending_lead = '**A.** '
        elif 'num' in classes:
            self.text += '**'
            return 'bold'
        elif 'label' in classes and self.inside('bigstat'):
            self.text += ' '
        elif 'quote-xl' in classes:
            self.blank()
            self.quote += 1
            return 'unquote'
        return None

    def kit_end(self, action):
        if action == 'unskip':
            self.skip_text = max(0, self.skip_text - 1)
        elif action == 'lead':
            label = re.sub(r'\s+', ' ', ''.join(self.capture or [])).strip()
            self.capture = None
            self.pending_lead = f'**{label}：** ' if label else ''
        elif action == 'bold':
            self.text += '**'
        elif action == 'unquote':
            self.flush()
            while self.lines and self.lines[-1] == '>':
                self.lines.pop()
            self.quote = max(0, self.quote - 1)
            self.lines.append('')

    # ---- block helpers -------------------------------------------------
    def flush(self):
        text = re.sub(r'[ \t\r\n]+', ' ', self.text).strip()
        text = re.sub(r'\*\*\s*\*\*', '', text)
        # <br> is kept as a Markdown hard break (whitespace collapsing above would turn it into a space).
        text = re.sub(r'\s*' + BREAK + r'\s*', '  \n', text).strip()
        if text:
            if self.pending_lead:
                text, self.pending_lead = self.pending_lead + text, ''
            quote = '> ' * self.quote
            self.lines.append(quote + self.prefix + text)
            self.prefix = ''
        # With no text yet, keep the prefix: '<li><p>…' must still become '- …'.
        self.text = ''

    def end_block(self, blank=True):
        self.blank() if blank else self.flush()
        self.prefix = ''

    def blank(self):
        self.flush()
        # Inside a quote the separator keeps the '>' so paragraphs stay in one quote.
        separator = '>' if self.quote else ''
        if self.lines and self.lines[-1] not in ('', '>'):
            self.lines.append(separator)

    # ---- parser events -------------------------------------------------
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'svg', 'style', 'script'}:
            self.skip += 1
            return
        if self.skip:
            return
        if self.cell is not None:
            if tag == 'br':
                self.cell.append(' ')
            elif tag == 'img':
                self.cell.append(f'![{attrs.get("alt", "")}]({attrs.get("src", "")})')
            return
        if tag == 'table':
            self.blank()
            self.table = []
            return
        if self.table is not None:
            if tag == 'tr':
                self.row = []
            elif tag in {'td', 'th'}:
                self.cell = []
            return
        if tag == 'br' and self.inside('tiles'):
            self.text += ' '         # "3<br>試した版の数" reads as "**3** 試した版の数"
            return
        if tag not in {'img', 'br', 'hr'}:
            classes = set((attrs.get('class') or '').split())
            action = self.kit_start(tag, classes)
            self.kit_stack.append((tag, classes, action))
            if action in {'lead', 'unquote'}:
                return
        if tag in HEADINGS:
            self.blank()
            self.prefix = HEADINGS[tag]
        elif tag in {'ul', 'ol'}:
            self.flush()
            self.lists.append([tag, 0])
        elif tag == 'li':
            self.flush()
            depth = max(0, len(self.lists) - 1)
            kind = self.lists[-1] if self.lists else ['ul', 0]
            kind[1] += 1
            self.prefix = '  ' * depth + (f'{kind[1]}. ' if kind[0] == 'ol' else '- ')
        elif tag == 'blockquote':
            self.blank()
            self.quote += 1
        elif tag == 'hr':
            self.blank()
            self.lines.extend(['---', ''])
        elif tag == 'br':
            self.text += BREAK
        elif tag == 'img':
            self.blank()
            alt = (attrs.get('alt') or '').replace(']', '').replace('<', '&lt;').replace('>', '&gt;')
            self.lines.extend([f'![{alt}]({attrs.get("src", "")})', ''])
        elif tag == 'a':
            href = attrs.get('href', '')
            self.links.append(href if SAFE_LINK.match(href or '') else None)
            if self.links[-1]:
                self.text += '['
        elif tag == 'small':
            self.text += ' '
        elif tag in BLOCKS:
            # Separate blocks by a blank line: Markdown joins consecutive lines into one paragraph.
            self.blank() if tag not in {'dt', 'dd'} else self.flush()
            if tag == 'figcaption':
                self.text += '*'
        elif _inline_marker(tag):
            # A bold label opening a block ("<b>v1</b>説明") gets a space after it.
            self.label_open = _inline_marker(tag) == '**' and not self.text.strip()
            self.text += _inline_marker(tag)

    def handle_endtag(self, tag):
        if tag in {'svg', 'style', 'script'}:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if self.table is not None:
            if tag in {'td', 'th'} and self.cell is not None and self.row is not None:
                self.row.append(re.sub(r'\s+', ' ', ''.join(self.cell)).strip().replace('|', '\\|'))
                self.cell = None
            elif tag == 'tr' and self.row is not None:
                if self.row:
                    self.table.append(self.row)
                self.row = None
            elif tag == 'table':
                self.emit_table()
            return
        if tag in HEADINGS or tag in {'li', 'p', 'figure', 'section', 'dt', 'dd'}:
            self.end_block(blank=tag not in {'li', 'dt', 'dd'})
        elif tag == 'figcaption':
            # Italic caption; bold inside it ("**07:06**") would nest markers, so drop it.
            self.text = '*' + self.text.lstrip('*').replace('**', '').strip() + '*'
            self.end_block()
        elif tag in {'ul', 'ol'}:
            if self.lists:
                self.lists.pop()
            if not self.lists:
                self.blank()
        elif tag == 'blockquote':
            self.flush()
            self.quote = max(0, self.quote - 1)
            self.blank()
        elif tag == 'a':
            href = self.links.pop() if self.links else None
            if href:
                self.text += f']({href})'
        elif tag in BLOCKS:
            self.end_block()
        elif _inline_marker(tag):
            self.text += _inline_marker(tag)
            if self.label_open and _inline_marker(tag) == '**':
                self.text += ' '
            self.label_open = False
        # Kit actions run after the generic end, so a quote's last line keeps its '> '.
        for index in range(len(self.kit_stack) - 1, -1, -1):
            if self.kit_stack[index][0] == tag:
                action = self.kit_stack.pop(index)[2]
                if action:
                    self.kit_end(action)
                break

    def handle_data(self, data):
        if self.skip:
            return
        if self.capture is not None:
            self.capture.append(data)
            return
        if self.skip_text:
            return
        # Text such as "<final_verdict>" (written &lt;…&gt; in the page) must stay visible:
        # raw angle brackets would be read as an HTML tag and hidden by Markdown viewers.
        data = data.replace('<', '&lt;').replace('>', '&gt;')
        if self.cell is not None:
            self.cell.append(data)
        elif self.table is None:
            self.text += data

    def emit_table(self):
        rows, self.table = self.table or [], None
        if rows:
            width = max(len(r) for r in rows)
            rows = [r + [''] * (width - len(r)) for r in rows]
            self.lines.append('| ' + ' | '.join(rows[0]) + ' |')
            self.lines.append('|' + '---|' * width)
            self.lines.extend('| ' + ' | '.join(r) + ' |' for r in rows[1:])
            self.lines.append('')

    def result(self):
        self.flush()
        text = '\n'.join(self.lines)
        text = re.sub(r'\n{3,}', '\n\n', text)
        # The parser already decoded character references; decoding again would turn the
        # escaped &lt;…&gt; back into raw tags.
        return text.strip() + '\n'


NUMBER_LABEL = re.compile(r'^(?:\d{1,2}|PART\s*\d+|第\d+章)$', re.I)
TIME_LABEL = re.compile(r'^(?:PART\s*\d+\s*)?[\d:：〜~–\-／/ 　]+$', re.I)
LEAD_LABEL = re.compile(r'^\*\*[^*]+[：.]\*\* ')
BOLD_TITLE = re.compile(r'^\*\*[^*]+\*\*\s*(?:（[^）]*）)?$')  # a bold-only line works as a small heading
PLAIN_LINE = re.compile(r'^(?![#!>|-]|\*(?!\*)|\d+\. |---)')  # bold-led lines count; captions (*...*) do not


def _tidy(text):
    """Fold chapter numbers/times into the heading and turn runs of short blocks into lists."""
    blocks = [b.strip() for b in text.split('\n\n') if b.strip()]
    merged = []
    for block in blocks:
        if block.startswith('## ') or block.startswith('### '):
            number = time = None
            while merged and '\n' not in merged[-1] and len(merged[-1]) <= 30:
                label = merged[-1].strip()
                if time is None and TIME_LABEL.match(label) and re.search(r'\d:\d', label):
                    time = merged.pop()
                elif number is None and NUMBER_LABEL.match(label):
                    number = merged.pop()
                else:
                    break
            level, title = block.split(' ', 1)
            block = level + ' ' + (number + ' ' if number else '') + title + (f'（{time.strip()}）' if time else '')
        merged.append(block)
    # Three or more short single-line blocks in a row are grid/flow items: a list.
    out, run = [], []
    def close_run():
        if len(run) >= 3:
            out.append('\n'.join('- ' + item for item in run))
        else:
            out.extend(run)
        run.clear()
    def list_item(block):
        # Grid/flow items: a bold-led label line, or a short phrase that is not a sentence.
        if '\n' in block or len(block) > 90 or not PLAIN_LINE.match(block) or BOLD_TITLE.match(block):
            return False
        if LEAD_LABEL.match(block):      # "**POINT：** …", "**Q.** …" are their own paragraphs
            return False
        return block.startswith('**') or (len(block) <= 40 and not block.rstrip().endswith('。'))
    for block in merged:
        if list_item(block):
            run.append(block)
        else:
            close_run()
            out.append(block)
    close_run()
    return '\n\n'.join(out) + '\n'


def page_markdown(markup):
    converter = _Converter()
    converter.feed(markup)
    converter.close()
    return _tidy(converter.result())


def document_markdown(document):
    """Markdown for the whole document, in page order, from the pages actually rendered."""
    parts = [page_markdown(page['html']) for page in document.get('pages', [])]
    body = '\n---\n\n'.join(part for part in parts if part.strip())
    if not re.search(r'^# ', body, re.M):
        body = '# ' + str(document.get('title', '')).strip() + '\n\n' + body
    return body
