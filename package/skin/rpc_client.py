"""Minimal asynchronous JSON-RPC transport to the installed Codex app-server."""
import asyncio
import json
import os
from pathlib import Path
import shutil

import console_guard
from texts import t


def executable():
    local = os.environ.get('LOCALAPPDATA', os.path.expanduser('~/AppData/Local'))
    installed = Path(local) / 'Programs/OpenAI/Codex/bin/codex.exe'
    if installed.is_file():
        return str(installed)
    path = shutil.which('codex.exe') or shutil.which('codex')
    if not path:
        raise FileNotFoundError(t("codex_missing"))
    return path


class RpcClient:
    def __init__(self, on_event):
        self.on_event = on_event
        self.pending = {}
        self.counter = 0
        self.process = None
        self.tasks = []
        self.diagnostics = []

    async def start(self, cwd):
        self.process = await asyncio.create_subprocess_exec(
            executable(), 'app-server', '--stdio', cwd=cwd,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, limit=16 * 1024 * 1024)
        self.tasks = [asyncio.create_task(self.read()), asyncio.create_task(self.read_errors())]
        await self.call('initialize', {'clientInfo': {'name': 'terminal_skin',
                         'title': 'Matrix Terminal', 'version': '0.1.0'}})
        await self.send({'method': 'initialized', 'params': {}})

    async def send(self, value):
        if not self.process or self.process.returncode is not None:
            raise RuntimeError('Соединение с Codex закрыто')
        self.process.stdin.write((json.dumps(value, ensure_ascii=False) + '\n').encode('utf-8'))
        await self.process.stdin.drain()

    async def call(self, method, params=None, timeout=90):
        self.counter += 1
        ident = self.counter
        future = asyncio.get_running_loop().create_future()
        self.pending[ident] = future
        try:
            await self.send({'id': ident, 'method': method, 'params': params or {}})
            return await asyncio.wait_for(future, timeout)
        finally:
            self.pending.pop(ident, None)

    async def respond(self, ident, result):
        await self.send({'id': ident, 'result': result})

    async def read(self):
        try:
            while line := await self.process.stdout.readline():
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                if 'method' in data:
                    self.on_event(data)
                elif data.get('id') in self.pending:
                    future = self.pending[data['id']]
                    if not future.done():
                        if 'error' in data:
                            future.set_exception(RuntimeError(data['error'].get('message', str(data['error']))))
                        else:
                            future.set_result(data.get('result', {}))
        finally:
            for future in list(self.pending.values()):
                if not future.done():
                    future.set_exception(RuntimeError('Codex завершил соединение. ' + '\n'.join(self.diagnostics[-3:])))
            self.on_event({'method': 'transport/closed', 'params': {}})

    async def read_errors(self):
        while line := await self.process.stderr.readline():
            self.diagnostics.append(line.decode('utf-8', errors='replace').strip())
            self.diagnostics = self.diagnostics[-30:]

    async def close(self):
        if self.process and self.process.returncode is None:
            self.process.stdin.close()
            try:
                await asyncio.wait_for(self.process.wait(), 3)
            except asyncio.TimeoutError:
                # terminate() снимает только сам codex.exe, его потомки
                # остаются жить: так в системе и накопился десяток
                # процессов Codex за один вечер.
                await asyncio.to_thread(console_guard.kill_tree, self.process.pid)
                await self.process.wait()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
