"""LLM providers (standard library HTTP) plus a deterministic offline mock for demos and CI."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Protocol


class LLM(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str: ...


def _post(url: str, headers: dict, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=120) as res:
        return json.loads(res.read())


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, key: str, model: str):
        self.key, self.model = key, model

    def complete(self, system: str, user: str) -> str:
        data = _post(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": self.key, "anthropic-version": "2023-06-01"},
            {"model": self.model, "max_tokens": 1024, "system": system, "messages": [{"role": "user", "content": user}]},
        )
        return "".join(b.get("text", "") for b in data["content"])


class OpenAILLM:
    name = "openai"

    def __init__(self, key: str, model: str):
        self.key, self.model = key, model

    def complete(self, system: str, user: str) -> str:
        data = _post(
            "https://api.openai.com/v1/chat/completions",
            {"authorization": f"Bearer {self.key}"},
            {"model": self.model, "temperature": 0, "response_format": {"type": "json_object"},
             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
        )
        return data["choices"][0]["message"]["content"]


_WORD = re.compile(r"[a-z0-9]+")


def _words(s: str) -> set[str]:
    return set(_WORD.findall(s.lower()))


class MockLLM:
    """
    Offline stand-in. For healing it picks the element whose label best matches the description.
    For exploration it follows simple tester heuristics: fill empty fields from test data, submit
    what was just typed, otherwise tap the control that best matches the goal and was not tapped yet.
    """

    name = "mock"

    def complete(self, system: str, user: str) -> str:
        return self._heal(user) if "TASK: HEAL" in user else self._explore(user)

    @staticmethod
    def _lines(user: str) -> list[tuple[int, str]]:
        return [(int(m.group(1)), m.group(2)) for m in re.finditer(r"^\[(\d+)\] (.+)$", user, re.M)]

    def _heal(self, user: str) -> str:
        want = _words(re.search(r"DESCRIPTION: (.+)", user).group(1))
        # compare only what a user sees or hears (text, accessibility label, hint), not ids
        visible = lambda line: _words(" ".join(re.findall(r'="([^"]*)"', line)))  # noqa: E731
        best = max(self._lines(user), key=lambda e: len(want & visible(e[1])), default=(-1, ""))
        return json.dumps({"index": best[0] if want & visible(best[1]) else -1})

    def _explore(self, user: str) -> str:
        goal = _words(re.search(r"GOAL: (.+)", user).group(1))
        data = json.loads(re.search(r"TEST DATA: (.+)", user).group(1))
        history = re.search(r"HISTORY:\n(.*?)SCREEN:", user, re.S).group(1)
        last = history.strip().splitlines()[-1] if history.strip() else ""
        elements = self._lines(user)

        # 1. fill empty editable fields from test data
        for idx, line in elements:
            if "editable" in line and 'text="' not in line:
                for key, value in data.items():
                    # credentials are always needed; other data only when the goal asks for it
                    relevant = key.lower() in ("email", "username", "password") or key.lower() in goal
                    if relevant and key.lower() in line.lower() and f"typed {key}" not in history:
                        return json.dumps({"action": "type", "index": idx, "text": value, "data_key": key,
                                           "reason": f"fill {key} from test data"})
        # 2. submit what was just typed: tap the next tappable control after the last field
        if last.startswith("typed"):
            field_idx = max((i for i, l in elements if "editable" in l and 'text="' in l), default=-1)
            for idx, line in elements:
                if idx > field_idx and "tappable" in line:
                    return json.dumps({"action": "tap", "index": idx, "reason": "submit the field just filled"})
        # 3. tap the untapped control that best matches the goal
        scored = []
        for idx, line in elements:
            if "tappable" not in line:
                continue
            label = re.sub(r"\(\d+\)", "", line)
            if f'tapped "{label}"' in history:
                continue
            scored.append((len(goal & _words(label)), -idx, idx, label))
        if scored and max(scored)[0] > 0:
            _, _, idx, label = max(scored)
            name = re.search(r'(?:a11y|text)="([^"]*)"', label)
            return json.dumps({"action": "tap", "index": idx, "reason": f"matches the goal: {name.group(1).strip() if name else label}"})
        return json.dumps({"action": "give_up", "reason": "no control on this screen moves toward the goal"})


def get_llm() -> LLM:
    choice = os.environ.get("LLM_PROVIDER", "mock").lower()
    if choice == "anthropic":
        return AnthropicLLM(os.environ["ANTHROPIC_API_KEY"], os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"))
    if choice == "openai":
        return OpenAILLM(os.environ["OPENAI_API_KEY"], os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    return MockLLM()


def extract_json(text: str) -> dict:
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        raise ValueError(f"No JSON in model reply: {text[:200]}")
    return json.loads(text[s : e + 1])
