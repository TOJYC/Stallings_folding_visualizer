"""Core Stallings folding algorithm for free-group subgroups.

This module is independent of the browser UI. It uses plain Python data
structures and returns JSON-compatible graph snapshots for each fold.
"""

from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from typing import Any

MAX_FOLDS = 20_000


class InputError(ValueError):
    """A user-facing validation or algorithm-limit error."""

    def __init__(self, key: str, **details: Any) -> None:
        super().__init__(key)
        self.key = key
        self.details = details


def parse_word(raw: str, rank: int) -> list[dict[str, int]]:
    """Parse one word; each letter is represented by generator index and sign."""
    s = re.sub(r"\s+", "", raw)
    if not s or s == "1":
        return []

    word: list[dict[str, int]] = []
    i = 0

    while i < len(s):
        ch = s[i]
        sign = 1

        if ch in ("x", "X") and i + 1 < len(s) and s[i + 1].isdigit() and s[i + 1].isascii():
            j = i + 1
            while j < len(s) and s[j].isdigit() and s[j].isascii():
                j += 1
            g = int(s[i + 1 : j]) - 1
            if g < 0 or g > 9_007_199_254_740_991:
                raise InputError("invalidGen", raw=raw)
            if ch == "X":
                sign = -1
            i = j
        elif ch.isascii() and ch.isalpha():
            g = ord(ch.lower()) - ord("a")
            if ch != ch.lower():
                sign = -1
            i += 1
        else:
            raise InputError("invalidChar", raw=raw, ch=ch)

        suffix = 0
        if s.startswith("^{-1}", i):
            suffix = 5
        elif s.startswith("^-1", i):
            suffix = 3
        elif s.startswith("⁻¹", i):
            suffix = 2

        if suffix:
            sign *= -1
            i += suffix

        if g >= rank:
            raise InputError("generatorOutOfRange", raw=raw, g=g + 1, n=rank)

        word.append({"g": g, "s": sign})

    return word


def freely_reduce(word: list[dict[str, int]]) -> list[dict[str, int]]:
    """Reduce adjacent inverse letters using a stack."""
    out: list[dict[str, int]] = []
    for token in word:
        last = out[-1] if out else None
        if last and last["g"] == token["g"] and last["s"] == -token["s"]:
            out.pop()
        else:
            out.append(dict(token))
    return out


def build_initial_graph(words: list[list[dict[str, int]]]) -> dict[str, Any]:
    """Build the rose R_k with one petal for each input word."""
    graph: dict[str, Any] = {"base": 0, "vertices": [0], "edges": [], "petals": []}
    next_vertex = 1
    next_edge = 0

    for petal_index, word in enumerate(words):
        cur = graph["base"]
        path_vertices = [cur]
        path_edges: list[int] = []

        for i, token in enumerate(word):
            dest = graph["base"] if i == len(word) - 1 else next_vertex
            if dest != graph["base"]:
                graph["vertices"].append(dest)
                next_vertex += 1

            edge: dict[str, int] = {
                "id": next_edge,
                "label": token["g"],
                "petal": petal_index,
                "position": i,
                "wordSign": token["s"],
                "wordLength": len(word),
            }
            next_edge += 1

            # Orient every edge by its positive generator label.
            if token["s"] > 0:
                edge["u"], edge["v"] = cur, dest
            else:
                edge["u"], edge["v"] = dest, cur

            graph["edges"].append(edge)
            path_edges.append(edge["id"])
            path_vertices.append(dest)
            cur = dest

        graph["petals"].append(
            {
                "index": petal_index,
                "vertices": path_vertices,
                "edges": path_edges,
                "length": len(word),
            }
        )

    return graph


