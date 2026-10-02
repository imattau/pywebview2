from importlib import reload

import pytest


@pytest.fixture(autouse=True)
def reload_webview():
    import webview
    from webview import http, protocol

    reload(webview)
    reload(http)
    reload(protocol)


@pytest.fixture(autouse=True)
def set_env():
    import os

    os.environ['PYWEBVIEW2_TEST'] = 'true'


# @pytest.fixture(autouse=True)
# def set_gui():
#     import os
#     os.environ['PYWEBVIEW2_GUI'] = 'qt'
