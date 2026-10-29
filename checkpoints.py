"""Local stage checkpoints. No client object or credentials are serialized."""
import gzip
import hashlib
import json
import time


def signature(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class Checkpoint:
    def __init__(self, folder, name, context):
        self.path = folder / ('checkpoint-' + name + '.json.gz')
        self.state_path = folder / ('checkpoint-' + name + '.state.json')
        self.signature = signature(context)

    def load(self):
        if not self.path.exists():
            return None
        with gzip.open(self.path, 'rt', encoding='utf-8') as stream:
            saved = json.load(stream)
        return saved if saved.get('signature') == self.signature else None

    def save(self, **state):
        temp = self.path.with_suffix('.tmp')
        with gzip.open(temp, 'wt', encoding='utf-8') as stream:
            json.dump({'signature': self.signature, **state}, stream, ensure_ascii=False)
        temp.replace(self.path)
        # Small metadata avoids repeatedly loading image-filled checkpoints for UI polling.
        summary = {'version': 1, 'signature': self.signature, 'saved_at': time.time(),
                   'completed': 'result' in state or bool(state.get('approved')),
                   'approved': bool(state.get('approved')) or (isinstance(state.get('result'), dict) and bool(state['result'].get('approved'))),
                   'round': state.get('round', 0), 'has_pending_tools': bool(state.get('pending'))}
        small = self.state_path.with_suffix('.tmp')
        small.write_text(json.dumps(summary), encoding='utf-8')
        small.replace(self.state_path)
