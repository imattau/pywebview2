from threading import Event

import webview

from .util import assert_js, run_test


class Api:
    def test(self):
        return 'JS Api is working too'


def test_custom_protocol():
    api = Api()
    window = webview.create_window('Custom protocol test', 'assets/test.html', js_api=api)
    run_test(webview, window, assert_func, start_args={'custom_protocol': True})


def evaluate_async(window, script):
    result = {}
    done = Event()

    def callback(value):
        result['value'] = value
        done.set()

    window.evaluate_js(script, callback)
    assert done.wait(10), f'Timed out evaluating {script}'
    return result['value']


def assert_func(window):
    from webview import http, protocol

    url = window.get_current_url()
    if protocol.origin_for(webview.guilib) is None:
        # backend without scheme handler support falls back to the HTTP server
        assert url.startswith('http://127.0.0.1')
        return

    assert protocol.is_protocol_url(url)
    assert http.global_server is None

    html_result = window.evaluate_js('document.getElementById("heading").innerText')
    assert html_result == 'Hello there!'

    css_result = window.evaluate_js(
        'window.getComputedStyle(document.body, null).getPropertyValue("background-color")'
    )
    assert css_result == 'rgb(255, 0, 0)'

    js_result = window.evaluate_js('window.testResult')
    assert js_result == 80085

    fetch_result = evaluate_async(
        window,
        """
        fetch('data.json').then(r => r.json()).then(data => data.value)
        """,
    )
    assert fetch_result == 42

    # Qt WebEngine cannot reply with an error status, so the request fails instead
    status = evaluate_async(
        window, "fetch('../conftest.py').then(r => r.status).catch(() => 'blocked')"
    )
    assert status in (403, 404, 'blocked')

    if webview.renderer != 'cocoa':
        assert window.evaluate_js('window.isSecureContext') is True

    assert_js(window, 'test', 'JS Api is working too')


def test_custom_protocol_load_url():
    window = webview.create_window('Custom protocol load_url test', html='<h1>start</h1>')
    run_test(webview, window, load_url_func, start_args={'custom_protocol': True})


def load_url_func(window):
    from webview import protocol

    window.load_url('assets/module.html')
    window.events.loaded.wait(10)

    if protocol.origin_for(webview.guilib) is not None:
        assert protocol.is_protocol_url(window.get_current_url())

    assert window.evaluate_js('document.getElementById("heading").innerText') == 'Module page'
    # module scripts are deferred and need a correct MIME type and CORS support
    assert window.evaluate_js('window.moduleResult') == 'module loaded'
