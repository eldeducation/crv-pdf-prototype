"""Pre-run cost estimate from what will actually be sent (no AI call).

Users cannot know in advance what a video will cost, so the run sets its own
safety ceiling from this estimate instead of asking for a dollar amount.
Output sizes come from measured runs (2026-11-06, Opus 5.5, detailed editorial
seminar, 14 pages): document submissions used 31.5k-36.5k output tokens and the
first editor input was 39.4k tokens. Analysis-stage outputs are not yet measured
and use conservative values below the provider cap.
"""
import base64
import io
import json
import math
import os

from PIL import Image

ASCII_CHARS_PER_TOKEN = 3.0
OTHER_TOKENS_PER_CHAR = 1.1
IMAGE_PIXELS_PER_TOKEN = 750
IMAGE_TOKEN_CAP = 1600

DOCUMENT_OUTPUT = {'compact': 15000, 'standard': 24000, 'detailed': 34000}
PLAN_OUTPUT = {'compact': 10000, 'standard': 16000, 'detailed': 22000}
REVIEW_OUTPUT = 8000
APPROVE_OUTPUT = 5000
INSPECT_OUTPUT = 500
INSPECT_GROWTH = 13000          # input added by one inspection round (measured 12k-15k)
TOKENS_PER_PREVIEW_PAGE = 1500  # page previews returned after each submission
OUTPUT_TOKENS_PER_PAGE = 2500   # 34k output tokens produced about 14 pages

CEILING_FACTOR = 1.3
DEFAULT_MAX_RUN_USD = 10.0
DEFAULT_CONFIRM_USD = 5.0


def count_tokens(messages, tools=(), system=''):
    """Approximate provider input tokens; within a few percent on the measured run."""
    texts, image_tokens = [], 0

    def walk(value):
        nonlocal image_tokens
        if isinstance(value, dict):
            if value.get('type') == 'image' and isinstance(value.get('source'), dict):
                with Image.open(io.BytesIO(base64.b64decode(value['source']['data']))) as picture:
                    image_tokens += min(IMAGE_TOKEN_CAP, math.ceil(picture.width * picture.height / IMAGE_PIXELS_PER_TOKEN))
                return
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            texts.append(value)
        elif value is not None:
            texts.append(json.dumps(value, ensure_ascii=False))

    walk(messages)
    walk(list(tools))
    texts.append(system or '')
    text = ''.join(texts)
    ascii_count = sum(ch.isascii() for ch in text)
    return math.ceil(ascii_count / ASCII_CHARS_PER_TOKEN + (len(text) - ascii_count) * OTHER_TOKENS_PER_CHAR) + image_tokens


def limits():
    """Operator-side limits; users are never asked for a dollar amount."""
    def number(name, default):
        try:
            value = float(os.getenv(name, default))
        except ValueError:
            return default
        return value if math.isfinite(value) and value > 0 else default
    return number('VIDEO_PDF_MAX_RUN_USD', DEFAULT_MAX_RUN_USD), number('VIDEO_PDF_CONFIRM_USD', DEFAULT_CONFIRM_USD)


def estimate_run(*, analysis_input, editor_input, plan_tokens, plan_ready, detail_level, editorial, rates, spent=0.0):
    """Return low/high cost of the remaining work and the run's automatic ceiling.

    low: no extra inspection, one submission, one content check, approval.
    high: two inspections in each stage, one full fix, two content checks."""
    detail = detail_level if detail_level in DOCUMENT_OUTPUT else 'standard'
    rate_in, rate_out = rates
    cost = lambda calls: sum(i * rate_in + o * rate_out for i, o in calls)
    plan_out = PLAN_OUTPUT[detail]
    document_out = round(DOCUMENT_OUTPUT[detail] * (1.0 if editorial else 0.8))
    previews = max(3, round(document_out / OUTPUT_TOKENS_PER_PAGE)) * TOKENS_PER_PREVIEW_PAGE
    plan = plan_tokens if plan_ready else plan_out
    low, high = [], []
    if not plan_ready:
        a = analysis_input
        low += [(a, plan_out)]
        high += [(a, INSPECT_OUTPUT), (a + INSPECT_GROWTH, INSPECT_OUTPUT), (a + 2 * INSPECT_GROWTH, plan_out)]
    b, g, d = editor_input, INSPECT_GROWTH, document_out
    review_in = analysis_input + plan + d
    low += [(b, INSPECT_OUTPUT), (b + g, d), (review_in, REVIEW_OUTPUT), (b + g + d + previews, APPROVE_OUTPUT)]
    high += [(b, INSPECT_OUTPUT), (b + g, INSPECT_OUTPUT), (b + 2 * g, d),
             (b + 2 * g + d + previews, round(d * 1.1)), (review_in, REVIEW_OUTPUT), (review_in, REVIEW_OUTPUT),
             (b + 2 * g + 2 * d + 2 * previews, APPROVE_OUTPUT)]
    max_run, confirm = limits()
    low_usd, high_usd = cost(low), cost(high)
    ceiling = min(max_run, spent + max(0.5, high_usd * CEILING_FACTOR))
    return {'low_usd': round(low_usd, 2), 'high_usd': round(high_usd, 2), 'ceiling_usd': round(ceiling, 2),
            'confirm_above_usd': confirm, 'needs_confirmation': high_usd > confirm,
            'exceeds_max': spent + high_usd > max_run, 'spent_usd': round(spent, 3),
            'expected_output': {'content_plan': plan_out, 'content_review': REVIEW_OUTPUT,
                                'document_edit': round(d * 1.2)},
            'basis': {'analysis_input_tokens': analysis_input, 'editor_input_tokens': editor_input,
                      'plan_ready': plan_ready, 'detail_level': detail, 'editorial': editorial}}
