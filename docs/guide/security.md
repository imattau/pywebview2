# Security

## Serving local files

By default local files are served by an HTTP server on `127.0.0.1` and a random port. Any process on the machine, or a web page in a browser that finds the port, can request those files.

Start the application with `custom_protocol=True` to serve local files through a native URL scheme handler instead:

```python
webview.create_window('My App', 'frontend/index.html')
webview.start(custom_protocol=True)
```

Files are then loaded from `pywebview://localhost/` (GTK, Cocoa, Qt WebEngine) or `https://pywebview.localhost/` (EdgeChromium). These requests are answered inside the application and never reach a network socket. Only files inside the root directory, the deepest directory common to the local URLs of windows created before `start`, are served, and requests that escape it through `..` or symbolic links are refused. Pages are treated as a secure context, so APIs such as `crypto.subtle` are available. The origin is fixed, so `localStorage` and cookies persist between runs when `private_mode=False`.

Backends that do not support scheme handlers (CEF, MSHTML, QtWebKit, Android and iOS) fall back to the HTTP server. Projects created with `pywebview2 init` enable the custom protocol by default.

## SSL for the HTTP server

If you use the HTTP server, it is advisable to enable SSL for it. To accomplish this, simply start the application with the `ssl` paramater set to True `webview.start(ssl=True)`. You need to have `cryptography` pip dependency installed in order to use `ssl`. It is not installed by default.

If you employ a REST API, [CSRF attacks](https://www.owasp.org/index.php/Cross-Site_Request_Forgery_(CSRF)) can be a major concern. _pywebview_ mitigates this risk by generating a session-unique token that is accessible in Python as `webview.token` and in JavaScript as `window.pywebview.token`. For more information on securing APIs, refer to the [CSRF Prevention Cheat Sheet](https://www.owasp.org/index.php/Cross-Site_Request_Forgery_\(CSRF\)_Prevention_Cheat_Sheet). You can also see a practical example in the [Flask app](https://github.com/r0x0r/pywebview/tree/master/examples/flask_app).
