"""OpenRouter chat-completions adapter for the existing visual editing loop."""
import json
import time
import urllib.request
import urllib.error
import re


def parse_arguments(raw):
    # Accept only unambiguous transport formatting. Never invent missing braces,
    # values or keys, or silently discard a second JSON object.
    cleaned = raw.strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n([\s\S]*?)\n```', cleaned)
    if fenced:
        cleaned = fenced[1]
    return json.loads(cleaned, strict=False)


def model_id(model):
    aliases = {'claude-opus-5-5': 'anthropic/claude-opus-5.5'}
    return aliases.get(model, model)


def image_content(block):
    src = block['source']
    if src['type'] != 'base64':
        raise ValueError('Only inline evidence images are supported')
    return {'type': 'image_url', 'image_url': {'url': 'data:' + src['media_type'] + ';base64,' + src['data']}}


def convert_messages(messages, system):
    converted = [{'role': 'system', 'content': system}]
    for message in messages:
        content = message['content']
        if isinstance(content, str):
            converted.append({'role': message['role'], 'content': content})
            continue
        if message['role'] == 'assistant':
            item = {'role': 'assistant', 'content': '\n'.join(b['text'] for b in content if b['type'] == 'text') or None}
            tools = [{'id': b['id'], 'type': 'function', 'function': {'name': b['name'], 'arguments': json.dumps(b['input'], ensure_ascii=False)}}
                     for b in content if b['type'] == 'tool_use']
            details = [d for b in content if b['type'] == 'openrouter_reasoning_details' for d in b['details']]
            if tools:
                item['tool_calls'] = tools
            if details:
                item['reasoning_details'] = details
            converted.append(item)
            continue
        tool_results = [b for b in content if b['type'] == 'tool_result']
        if tool_results:
            image_followups = []
            for result in tool_results:
                blocks = result['content']
                if isinstance(blocks, str):
                    text = blocks
                else:
                    text = '\n'.join(b['text'] for b in blocks if b['type'] == 'text')
                    if any(b['type'] == 'image' for b in blocks):
                        image_followups.append({'type': 'text', 'text': 'Images for tool result ' + result['tool_use_id']})
                        for block in blocks:
                            if block['type'] == 'image':
                                image_followups.append(image_content(block))
                            elif block['type'] == 'text':
                                image_followups.append(block)
                converted.append({'role': 'tool', 'tool_call_id': result['tool_use_id'],
                                  'content': ('Tool error: ' if result.get('is_error') else '') + text})
            if image_followups:
                converted.append({'role': 'user', 'content': image_followups})
        else:
            blocks = [image_content(b) if b['type'] == 'image' else b for b in content if b['type'] in {'image', 'text'}]
            converted.append({'role': 'user', 'content': blocks})
    return converted


class OpenRouterClient:
    def __init__(self, api_key, config, error_type=RuntimeError):
        self.key, self.config, self.error_type = api_key, config, error_type
        self.calls = []

    def send(self, messages, tools, system):
        model = model_id(self.config.model)
        if '/' not in model:
            raise self.error_type('OpenRouterのモデル名は「anthropic/claude-opus-5.5」等を指定してください。')
        payload = {'model': model, 'messages': convert_messages(messages, system),
                   'tools': [{'type': 'function', 'function': {'name': t['name'], 'description': t['description'], 'parameters': t['input_schema']}} for t in tools],
                   'reasoning': {'effort': self.config.effort}, 'max_tokens': self.config.max_tokens,
                   'provider': {'require_parameters': True}, 'stream': True, 'stream_options': {'include_usage': True}}
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        if len(data) > 30_000_000:
            raise self.error_type('AIへの送信量が大きすぎます。解析画像数を減らしてください。')
        request = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions', data=data,
                                         headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.key})
        start, tool_calls, reasons, usage = time.monotonic(), {}, {}, {}
        text, stop, ended = '', None, False
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                for raw in response:
                    line = raw.decode('utf-8').strip()
                    if not line.startswith('data:'):
                        continue
                    if line[5:].strip() == '[DONE]':
                        ended = True
                        break
                    event = json.loads(line[5:])
                    if event.get('error'):
                        code = event['error'].get('code', 'unknown')
                        raise self.error_type(f'OpenRouterの生成に失敗しました（{code}）。利用上限・モデルの利用条件を確認してください。')
                    if event.get('usage'):
                        u = event['usage']
                        usage.update(input_tokens=u.get('prompt_tokens', 0), output_tokens=u.get('completion_tokens', 0))
                        if u.get('cost') is not None:
                            usage['cost_usd'] = u['cost']
                        if (u.get('completion_tokens_details') or {}).get('reasoning_tokens') is not None:
                            usage['reasoning_tokens'] = u['completion_tokens_details']['reasoning_tokens']
                    for choice in event.get('choices', []):
                        if choice.get('index', 0) != 0:
                            continue
                        stop = choice.get('finish_reason') or stop
                        delta = choice.get('delta') or {}
                        text += delta.get('content') or ''
                        for detail_index, detail in enumerate(delta.get('reasoning_details') or []):
                            index = detail.get('index', detail.get('id') or str(detail_index))
                            previous = reasons.setdefault(str(index), {})
                            for name, value in detail.items():
                                if name in {'text', 'summary', 'data'} and isinstance(value, str):
                                    previous[name] = previous.get(name, '') + value
                                else:
                                    previous[name] = value
                        for tool in delta.get('tool_calls') or []:
                            item = tool_calls.setdefault(tool.get('index', 0), {'id': '', 'name': '', 'arguments': ''})
                            if tool.get('id'):
                                item['id'] = tool['id']
                            fn = tool.get('function') or {}
                            item['name'] += fn.get('name') or ''
                            item['arguments'] += fn.get('arguments') or ''
                    if time.monotonic() - start > 1800:
                        raise self.error_type('1回のAI処理が30分を超えたため終了しました。')
        except urllib.error.HTTPError as error:
            hints = {401: 'APIキーが認証されませんでした。', 402: '残高またはキーの利用上限が不足しています。',
                     403: 'このキー・地域・アカウントでは利用できません。', 404: '指定したモデルが利用できません。',
                     429: '利用上限です。時間をおいて再実行してください。', 400: 'モデル名・推論設定・入力容量を確認してください。'}
            raise self.error_type(f'OpenRouter HTTP {error.code}: ' + hints.get(error.code, 'API接続に失敗しました。')) from None
        except urllib.error.URLError:
            raise self.error_type('OpenRouterに接続できません。ネットワーク接続を確認してください。') from None
        finally:
            self.calls.append({'seconds': round(time.monotonic()-start, 2), 'usage': usage, 'stop_reason': stop, 'provider': 'openrouter'})
        self.calls[-1]['output_shape'] = {'text_characters': len(text),
            'tool_argument_characters': sum(len(t['arguments']) for t in tool_calls.values()),
            'tool_count': len(tool_calls)}
        if stop == 'length':
            raise self.error_type(f'AIの返答が1回の出力上限（{self.config.max_tokens:,}トークン）で途切れました。途中の出力は完成扱いにせず、使用量を保存しました。')
        if not ended or stop is None or stop in {'content_filter', 'error'}:
            raise self.error_type('OpenRouterから完全な生成結果を受信できませんでした（' + str(stop) + '）。')
        blocks = []
        if reasons:
            blocks.append({'type': 'openrouter_reasoning_details', 'details': list(reasons.values())})
        if text:
            blocks.append({'type': 'text', 'text': text})
        for index in sorted(tool_calls):
            item = tool_calls[index]
            try:
                arguments = parse_arguments(item['arguments'])
            except json.JSONDecodeError as error:
                self.calls[-1]['invalid_tool_output'] = {'index': index, 'characters': len(item['arguments']),
                                                         'line': error.lineno, 'column': error.colno}
                failure = self.error_type('AIの提出データをJSONとして読み取れませんでした。')
                failure.tool_output = {'name': item['name'], 'arguments': item['arguments']}
                raise failure from None
            if not item['id'] or not item['name'] or not isinstance(arguments, dict):
                raise self.error_type('AIのツール出力が不正です。')
            blocks.append({'type': 'tool_use', 'id': item['id'], 'name': item['name'], 'input': arguments})
        if not blocks:
            raise self.error_type('AIから内容のある応答を受信できませんでした。')
        return blocks
