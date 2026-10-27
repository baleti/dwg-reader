"""HTTP contract tests using synthetic documents and an entirely mocked cache."""
import gzip
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from aiohttp.test_utils import TestClient, TestServer


class FakeDoc:
    def __init__(self, path):
        self.path = path
        self.m = types.SimpleNamespace(objs={})
        self.sc = types.SimpleNamespace(by_block={
            1: [{'handle': 42, 'kind': 'TEXT', 'text': 'hello',
                 'height': 1.23456, 'pts': [1, 2], 'eed': 'hidden'}],
        })
        self.layout = Mock(side_effect=lambda i, twist: {'i': i, 'twist': twist})

    def meta(self):
        return {'default': 1, 'layouts': [
            {'i': 0, 'name': 'Model', 'ps': False},
            {'i': 1, 'name': 'Sheet', 'ps': True},
        ]}


# These modules are absent in the source-only checkout. Supply them before
# importing server, so no real parser or OLE decoder is needed.
build_stub = types.ModuleType('dwgviewer.build')
build_stub.Doc = FakeDoc
ole_stub = types.ModuleType('dwgviewer.ole')
ole_stub.image_png = lambda obj: None
with patch.dict(sys.modules, {'dwgviewer.build': build_stub,
                             'dwgviewer.ole': ole_stub}):
    server = importlib.import_module('dwgviewer.server')
from dwgviewer import ctb


class ServerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = str(self.root / 'synthetic.dwg')  # Never opened.
        self.doc = FakeDoc(self.path)
        self.doc_factory = self.patch(server.build, 'Doc', return_value=self.doc)
        self.png = self.patch(server.OLE, 'image_png', return_value=None)
        self.read_meta = self.patch(server.cache, 'read_meta', return_value=None)
        self.write_meta = self.patch(server.cache, 'write_meta')
        self.read_layout = self.patch(server.cache, 'read_layout', return_value=None)
        self.write_layout = self.patch(server.cache, 'write_layout')
        self.patch(server.cache, 'layout_path', return_value=str(self.root / 'layout.gz'))
        self.patch(server.cache, 'prune')
        self.patch(ctb, 'SEARCH', new=[str(self.root)])
        web = self.root / 'web'
        web.mkdir()
        self.index = b'<!doctype html><title>Synthetic viewer</title>'
        (web / 'index.html').write_bytes(self.index)
        self.patch(server, 'WEB', new=str(web))

    def patch(self, obj, name, **kwargs):
        p = patch.object(obj, name, **kwargs)
        result = p.start()
        self.addCleanup(p.stop)
        return result

    async def client(self, *, loading=False, start_layout=None, raw=False):
        app = server.make_app(self.path, start_layout=start_layout, prefetch=False)
        # aiohttp awaits the startup callback's returned Task. Defer that exact
        # callback explicitly to exercise the otherwise transient empty state,
        # without sleeping or leaving executor threads/tasks running at teardown.
        self.load = app.on_startup[-1]
        if loading:
            app.on_startup.remove(self.load)
        client = TestClient(TestServer(app, host='127.0.0.1'), auto_decompress=not raw)
        self.addAsyncCleanup(client.close)
        await client.start_server()
        return client

    async def assert_json(self, client, url, expected, status=200):
        async with client.get(url) as response:
            self.assertEqual(response.status, status)
            self.assertEqual(await response.json(), expected)

    async def test_meta_loading_then_default(self):
        client = await self.client(loading=True)
        await self.assert_json(client, '/api/meta', {'loading': True})
        self.doc_factory.assert_not_called()
        await self.load(client.server.app)
        await self.assert_json(client, '/api/meta', dict(self.doc.meta(), start=1))
        self.doc_factory.assert_called_once_with(self.path)
        self.write_meta.assert_called_once_with(self.path, self.doc.meta())

    async def test_meta_start_layout_zero(self):
        client = await self.client(start_layout=0)
        await self.assert_json(client, '/api/meta', dict(self.doc.meta(), start=0))
        self.assertNotIn('start', self.write_meta.call_args.args[1])

    async def test_meta_r14_error(self):
        self.doc_factory.side_effect = NotImplementedError('AC1014')
        with patch('traceback.print_exc'):
            client = await self.client()
        await self.assert_json(client, '/api/meta', {'error':
            'This drawing is R14 (AC1014), a file version the parser cannot read yet.'})
        self.write_meta.assert_not_called()

    async def test_meta_unexpected_error(self):
        self.doc_factory.side_effect = RuntimeError('synthetic failure')
        with patch('traceback.print_exc'):
            client = await self.client()
        await self.assert_json(client, '/api/meta', {'error': 'RuntimeError: synthetic failure'})

    async def test_meta_damaged_error(self):
        self.doc_factory.side_effect = ValueError('bad data')
        with patch('traceback.print_exc'):
            client = await self.client()
        await self.assert_json(client, '/api/meta', {'error':
            'This drawing could not be read: the file looks damaged, truncated or uses '
            'data this parser does not decode (bad data).'})

    async def test_layout_loading(self):
        client = await self.client(loading=True)
        await self.assert_json(client, '/api/layout/0', {'loading': True}, status=503)
        self.read_layout.assert_not_called()

    async def test_layout_json_fallback(self):
        client = await self.client()
        await self.assert_json(client, '/api/layout/1', {'i': 1, 'twist': True})
        self.doc.layout.assert_called_once_with(1, True)
        self.write_layout.assert_called_once_with(self.path, 1, True, {'i': 1, 'twist': True})

    async def test_layout_twist_zero(self):
        client = await self.client()
        await self.assert_json(client, '/api/layout/0?twist=0', {'i': 0, 'twist': False})
        self.doc.layout.assert_called_once_with(0, False)
        self.read_layout.assert_called_with(self.path, 0, False)

    async def test_layout_cached_gzip(self):
        payload = {'cached': True}
        body = gzip.compress(json.dumps(payload).encode(), mtime=0)
        self.read_layout.return_value = body
        client = await self.client(raw=True)
        async with client.get('/api/layout/1') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers['Content-Encoding'], 'gzip')
            self.assertEqual(response.content_type, 'application/json')
            self.assertEqual(await response.read(), body)
            self.assertEqual(json.loads(gzip.decompress(body)), payload)
        self.doc.layout.assert_not_called()
        self.write_layout.assert_not_called()

    async def test_layout_new_cache_gzip(self):
        payload = {'i': 1, 'twist': True}
        body = gzip.compress(json.dumps(payload).encode(), mtime=0)
        self.read_layout.side_effect = [None, body]
        client = await self.client(raw=True)
        async with client.get('/api/layout/1') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers['Content-Encoding'], 'gzip')
            self.assertEqual(json.loads(gzip.decompress(await response.read())), payload)
        self.doc.layout.assert_called_once_with(1, True)
        self.write_layout.assert_called_once_with(self.path, 1, True, payload)

    async def test_entity_found(self):
        client = await self.client()
        await self.assert_json(client, '/api/entity/42', {
            'kind': 'TEXT', 'summary': 'text=hello, height=1.235',
            'props': {'handle': 42, 'kind': 'TEXT', 'text': 'hello', 'height': 1.23456}})

    async def test_entity_unknown(self):
        client = await self.client()
        await self.assert_json(client, '/api/entity/999', {})

    async def test_entity_loading(self):
        client = await self.client(loading=True)
        await self.assert_json(client, '/api/entity/42', {'kind': 'loading'})

    async def test_ole_loading(self):
        client = await self.client(loading=True)
        async with client.get('/api/ole/42') as response:
            self.assertEqual(response.status, 404)
        self.png.assert_not_called()

    async def test_ole_missing_wrong_type_and_no_image(self):
        self.doc.m.objs = {1: types.SimpleNamespace(type=1),
                           2: types.SimpleNamespace(type=74)}
        client = await self.client()
        for handle in (999, 1, 2):
            with self.subTest(handle=handle):
                async with client.get('/api/ole/%d' % handle) as response:
                    self.assertEqual(response.status, 404)
        self.png.assert_called_once_with(self.doc.m.objs[2])

    async def test_ctblist(self):
        for name in ('a.ctb', 'b.CTB', 'c.txt'):
            (self.root / name).touch()
        client = await self.client()
        await self.assert_json(client, '/api/ctblist', ['a.ctb', 'b.CTB'])

    async def test_ctb_unknown(self):
        client = await self.client()
        await self.assert_json(client, '/api/ctb?name=unknown', {'name': 'unknown', 'found': False})

    async def test_index(self):
        client = await self.client()
        async with client.get('/') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.content_type, 'text/html')
            self.assertEqual(await response.read(), self.index)


if __name__ == '__main__':
    unittest.main()
