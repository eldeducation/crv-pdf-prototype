"""Prompt caching for the stable request prefix (same content, lower input price).

Every turn of a stage resends the same system prompt, content plan and video
images. Caching lets the provider read that prefix back at a fraction of the
input price. The content sent to the model is unchanged, so output is unaffected.

Only the stable prefix is marked (system prompt + end of the first user message),
with explicit content markers, so no new request parameter is needed. The growing
tail is deliberately not cached: on measured runs, newly written pages and previews
are read back too few times to repay the cache-write premium (prefix only: -9% to
-15% on the document stage; prefix + tail: -12% to +5%).

TTL by stage: the document stage needs 1 hour because one page-writing response
can run 4-9 minutes and a cache entry's lifetime is measured from the start of
each request; the analysis stage uses 5 minutes (its turns follow each other
quickly); the one-off content check is not cached (a write never read is a surcharge).
"""
import copy

TTL_BY_PHASE = {'document_edit': '1h', 'content_plan': '5m'}

# Cache read price relative to base input, by model (Claude docs, 2026-10); others 0.1.
READ_MULTIPLIER = {'claude-fable-5-1': 0.025, 'claude-mythos-5-1': 0.025, 'claude-opus-5-5': 0.05}
WRITE_MULTIPLIER = {'5m': 1.25, '1h': 2.0}


def cache_control(ttl):
    return {'type': 'ephemeral', 'ttl': '1h'} if ttl == '1h' else {'type': 'ephemeral'}


def read_multiplier(model):
    name = str(model).split('/')[-1].replace('.', '-')
    return next((v for k, v in READ_MULTIPLIER.items() if name.startswith(k)), 0.1)


def _mark(content, marker, text_only=False):
    """Content list with the marker on its last block (or last text part)."""
    if isinstance(content, str):
        return [{'type': 'text', 'text': content, 'cache_control': marker}]
    parts = list(content or [])
    for index in range(len(parts) - 1, -1, -1):
        if not text_only or parts[index].get('type') == 'text':
            parts[index] = {**parts[index], 'cache_control': marker}
            break
    return parts


def anthropic_request(payload, ttl):
    """Messages API payload with markers on the system prompt and the first user message."""
    if not ttl:
        return payload
    marker = cache_control(ttl)
    payload = dict(payload)
    if isinstance(payload.get('system'), str) and payload['system']:
        payload['system'] = [{'type': 'text', 'text': payload['system'], 'cache_control': marker}]
    messages = list(payload.get('messages') or [])
    if messages and messages[0].get('role') == 'user':
        messages[0] = {**copy.copy(messages[0]), 'content': _mark(messages[0]['content'], marker)}
    payload['messages'] = messages
    return payload


def openrouter_request(payload, ttl):
    """OpenRouter chat payload (already converted): markers on the system message and on the
    last text part of the first user message."""
    if not ttl:
        return payload
    marker = cache_control(ttl)
    payload = dict(payload)
    messages = [dict(m) for m in payload.get('messages') or []]
    for message in messages:
        if message.get('role') == 'system' and isinstance(message.get('content'), str):
            message['content'] = [{'type': 'text', 'text': message['content'], 'cache_control': marker}]
            break
    for message in messages:
        if message.get('role') == 'user':
            message['content'] = _mark(message['content'], marker, text_only=True)
            break
    payload['messages'] = messages
    return payload


def call_cost(usage, rates, model):
    """USD for one Anthropic-format usage record (input_tokens = uncached remainder)."""
    rate_in, rate_out = rates
    detail = usage.get('cache_creation') or {}
    write_1h = detail.get('ephemeral_1h_input_tokens', 0) or 0
    write_5m = detail.get('ephemeral_5m_input_tokens', (usage.get('cache_creation_input_tokens', 0) or 0) - write_1h) or 0
    return (usage.get('input_tokens', 0) * rate_in
            + write_5m * rate_in * WRITE_MULTIPLIER['5m'] + write_1h * rate_in * WRITE_MULTIPLIER['1h']
            + (usage.get('cache_read_input_tokens', 0) or 0) * rate_in * read_multiplier(model)
            + usage.get('output_tokens', 0) * rate_out)
