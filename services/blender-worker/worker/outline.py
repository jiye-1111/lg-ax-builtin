"""바닥 모양: 벽들 가운데 집 바깥을 한 바퀴 도는 선을 찾는다.

벽 끝이 조금 떨어져 있어도(TOL 이내) 이어진 것으로 본다. 방 안쪽 벽, 끝이 떠 있는 벽은 뺀다.
벽이 한 바퀴 이어지지 않으면 None (그때는 예전처럼 네모 바닥을 쓴다).
"""
from __future__ import annotations

import math

TOL = 0.15          # 이만큼 떨어진 벽 끝은 같은 모서리로 본다 (m)
MIN_AREA = 1.0      # 이보다 작은 고리는 방이 아니다 (m²)
RECT_FILL = 0.97    # 감싸는 네모의 이만큼을 채우면 네모로 본다


def _nodes_and_edges(walls, tol):
    nodes: list[tuple[float, float]] = []

    def nid(p) -> int:
        for i, q in enumerate(nodes):
            if math.hypot(p[0] - q[0], p[1] - q[1]) <= tol:
                return i
        nodes.append((float(p[0]), float(p[1])))
        return len(nodes) - 1

    raw = [(nid(w.start), nid(w.end)) for w in walls]
    edges: set[tuple[int, int]] = set()
    for a, b in raw:
        if a == b:
            continue
        ax, ay = nodes[a]
        dx, dy = nodes[b][0] - ax, nodes[b][1] - ay
        L2 = dx * dx + dy * dy
        on = []  # 이 벽 중간에 붙은 다른 벽 끝: 거기서 벽을 나눈다
        for c, (cx, cy) in enumerate(nodes):
            if c in (a, b):
                continue
            t = ((cx - ax) * dx + (cy - ay) * dy) / L2
            if 0 < t < 1 and math.hypot(ax + t * dx - cx, ay + t * dy - cy) <= tol:
                on.append((t, c))
        chain = [a, *[c for _, c in sorted(on)], b]
        edges.update((min(u, v), max(u, v)) for u, v in zip(chain, chain[1:]) if u != v)
    return nodes, edges


def _prune(edges):
    """끝이 떠 있는 벽을 없어질 때까지 뗀다"""
    adj: dict[int, set[int]] = {}
    for u, v in edges:
        adj.setdefault(u, set()).add(v)
        adj.setdefault(v, set()).add(u)
    loose = [n for n, nb in adj.items() if len(nb) < 2]
    while loose:
        n = loose.pop()
        for m in adj.pop(n, ()):
            adj[m].discard(n)
            if len(adj[m]) < 2:
                loose.append(m)
    return adj


def floor_outline(walls, tol: float = TOL) -> list[tuple[float, float]] | None:
    nodes, edges = _nodes_and_edges(list(walls), tol)
    adj = _prune(edges)
    if len(adj) < 3:
        return None
    start = min(adj, key=lambda n: nodes[n])  # 가장 왼쪽(같으면 아래): 반드시 바깥 선 위에 있다
    back = math.pi                             # 왼쪽 바깥에서 들어왔다고 치고 돈다

    def turn(v, back_angle):
        def ccw(w):
            a = math.atan2(nodes[w][1] - nodes[v][1], nodes[w][0] - nodes[v][0])
            return (a - back_angle) % (2 * math.pi) or 2 * math.pi
        return min(adj[v], key=ccw)

    path, v = [start], start
    nxt = first = turn(start, back)
    for _ in range(4 * len(edges) + 4):
        back = math.atan2(nodes[v][1] - nodes[nxt][1], nodes[v][0] - nodes[nxt][0])
        v, nxt = nxt, turn(nxt, back)
        if v == start and nxt == first:
            break
        path.append(v)
    else:
        return None
    pts = [nodes[i] for i in path]
    pts = [p for i, p in enumerate(pts) if abs(_cross(pts[i - 1], p, pts[(i + 1) % len(pts)])) > 1e-6]
    return pts if len(pts) >= 3 and _area(pts) >= MIN_AREA else None


def _cross(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])


def _area(pts) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2


def is_rectangle(pts) -> bool:
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    box = (max(xs) - min(xs)) * (max(ys) - min(ys))
    return box > 0 and _area(pts) >= RECT_FILL * box
