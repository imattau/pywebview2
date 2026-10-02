import os

import pytest

from webview import protocol


@pytest.fixture
def root(tmp_path):
    (tmp_path / 'index.html').write_text('<h1>index</h1>')
    (tmp_path / 'app.js').write_text('console.log(1)')
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 'index.html').write_text('sub')
    (tmp_path / 'with space.css').write_text('body {}')
    (tmp_path.parent / 'secret.txt').write_text('secret')
    protocol.set_root(str(tmp_path))
    yield tmp_path
    protocol.set_root(None)


@pytest.mark.parametrize('origin', [protocol.SCHEME_ORIGIN, protocol.HTTPS_ORIGIN])
def test_serves_files(root, origin):
    response = protocol.handle(origin + 'app.js')
    assert response.status == 200
    assert response.body == b'console.log(1)'
    assert response.headers['Content-Type'] == 'text/javascript; charset=utf-8'


def test_directory_index(root):
    assert protocol.handle(protocol.SCHEME_ORIGIN).body == b'<h1>index</h1>'
    assert protocol.handle(protocol.SCHEME_ORIGIN + 'sub/').body == b'sub'


def test_quoted_path(root):
    response = protocol.handle(protocol.SCHEME_ORIGIN + 'with%20space.css')
    assert response.status == 200
    assert response.mimetype == 'text/css'


def test_query_and_fragment_ignored(root):
    assert protocol.handle(protocol.SCHEME_ORIGIN + 'app.js?v=1#x').status == 200


def test_not_found(root):
    assert protocol.handle(protocol.SCHEME_ORIGIN + 'missing.js').status == 404


@pytest.mark.parametrize('path', ['../secret.txt', '%2e%2e/secret.txt', 'sub/../../secret.txt'])
def test_traversal_blocked(root, path):
    response = protocol.handle(protocol.SCHEME_ORIGIN + path)
    assert response.status in (403, 404)
    assert b'secret' not in response.body


@pytest.mark.skipif(not hasattr(os, 'symlink'), reason='symlinks unsupported')
def test_symlink_outside_root_blocked(root):
    try:
        os.symlink(root.parent / 'secret.txt', root / 'link.txt')
    except OSError:
        pytest.skip('cannot create symlink')
    assert protocol.handle(protocol.SCHEME_ORIGIN + 'link.txt').status == 403


def test_wrong_host(root):
    assert protocol.handle('pywebview://evil/app.js').status == 404
    assert protocol.handle('https://example.com/app.js').status == 404


def test_method_not_allowed(root):
    assert protocol.handle(protocol.SCHEME_ORIGIN + 'app.js', 'POST').status == 405


def test_head(root):
    response = protocol.handle(protocol.SCHEME_ORIGIN + 'app.js', 'HEAD')
    assert response.status == 200
    assert response.body == b''
    assert response.headers['Content-Length'] == '14'


def test_no_root():
    protocol.set_root(None)
    assert protocol.handle(protocol.SCHEME_ORIGIN + 'index.html').status == 404


class FakeGui:
    custom_protocol_origin = protocol.SCHEME_ORIGIN


def test_resolve_url(root, monkeypatch):
    import webview

    monkeypatch.setitem(webview._state.data, 'custom_protocol', True)
    index = str(root / 'index.html')

    assert protocol.resolve_url(index, FakeGui) == protocol.SCHEME_ORIGIN + 'index.html'
    assert protocol.resolve_url(index + '#/route', FakeGui) == (
        protocol.SCHEME_ORIGIN + 'index.html#/route'
    )
    assert protocol.resolve_url(str(root / 'with space.css'), FakeGui) == (
        protocol.SCHEME_ORIGIN + 'with%20space.css'
    )
    assert protocol.resolve_url(str(root.parent / 'secret.txt'), FakeGui) is None
    assert protocol.resolve_url('https://example.com', FakeGui) is None
    assert protocol.resolve_url(index, object()) is None

    monkeypatch.setitem(webview._state.data, 'custom_protocol', False)
    assert protocol.resolve_url(index, FakeGui) is None
