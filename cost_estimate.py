"""Pre-run cost estimate from what will actually be sent (no AI call).

Users cannot know in advance what a video will cost, so the run sets its own
safety ceiling from this estimate instead of asking for a dollar amount.
Output sizes come from measured runs (2026-11-06, Opus 5.5, detailed editorial
seminar, 14 pages): document submissions used 31.5k-36.5k output tokens and the
first editor input was 39.4k tokens. Analysis-stage outputs are not yet measured
and use conservative values below the provider cap.

Recalibrated 2026-11-10 on three Opus 5.5 runs (seminar/detailed, training/standard x2):
in the editor conversation every earlier reply is sent again, and each resent reply
was billed at about 2.1-2.2x its original output tokens (fit over 10 round-to-round
steps, error about 5k tokens). Page images were billed at about 1.4x width*height/750.
A content check is two calls (a look at frames, then the review), not one.
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
IMAGE_FACTOR = 1.4              # measured billing of page/frame images vs width*height/750
IMAGE_TOKEN_CAP = 4784          # high-resolution models (Opus 4.7 and later)
RESEND_FACTOR = 2.2             # a reply sent back in the history, per output token it had

DOCUMENT_OUTPUT = {'compact': 15000, 'standard': 24000, 'detailed': 34000}
PLAN_OUTPUT = {'compact': 10000, 'standard': 16000, 'detailed': 22000}
REVIEW_LOOK_OUTPUT = 4500       # first call of a content check (measured 1.3k-4.5k)
REVIEW_LOOK_GROWTH = 15000      # frames it asked for, added to the second call (measured 6k-18k)
REVIEW_OUTPUT = 6500            # the review itself (measured 3.9k-4.8k)
APPROVE_OUTPUT = 5000
INSPECT_OUTPUT = 500
INSPECT_GROWTH = 13000          # input added by one inspection round (measured 12k-15k)
TOKENS_PER_PREVIEW_PAGE = 2000  # page previews (and crops) returned after a submission, billed
FEEDBACK_TOKENS = 5000          # layout/design/content findings returned with the previews
OUTPUT_TOKENS_PER_PAGE = 2500   # 34k output tokens produced about 14 pages
FIX_SHARE = 0.6                 # share of a full submission resent by one page-level fix
# DOCUMENT_OUTPUT still includes the Markdown the editor used to write (about a
# quarter of a submission); kept until new runs are measured, so estimates stay on the safe side.

CEILING_FACTOR = 1.3
DEFAULT_MAX_RUN_USD = 10.0
DEFAULT_CONFIRM_USD = 5.0


def count_tokens(messages, tools=(), system=''):
    """Approximate provider input tokens (planning estimate, not a billing tokenizer).

    Earlier assistant replies are weighted by RESEND_FACTOR: sent back in the history
    they were billed at about twice their text size (reasoning included)."""
    image_tokens = 0

    def text_tokens(texts):
        text = ''.join(texts)
        ascii_count = sum(ch.isascii() for ch in text)
        return ascii_count / ASCII_CHARS_PER_TOKEN + (len(text) - ascii_count) * OTHER_TOKENS_PER_CHAR

    def walk(value, texts):
        nonlocal image_tokens
        if isinstance(value, dict):
            if value.get('type') == 'image' and isinstance(value.get('source'), dict):
                with Image.open(io.BytesIO(base64.b64decode(value['source']['data']))) as picture:
                    image_tokens += min(IMAGE_TOKEN_CAP, math.ceil(
                        picture.width * picture.height / IMAGE_PIXELS_PER_TOKEN * IMAGE_FACTOR))
                return
            for item in value.values():
                walk(item, texts)
        elif isinstance(value, list):
            for item in value:
                walk(item, texts)
        elif isinstance(value, str):
            texts.append(value)
        elif value is not None:
            texts.append(json.dumps(value, ensure_ascii=False))

    plain, replies = [], []
    for message in (messages if isinstance(messages, list) else [messages]):
        is_reply = isinstance(message, dict) and message.get('role') == 'assistant'
        walk(message, replies if is_reply else plain)
    walk(list(tools), plain)
    plain.append(system or '')
    return math.ceil(text_tokens(plain) + text_tokens(replies) * RESEND_FACTOR) + image_tokens


def limits():
    """Operator-side limits; users are never asked for a dollar amount."""
    def number(name, default):
        try:
            value = float(os.getenv(name, default))
        except ValueError:
            return default
        return value if math.isfinite(value) and value > 0 else default
    return number('VIDEO_PDF_MAX_RUN_USD', DEFAULT_MAX_RUN_USD), number('VIDEO_PDF_CONFIRM_USD', DEFAULT_CONFIRM_USD)


def session_cost(calls, rates, ttl=None, read_multiplier=0.1, prefix=0):
    """Cost of one conversation's calls, in order. With caching, the stable prefix is
    written once (first call) and read back by later calls; the rest is full price."""
    from prompt_cache import WRITE_MULTIPLIER
    rate_in, rate_out = rates
    total = 0.0
    for index, (tokens_in, tokens_out) in enumerate(calls):
        cached = min(prefix, tokens_in) if ttl else 0
        factor = (WRITE_MULTIPLIER[ttl] if index == 0 else read_multiplier) if ttl else 1.0
        total += cached * rate_in * factor + (tokens_in - cached) * rate_in + tokens_out * rate_out
    return total


def estimate_run(*, analysis_input, editor_input, plan_tokens, plan_ready, detail_level, editorial, rates,
                 spent=0.0, model='', cache=True):
    """Return low/high cost of the remaining work and the run's automatic ceiling.

    low: no extra inspection, one submission, one content check, approval.
    high: two inspections in each stage, a rejected first submission sent again in
    full, one page-level fix and two content checks (what the measured runs did).
    Each reply stays in the conversation and is billed again on every later call."""
    from prompt_cache import TTL_BY_PHASE, read_multiplier
    detail = detail_level if detail_level in DOCUMENT_OUTPUT else 'standard'
    plan_out = PLAN_OUTPUT[detail]
    document_out = round(DOCUMENT_OUTPUT[detail] * (1.0 if editorial else 0.8))
    returned = max(3, round(document_out / OUTPUT_TOKENS_PER_PAGE)) * TOKENS_PER_PREVIEW_PAGE + FEEDBACK_TOKENS
    plan = plan_tokens if plan_ready else plan_out
    a, b, g, d = analysis_input, editor_input, INSPECT_GROWTH, document_out

    def conversation(start, steps):
        """(input, output) per call; each step's reply and tool result join the history."""
        calls, history = [], start
        for output, result in steps:
            calls.append((history, output))
            history += round(output * RESEND_FACTOR) + result
        return calls

    def check():
        review_in = analysis_input + plan + d
        return [(review_in, REVIEW_LOOK_OUTPUT), (review_in + REVIEW_LOOK_GROWTH, REVIEW_OUTPUT)]

    inspect = (INSPECT_OUTPUT, g)
    plan_calls = {'low': [] if plan_ready else conversation(a, [(plan_out, 0)]),
                  'high': [] if plan_ready else conversation(a, [inspect, inspect, (plan_out, 0)])}
    editor_calls = {'low': conversation(b, [inspect, (d, returned), (APPROVE_OUTPUT, 0)]),
                    # A fix resends only the changed pages (revise_pages); assume up to 60% of the document.
                    'high': conversation(b, [inspect, inspect, (d, returned), (d, returned),
                                             (round(d * FIX_SHARE), returned), (APPROVE_OUTPUT, 0)])}
    review_calls = {'low': [check()], 'high': [check(), check()]}
    reads = read_multiplier(model)
    ttl = (lambda phase: TTL_BY_PHASE.get(phase)) if cache else (lambda phase: None)
    total = lambda case: (session_cost(plan_calls[case], rates, ttl('content_plan'), reads, prefix=a)
                          + session_cost(editor_calls[case], rates, ttl('document_edit'), reads, prefix=b)
                          + sum(session_cost(calls, rates, ttl('content_review'), reads, prefix=calls[0][0])
                                for calls in review_calls[case]))
    max_run, confirm = limits()
    low_usd, high_usd = total('low'), total('high')
    ceiling = min(max_run, spent + max(0.5, high_usd * CEILING_FACTOR))
    return {'low_usd': round(low_usd, 2), 'high_usd': round(high_usd, 2), 'ceiling_usd': round(ceiling, 2),
            'confirm_above_usd': confirm, 'needs_confirmation': high_usd > confirm,
            'exceeds_max': spent + high_usd > max_run, 'spent_usd': round(spent, 3),
            'expected_output': {'content_plan': plan_out, 'content_review': max(REVIEW_OUTPUT, REVIEW_LOOK_OUTPUT),
                                'document_edit': round(d * 1.2)},
            'basis': {'analysis_input_tokens': analysis_input, 'editor_input_tokens': editor_input,
                      'plan_ready': plan_ready, 'detail_level': detail, 'editorial': editorial, 'prompt_cache': cache}}
