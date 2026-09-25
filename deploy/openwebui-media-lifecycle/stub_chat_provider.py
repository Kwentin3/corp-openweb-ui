#!/usr/bin/env python3
"""Isolated GUI smoke fixture; never configure this provider in production."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip('/') != '/v1/models':
            self.send_error(404)
            return
        self._json({"object": "list", "data": [{"id": "media-smoke-model", "object": "model", "owned_by": "test"}]})

    def do_POST(self):
        if self.path.rstrip('/') != '/v1/chat/completions':
            self.send_error(404)
            return
        request = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        if request.get('stream'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            for event in (
                {"id": "media-smoke", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "Аудио получено."}, "finish_reason": None}]},
                {"id": "media-smoke", "object": "chat.completion.chunk", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ):
                self.wfile.write(b'data: ' + json.dumps(event).encode() + b'\n\n')
                self.wfile.flush()
            self.wfile.write(b'data: [DONE]\n\n')
            self.wfile.flush()
        else:
            self._json({"id": "media-smoke", "object": "chat.completion", "choices": [{"index": 0, "message": {"role": "assistant", "content": "Аудио получено."}, "finish_reason": "stop"}]})

    def _json(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


HTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
