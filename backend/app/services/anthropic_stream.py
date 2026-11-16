"""A streamed Messages API call, assembled into the same response shape as a non-streamed one.

The research chat shows a reply as it is written, so it streams. Each content block is rebuilt exactly from its
events (text, reasoning and its signature, tool inputs, citations, and server tool results, which arrive whole),
because a continued conversation must send every block back unchanged. A listener sees each event as it arrives.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

import httpx

from app.services.opportunity_dossier import URL, DossierUnavailable

Listener = Callable[[str, dict[str, Any]], None]
log = logging.getLogger(__name__)


class Assembler:
    """Builds the final message from stream events. Unknown block and delta types are kept as they arrive."""

    def __init__(self, listener: Listener | None = None):
        self.message: dict[str, Any] = {}
        self.blocks: dict[int, dict[str, Any]] = {}
        self.partial: dict[int, str] = {}
        self.listener = listener

    def feed(self, kind: str, data: dict[str, Any]) -> None:
        if kind == 'message_start':
            self.message = dict(data.get('message') or {})
            self.message['content'] = []
        elif kind == 'content_block_start':
            self.blocks[data['index']] = dict(data.get('content_block') or {})
        elif kind == 'content_block_delta':
            block, delta = self.blocks.setdefault(data['index'], {}), data.get('delta') or {}
            kind_of = delta.get('type')
            if kind_of == 'text_delta':
                block['text'] = block.get('text', '') + delta.get('text', '')
            elif kind_of == 'thinking_delta':
                block['thinking'] = block.get('thinking', '') + delta.get('thinking', '')
            elif kind_of == 'signature_delta':
                block['signature'] = block.get('signature', '') + delta.get('signature', '')
            elif kind_of == 'input_json_delta':
                self.partial[data['index']] = self.partial.get(data['index'], '') + delta.get('partial_json', '')
            elif kind_of == 'citations_delta':
                block['citations'] = [*(block.get('citations') or []), delta.get('citation')]
        elif kind == 'content_block_stop':
            index = data['index']
            if index in self.partial:
                raw = self.partial.pop(index)
                try:
                    self.blocks[index]['input'] = json.loads(raw) if raw.strip() else {}
                except ValueError:  # a tool's input that does not parse is sent as empty, and the tool says what is missing
                    log.warning('A streamed tool input did not parse (%d characters); sent as empty.', len(raw))
                    self.blocks[index]['input'] = {}
        elif kind == 'message_delta':
            delta = data.get('delta') or {}
            for key in ('stop_reason', 'stop_sequence', 'stop_details'):
                if key in delta:
                    self.message[key] = delta[key]
            if data.get('usage'):
                self.message['usage'] = {**(self.message.get('usage') or {}), **data['usage']}
        elif kind == 'error':
            error = data.get('error') or {}
            raise DossierUnavailable(f"The research service stopped the reply ({error.get('type', 'error')}). {str(error.get('message', ''))[:200]}".strip())
        if self.listener is not None:
            # A listener only updates what the screen shows: its failure is logged and never stops a paid reply.
            try:
                self.listener(kind, {**data, '_block': self.blocks.get(data.get('index')) if 'index' in data else None})
            except Exception:  # noqa: BLE001
                log.exception('The research chat could not show a streamed event.')

    def result(self) -> dict[str, Any]:
        return {**self.message, 'content': [self.blocks[i] for i in sorted(self.blocks)]}


def events(lines) -> Any:
    """Server-sent events: (event name, data) for each event in a stream of lines."""
    name, data = '', []
    for line in lines:
        if line == '':
            if data:
                yield name, json.loads('\n'.join(data))
            name, data = '', []
        elif line.startswith('event:'):
            name = line[6:].strip()
        elif line.startswith('data:'):
            data.append(line[5:].strip())
    if data:
        yield name, json.loads('\n'.join(data))


def anthropic_stream(api_key: str, timeout: float = 600) -> Callable[..., dict[str, Any]]:
    def post(payload: dict[str, Any], listener: Listener | None = None) -> dict[str, Any]:
        assembler = Assembler(listener)
        headers = {'x-api-key': api_key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}
        try:
            with httpx.stream('POST', URL, json={**payload, 'stream': True}, headers=headers, timeout=httpx.Timeout(timeout, connect=20),
                              follow_redirects=False) as response:
                if response.status_code >= 400:
                    response.read()
                    detail = ''
                    try:
                        detail = str(response.json().get('error', {}).get('message', ''))[:300]
                    except ValueError:
                        pass
                    raise DossierUnavailable(f'The research service returned an error ({response.status_code}). {detail}'.strip())
                for name, data in events(response.iter_lines()):
                    if name == 'ping' or data.get('type') == 'ping':
                        continue
                    assembler.feed(data.get('type') or name, data)
        except httpx.HTTPError as exc:
            raise DossierUnavailable(f'The research service could not be reached, or the connection dropped ({type(exc).__name__}). Try again shortly.') from exc
        return assembler.result()
    return post
