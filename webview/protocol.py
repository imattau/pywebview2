"""
Custom URL protocol for serving local application files without an HTTP server.

Instead of exposing local files on ``http://127.0.0.1:<port>``, backends that
support it register a native scheme handler and serve files directly from the
application's frontend directory. Nothing listens on a network socket, so
other local processes and web pages cannot reach the application's assets,
and the origin stays the same between runs, which keeps localStorage and
cookies stable without a fixed port.

Backends expose support through a module-level ``custom_protocol_origin``
attribute. WebKit and Qt WebEngine use ``pywebview://localhost/``. WebView2
only treats http(s) as a secure context, so it uses
``https://pywebview.localhost/`` and intercepts those requests before they
reach the network.

The handler below is backend-agnostic: each backend translates its native
request into a URL, calls :func:`handle` and translates the result back.
"""

from __future__ import annotations

import logging
import mimetypes
import os
from dataclasses import dataclass, field
from urllib.parse import quote, unquote, urlsplit

from webview.util import abspath, is_local_url

logger = logging.getLogger('pywebview2')

SCHEME = 'pywebview'
HOST = 'localhost'
HTTPS_HOST = 'pywebview.localhost'

SCHEME_ORIGIN = f'{SCHEME}://{HOST}/'
HTTPS_ORIGIN = f'https://{HTTPS_HOST}/'

# Platform MIME databases are unreliable (notably the Windows registry), and a
# wrong type for a script breaks ES module loading, so the common web types
# are fixed here.
_MIME_TYPES = {
    '.html': 'text/html',
    '.htm': 'text/html',
    '.js': 'text/javascript',
    '.mjs': 'text/javascript',
    '.cjs': 'text/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.map': 'application/json',
    '.wasm': 'application/wasm',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.avif': 'image/avif',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf': 'font/ttf',
    '.otf': 'font/otf',
    '.txt': 'text/plain',
    '.xml': 'application/xml',
    '.mp4': 'video/mp4',
    '.webm': 'video/webm',
    '.mp3': 'audio/mpeg',
    '.ogg': 'audio/ogg',
    '.wav': 'audio/wav',
}

_TEXT_PREFIXES = ('text/', 'application/json', 'application/xml', 'image/svg+xml')

_root: str | None = None


@dataclass
class AssetResponse:
    status: int
    reason: str
    mimetype: str
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def content_type(self) -> str:
        if self.mimetype.startswith(_TEXT_PREFIXES) or self.mimetype == 'text/javascript':
            return f'{self.mimetype}; charset=utf-8'
        return self.mimetype


def is_enabled() -> bool:
    from webview import _state

    return bool(_state['custom_protocol'])


def origin_for(gui) -> str | None:
    """Return the origin a GUI backend serves the protocol on, or None if unsupported."""
    if gui is None or not is_enabled():
        return None
    return getattr(gui, 'custom_protocol_origin', None)


def get_root() -> str | None:
    return _root


def set_root(path: str | None) -> None:
    global _root
    _root = os.path.realpath(abspath(path)) if path else None
    logger.debug(f'Custom protocol root: {_root}')


def set_root_from_urls(urls: list) -> None:
    """Use the deepest directory common to all local URLs as the root."""
    dirs = []
    for url in urls:
        if is_local_url(url):
            path = abspath(_strip_suffix(url))
            dirs.append(path if os.path.isdir(path) else os.path.dirname(path))

    set_root(os.path.commonpath(dirs) if dirs else None)


def resolve_url(url, gui) -> str | None:
    """
    Map a local file URL to its custom protocol URL. Returns None when the
    protocol is disabled, unsupported by the backend, or the file lies outside
    the root, in which case the caller falls back to the HTTP server.
    """
    origin = origin_for(gui)
    if not origin or not is_local_url(url):
        return None

    path_part = _strip_suffix(url)
    suffix = url[len(path_part) :]
    path = os.path.realpath(abspath(path_part))

    if _root is None:
        set_root(path if os.path.isdir(path) else os.path.dirname(path))

    if not _is_within(path, _root):
        logger.debug(f'{url} is outside the custom protocol root, falling back to HTTP server')
        return None

    relative = os.path.relpath(path, _root).replace(os.sep, '/')
    if relative == '.':
        relative = ''

    return origin + quote(relative) + suffix


def is_protocol_url(url: str | None) -> bool:
    if not url:
        return False
    return url.startswith(SCHEME_ORIGIN) or url.startswith(HTTPS_ORIGIN)


def handle(url: str, method: str = 'GET') -> AssetResponse:
    """Serve a request for a custom protocol URL from the root directory."""
    parts = urlsplit(url)

    if (parts.scheme, parts.hostname) not in ((SCHEME, HOST), ('https', HTTPS_HOST)):
        return error_response(404, 'Not Found')

    if method not in ('GET', 'HEAD'):
        return error_response(405, 'Method Not Allowed', {'Allow': 'GET, HEAD'})

    if _root is None:
        return error_response(404, 'Not Found')

    relative = unquote(parts.path).lstrip('/')
    if '\0' in relative:
        return error_response(400, 'Bad Request')

    path = os.path.realpath(os.path.join(_root, relative))

    # realpath resolves both '..' segments and symlinks, so this also rejects
    # links that point outside the root.
    if not _is_within(path, _root):
        logger.warning(f'Blocked custom protocol request outside root: {url}')
        return error_response(403, 'Forbidden')

    if os.path.isdir(path):
        path = os.path.join(path, 'index.html')

    if not os.path.isfile(path):
        return error_response(404, 'Not Found')

    try:
        with open(path, 'rb') as f:
            body = f.read()
    except OSError as e:
        logger.error(f'Failed to read {path}: {e}')
        return error_response(500, 'Internal Server Error')

    response = AssetResponse(
        200,
        'OK',
        guess_mimetype(path),
        b'' if method == 'HEAD' else body,
        {
            'Cache-Control': 'no-cache',
            'Content-Length': str(len(body)),
            'X-Content-Type-Options': 'nosniff',
        },
    )
    response.headers['Content-Type'] = response.content_type
    return response


def guess_mimetype(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return _MIME_TYPES.get(ext) or mimetypes.guess_type(path)[0] or 'application/octet-stream'


def error_response(
    status: int, reason: str, headers: dict[str, str] | None = None
) -> AssetResponse:
    response = AssetResponse(status, reason, 'text/plain', reason.encode(), dict(headers or {}))
    response.headers['Content-Type'] = response.content_type
    response.headers['Content-Length'] = str(len(response.body))
    return response


def _is_within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives on Windows
        return False


def _strip_suffix(url: str) -> str:
    """Remove a query string or fragment from a local URL."""
    for i, char in enumerate(url):
        if char in '?#':
            return url[:i]
    return url