def find_fold(graph: dict[str, Any]) -> dict[str, int] | None:
    """Return the first deterministic pair of equally labelled directed edges."""
    at: dict[int, dict[tuple[int, int], list[dict[str, int]]]] = {
        v: {} for v in graph["vertices"]
    }

    def add(vertex: int, label: int, sign: int, edge: dict[str, int]) -> None:
        key = (label, sign)
        at[vertex].setdefault(key, []).append(edge)

    for edge in graph["edges"]:
        add(edge["u"], edge["label"], 1, edge)
        add(edge["v"], edge["label"], -1, edge)

    for vertex in graph["vertices"]:
        keys = sorted(at[vertex], key=lambda key: (key[0], 0 if key[1] == 1 else 1))
        for label, sign in keys:
            outgoing = at[vertex][(label, sign)]
            if len(outgoing) < 2:
                continue
            e1, e2 = outgoing[0], outgoing[1]
            return {
                "vertex": vertex,
                "label": label,
                "sign": sign,
                "e1": e1["id"],
                "e2": e2["id"],
                "t1": e1["v"] if sign > 0 else e1["u"],
                "t2": e2["v"] if sign > 0 else e2["u"],
            }

    return None


def fold_once(graph: dict[str, Any], fold: dict[str, int]) -> tuple[dict[str, Any], int | None, int | None]:
    """Apply one fold, keeping vertex and edge identities deterministic."""
    new_graph = deepcopy(graph)
    keep: int | None = None
    remove: int | None = None

    if fold["t1"] != fold["t2"]:
        t1, t2 = fold["t1"], fold["t2"]
        if t1 == new_graph["base"] or t2 == new_graph["base"]:
            keep = new_graph["base"]
            remove = t2 if t1 == new_graph["base"] else t1
        else:
            keep = min(t1, t2)
            remove = max(t1, t2)

        for edge in new_graph["edges"]:
            if edge["u"] == remove:
                edge["u"] = keep
            if edge["v"] == remove:
                edge["v"] = keep
        new_graph["vertices"] = [v for v in new_graph["vertices"] if v != remove]

    # Identify the two equally labelled oriented edges, retaining e1.
    new_graph["edges"] = [edge for edge in new_graph["edges"] if edge["id"] != fold["e2"]]
    return new_graph, keep, remove


def get_steps(words: list[list[dict[str, int]]]) -> list[dict[str, Any]]:
    """Return every graph state and the fold metadata connecting adjacent states."""
    graph = build_initial_graph(words)
    steps: list[dict[str, Any]] = [{"graph": deepcopy(graph), "foldFromPrevious": None}]
    count = 0

    while True:
        fold = find_fold(graph)
        if fold is None:
            break

        graph, keep, remove = fold_once(graph, fold)
        count += 1
        steps.append(
            {
                "graph": deepcopy(graph),
                "foldFromPrevious": {**fold, "keep": keep, "remove": remove},
            }
        )

        if count > MAX_FOLDS:
            raise InputError("tooManyFolds")

    return steps


def run_folding(rank: int, lines: list[str]) -> dict[str, Any]:
    """Validate input, reduce words, and run the full folding algorithm."""
    if (
        isinstance(rank, bool)
        or not isinstance(rank, (int, float))
        or not math.isfinite(rank)
        or not float(rank).is_integer()
        or not 1 <= rank <= 1000
    ):
        raise InputError("invalidRank")
    rank = int(rank)
    if not isinstance(lines, list) or any(not isinstance(line, str) for line in lines):
        raise InputError("invalidInput")

    raw_words = [parse_word(line, rank) for line in lines]
    reduced_words = [freely_reduce(word) for word in raw_words]
    steps = get_steps(reduced_words)
    return {
        "ok": True,
        "noGeneratorsEntered": len(lines) == 0,
        "reducedWords": reduced_words,
        "steps": steps,
    }


def run_folding_json(rank: int, lines_json: str) -> str:
    """JSON bridge used by JavaScript/Pyodide; errors are returned as data."""
    try:
        lines = json.loads(lines_json)
        result = run_folding(rank, lines)
    except InputError as exc:
        result = {"ok": False, "errorKey": exc.key, "errorVars": exc.details}
    except Exception as exc:  # Keep unexpected failures visible in the page.
        result = {
            "ok": False,
            "errorKey": "algorithmError",
            "errorVars": {"detail": f"{type(exc).__name__}: {exc}"},
        }
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
