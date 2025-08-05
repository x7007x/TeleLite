import asyncio
import json
import re
from functools import wraps

from quart import Quart, request  # async Flask-like framework, install via 'pip install quart'
import aiohttp

update_types = [
    'message', 'edited_message', 'channel_post', 'edited_channel_post',
    'business_connection', 'business_message', 'edited_business_message',
    'deleted_business_messages', 'message_reaction', 'message_reaction_count',
    'inline_query', 'chosen_inline_result', 'callback_query', 'shipping_query',
    'pre_checkout_query', 'purchased_paid_media', 'poll', 'poll_answer',
    'my_chat_member', 'chat_member', 'chat_join_request', 'chat_boost',
    'removed_chat_boost'
]

def safe_print(obj):
    try:
        print(json.dumps(obj, indent=4, ensure_ascii=False))
    except Exception:
        print(obj)

# FilterBase and Filters classes remain same, omitted here for brevity.
# Include your existing FilterBase and Filters classes here unchanged.

class FilterWrapper(FilterBase):
    def __init__(self, func):
        self.func = func
    def __call__(self, update):
        try:
            return self.func(update)
        except Exception:
            return False

class Bot:
    def __init__(self, token, webhook=None):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.handlers = {ut: [] for ut in update_types}
        self.webhook = webhook
        self.app = None
        if webhook:
            self.app = Quart(__name__)

            @self.app.route('/alive')
            async def handle_alive():
                return 'Alive 🕯️', 200

            @self.app.route('/webhook', methods=['POST'])
            async def handle_webhook():
                update = await request.get_json()
                if not update:
                    return 'No Data', 400
                update_type = self._extract_update_type(update)
                if update_type and update_type in self.handlers:
                    data = update.get(update_type, {})
                    data = self._fix_reserved_keys(data)
                    await self._process_handlers(update_type, data)
                return '🚀', 200

        self._session = None  # aiohttp.ClientSession will be lazily created

    def _extract_update_type(self, update):
        for ut in update_types:
            if ut in update:
                return ut
        return None

    def _fix_reserved_keys(self, data):
        if isinstance(data, dict):
            if 'from' in data:
                data['from_user'] = data.pop('from')
            for k, v in data.items():
                if isinstance(v, dict):
                    data[k] = self._fix_reserved_keys(v)
                elif isinstance(v, list):
                    data[k] = [self._fix_reserved_keys(i) if isinstance(i, dict) else i for i in v]
        return data

    async def _process_handlers(self, update_type, data):
        for filt, handler in self.handlers.get(update_type, []):
            try:
                ok = filt(data) if callable(filt) else match_filter(data, filt)
                if ok:
                    result = handler(data)
                    if asyncio.iscoroutine(result):
                        await result
            except Exception as e:
                print(f"Handler error: {e}")

    def _handler_decorator(self, update_type, filter_):
        def decorator(fn):
            self.handlers[update_type].append((filter_, fn))
            @wraps(fn)
            def wrapper(*args, **kwargs):
                res = fn(*args, **kwargs)
                if asyncio.iscoroutine(res):
                    return asyncio.run(res)
                return res
            return wrapper
        return decorator

    # Example handler decorator method:
    def on_message(self, filter_=None):
        return self._handler_decorator('message', filter_)

    # (Add other handler decorators here, same pattern as on_message)

    async def __call__(self, method: str, **params):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        url = f"{self.api_url}/{method}"
        headers = {'Content-Type': 'application/json'}
        async with self._session.post(url, json=params, headers=headers) as resp:
            data = await resp.json()
            safe_print(data)
            return data

    async def long_polling(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        offset = 0
        while True:
            try:
                async with self._session.post(
                    f"{self.api_url}/getUpdates",
                    json={"offset": offset, "timeout": 100, "allowed_updates": update_types},
                ) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(1)
                        continue
                    result_json = await resp.json()
                if result_json.get('ok'):
                    for upd in result_json.get('result', []):
                        offset = max(offset, upd['update_id'] + 1)
                        utype = self._extract_update_type(upd)
                        if not utype:
                            continue
                        data = self._fix_reserved_keys(upd.get(utype, {}))
                        await self._process_handlers(utype, data)
            except Exception as e:
                print(f"Long polling error: {e}")
                await asyncio.sleep(1)

    def run(self):
        if self.webhook:
            print("Running async webhook server with Quart...")
            import hypercorn.asyncio
            import hypercorn.config
            config = hypercorn.config.Config()
            config.bind = ["0.0.0.0:5000"]

            asyncio.run(hypercorn.asyncio.serve(self.app, config))
        else:
            print("Running async long polling...")
            asyncio.run(self.long_polling())
