"""Read-only provider catalogues. No inference, credentials on disk, or redirects."""
from __future__ import annotations
import json
import time
import urllib.error
import urllib.parse
import urllib.request

MAX_BYTES = 12_000_000
MAX_MODELS = 10000
TIMEOUT = 12
EFFORTS = ('low', 'medium', 'high', 'xhigh', 'max')


class CatalogError(Exception):
    def __init__(self, code, status=502):
        self.code, self.status = code, status
        super().__init__('Model catalogue: ' + code)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CatalogError('redirect')


def read_catalog(url, key, provider, timeout):
    destination = urllib.parse.urlsplit(url)
    expected = {'openrouter': 'openrouter.ai', 'anthropic': 'api.anthropic.com'}.get(provider)
    if not expected or destination.scheme != 'https' or destination.hostname != expected or destination.port not in (None, 443) or destination.username or destination.password:
        raise CatalogError('destination', 400)
    headers = {'Accept': 'application/json', 'Authorization': 'Bearer ' + key}
    if provider == 'anthropic':
        headers['anthropic-version'] = '2026-10-21'
    request = urllib.request.Request(url, headers=headers, method='GET')
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise CatalogError('too_large')
        result = json.loads(raw)
        if not isinstance(result, dict) or not isinstance(result.get('data'), list):
            raise CatalogError('invalid_response')
        return result
    except urllib.error.HTTPError as error:
        code = {401: 'authentication', 402: 'credits', 403: 'access', 429: 'rate_limit'}.get(error.code, 'provider_error')
        raise CatalogError(code, 400 if error.code in (401, 402, 403) else 502) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CatalogError('network') from None
    except (ValueError, UnicodeError):
        raise CatalogError('invalid_response') from None


def positive(value):
    return value if type(value) is int and value > 0 else None


def normalize(item, provider):
    if not isinstance(item, dict):
        raise CatalogError('invalid_response')
    model_id = item.get('id')
    if not isinstance(model_id, str) or not model_id or len(model_id) > 250 or any(ord(c) < 32 for c in model_id):
        raise CatalogError('invalid_response')
    reasons, unknown = [], False
    result = {'id': model_id, 'name': str(item.get('name') or item.get('display_name') or model_id)[:250]}
    if provider == 'openrouter':
        arch = item.get('architecture') or {}
        if not isinstance(arch, dict) or not isinstance(item.get('top_provider') or {}, dict):
            raise CatalogError('invalid_response')
        params = item.get('supported_parameters')
        for field, required, reason in (('input_modalities', 'image', 'no_image'), ('output_modalities', 'text', 'no_text')):
            values = arch.get(field)
            if not isinstance(values, list):
                unknown = True
            elif required not in values:
                reasons.append(reason)
        if not isinstance(params, list):
            unknown = True
        elif 'tools' not in params:
            reasons.append('no_tools')
        result.update(reasoning=None if not isinstance(params, list) else 'reasoning' in params,
                      max_output_tokens=positive((item.get('top_provider') or {}).get('max_completion_tokens')),
                      context_tokens=positive(item.get('context_length')))
        # The existing spending guard cannot estimate these additional fees.
        pricing = item.get('pricing') or {}
        if isinstance(pricing, dict):
            try:
                if float(pricing.get('image') or 0) or float(pricing.get('request') or 0):
                    reasons.append('extra_pricing')
            except (ValueError, TypeError, OverflowError):
                unknown = True
    else:
        caps = item.get('capabilities') or {}
        image = (caps.get('image_input') or {}).get('supported')
        if image is False:
            reasons.append('no_image')
        elif image is not True:
            unknown = True
        thinking = caps.get('thinking') or {}
        adaptive = ((thinking.get('types') or {}).get('adaptive') or {}).get('supported')
        enabled = ((thinking.get('types') or {}).get('enabled') or {}).get('supported')
        effort = caps.get('effort') or {}
        result.update(reasoning=thinking.get('supported'), adaptive=adaptive, thinking_enabled=enabled,
                      efforts=[e for e in EFFORTS if (effort.get(e) or {}).get('supported') is True],
                      max_output_tokens=positive(item.get('max_tokens')), context_tokens=positive(item.get('max_input_tokens')))
        if item.get('lifecycle') == 'retired':
            reasons.append('retired')
    result.update(compatibility='unsupported' if reasons else 'unknown' if unknown else 'supported', reasons=reasons)
    return result


def fetch_models(key, provider):
    if provider not in ('openrouter', 'anthropic'):
        raise CatalogError('provider', 400)
    # Provider preferences, privacy and guardrails are applied by OpenRouter.
    base = 'https://openrouter.ai/api/v1/models/user?output_modalities=all' if provider == 'openrouter' else 'https://api.anthropic.com/v1/models?limit=1000'
    deadline, cursor, seen, models = time.monotonic() + 25, None, set(), {}
    for _ in range(10):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CatalogError('network')
        url = base + ('&after_id=' + urllib.parse.quote(cursor, safe='') if cursor else '')
        page = read_catalog(url, key, provider, min(TIMEOUT, remaining))
        for item in page['data']:
            model = normalize(item, provider)
            models[model['id']] = model
        if len(models) > MAX_MODELS:
            raise CatalogError('too_large')
        if provider == 'openrouter' or not page.get('has_more'):
            return {'provider': provider, 'models': sorted(models.values(), key=lambda m: (m['name'].casefold(), m['id'])),
                    'fetched_at': time.time(), 'source': 'user_catalog' if provider == 'openrouter' else 'models_api'}
        cursor = page.get('last_id')
        if not isinstance(cursor, str) or not cursor or cursor in seen:
            raise CatalogError('invalid_response')
        seen.add(cursor)
    # Never silently return a partial list.
    raise CatalogError('too_large')


def apply_model_options(payload, options, provider, effort):
    """Respect explicit provider capabilities without changing the default path."""
    if not options:
        return
    limit = positive(options.get('max_output_tokens'))
    if limit:
        payload['max_tokens'] = min(payload['max_tokens'], limit)
    if provider == 'openrouter':
        if options.get('reasoning') is False:
            payload.pop('reasoning', None)
        return
    efforts = options.get('efforts') or []
    if options.get('adaptive') is False:
        payload.pop('thinking', None)
        if options.get('thinking_enabled') is True:
            budget = {'low': 1024, 'medium': 4096, 'high': 8192, 'xhigh': 16384, 'max': 24576}.get(effort, 8192)
            budget = min(budget, payload['max_tokens'] - 1024)
            if budget >= 1024:
                payload['thinking'] = {'type': 'enabled', 'budget_tokens': budget}
    if options.get('reasoning') is False:
        payload.pop('thinking', None)
    if not efforts:
        payload.pop('output_config', None)
    elif effort not in efforts:
        raise ValueError('選択したモデルでは、この推論の深さを使えません。')
