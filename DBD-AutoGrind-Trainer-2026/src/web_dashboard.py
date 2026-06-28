import asyncio
import threading
import logging
from aiohttp import web
from src.trainer import Trainer

log = logging.getLogger(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>DBD Trainer Dashboard</title>
    <meta charset="utf-8">
    <style>
        body { background: #1a1a2e; color: #eee; font-family: sans-serif; }
        .card { background: #0f3460; margin: 10px; padding: 15px; border-radius: 8px; }
        button { background: #e94560; border: none; color: white; padding: 10px 20px; margin: 5px; cursor: pointer; }
    </style>
</head>
<body>
    <h1>🔪 DBD AutoGrind Trainer 2026</h1>
    <div id="features"></div>
    <script>
        const ws = new WebSocket('ws://' + location.host + '/ws');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const container = document.getElementById('features');
            container.innerHTML = '';
            for (const [k, v] of Object.entries(data.features)) {
                container.innerHTML += `<div class="card">${k}: ${v ? "ON" : "OFF"}</div>`;
            }
        };
        function toggle(key) { ws.send(JSON.stringify({action: 'toggle', feature: key})); }
        function attach() { ws.send(JSON.stringify({action: 'attach'})); }
    </script>
    <button onclick="attach()">Attach to Game</button>
    <button onclick="toggle('esp')">Toggle ESP</button>
    <button onclick="toggle('aimbot')">Toggle Aimbot</button>
</body>
</html>
"""

class WebDashboard:
    def __init__(self, trainer: Trainer):
        self.trainer = trainer
        self.app = web.Application()
        self.runner = None
        self.site = None
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/ws', self.websocket_handler)

    async def index(self, request):
        return web.Response(text=HTML_TEMPLATE, content_type='text/html')

    async def websocket_handler(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        # Send initial state
        await ws.send_json({"features": self.trainer.features})
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = msg.json()
                if data.get("action") == "toggle":
                    feature = data.get("feature")
                    if feature in self.trainer.features:
                        self.trainer.features[feature] = not self.trainer.features[feature]
                elif data.get("action") == "attach":
                    await self.trainer.attach_to_game()
                await ws.send_json({"features": self.trainer.features})
        return ws

    def start(self):
        threading.Thread(target=self._run_server, daemon=True).start()

    def _run_server(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.runner = web.AppRunner(self.app)
        loop.run_until_complete(self.runner.setup())
        self.site = web.TCPSite(self.runner, 'localhost', 4200)
        loop.run_until_complete(self.site.start())
        log.info("Web dashboard running on http://localhost:4200")
        loop.run_forever()

    def stop(self):
        if self.runner:
            asyncio.ensure_future(self.runner.cleanup())
