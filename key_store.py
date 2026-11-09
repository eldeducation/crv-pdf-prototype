"""Optional saving of the API key on the local PC, encrypted with Windows DPAPI.

Opt-in only. The key is encrypted for the current Windows user (only this user
on this PC can decrypt it) and stored in a git-ignored file next to the app.
Never available on shared/cloud sessions or outside Windows: there the key
stays in memory only, as before.
"""
import ctypes
import os
from ctypes import wintypes
from pathlib import Path

FILE_NAME = 'api_key.local.dpapi'
_ENTROPY = b'crv-pdf-prototype api key v1'


def available(root):
    """Local Windows server only (not a shared-session copy, not the cloud image)."""
    root = Path(root)
    return (os.name == 'nt' and root.parent.name != 'share-sessions'
            and not os.getenv('VIDEO_PDF_DISABLE_KEY_STORE'))


class _Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]


def _blob(data):
    buffer = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def _crypt(data, protect):
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    source, _keep = _blob(data)
    entropy, _keep2 = _blob(_ENTROPY)
    result = _Blob()
    no_ui = 0x1                                                     # CRYPTPROTECT_UI_FORBIDDEN
    if protect:
        ok = crypt32.CryptProtectData(ctypes.byref(source), 'crv-pdf-prototype', ctypes.byref(entropy),
                                      None, None, no_ui, ctypes.byref(result))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(source), None, ctypes.byref(entropy),
                                        None, None, no_ui, ctypes.byref(result))
    if not ok:
        raise OSError('DPAPI failed')
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)


def save(root, key):
    if not available(root):
        raise OSError('Key saving is not available here.')
    path = Path(root) / FILE_NAME
    temp = path.with_suffix('.tmp')
    temp.write_bytes(_crypt(key.encode('utf-8'), True))
    temp.replace(path)


def load(root):
    """The saved key, or '' when none is saved or it cannot be decrypted by this user."""
    path = Path(root) / FILE_NAME
    if not available(root) or not path.is_file():
        return ''
    try:
        return _crypt(path.read_bytes(), False).decode('utf-8')
    except (OSError, UnicodeError):
        return ''


def delete(root):
    path = Path(root) / FILE_NAME
    try:
        path.unlink()
    except FileNotFoundError:
        pass
