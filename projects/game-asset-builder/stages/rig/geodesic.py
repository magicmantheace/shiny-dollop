"""Surface (graph-geodesic) distances for the skinning stack.

Pure Python + numpy — no Blender imports — so the rig's distance
decisions are unit-testable without a Blender runtime.

WHY: the weight-distance veto (skin_policy.apply_veto) restrains
bone-heat weights with straight-line (Euclidean) distance to a bone
segment. That leaks across a narrow web: a chest vertex sitting just
beside a raised arm is Euclidean-close to the arm segment even though
the surface path from that vertex to the arm runs all the way around
the armpit — so at a 2.2 rad wave it still sails the flank. Measuring
over the mesh surface catches that class: only flesh that is actually
connected to the bone's own region through the surface counts as
near it.

HOW THE RIG COMBINES THE TWO (measured, not assumed): the veto
compares the reach radius against max(Euclidean, geodesic) — a
vertex must be near in BOTH senses to keep an appendage's weight.
Geodesic alone was tried first on the Snow Goblin and made the
torso arm share WORSE (0.268, gate-rejected, vs the Euclidean
veto's 0.139): an arm's seed sleeve spreads over the flank the arm
hangs against, and that flank is surface-near the arm while being
straight-line-far from its segment. Each metric has a blind spot
the other covers; the union is the shipped semantics.

WHAT "geodesic" means here: the shortest path over the mesh's edge
graph, edge-weighted by Euclidean edge length. It is a graph
approximation of true surface distance, not an exact geodesic solve
(no sparse solver is available for a 50k-vert mesh in this codebase).
On a dense triangle mesh the approximation is close, and — unlike an
exact solve — it is deterministic, dependency-free, and fast enough
to run per bone inside the rig stage. The docstring says
graph-geodesic everywhere so the claim is never overstated.

SEEDS: a bone's distance field starts from the vertices that are
genuinely the bone's own flesh — vertices within ``seed_frac``
times the bone's own LENGTH of its segment, AND whose nearest bone
(Euclidean) is that bone. The sleeve scales with the bone, not with
the veto's reach radius: a vertex across a web or fold can be
Euclidean-close to the segment without being its flesh (that is the
whole defect class), and a sleeve tied to the reach radius balloons
across exactly those folds whenever the radius is generous. Half a
bone length is roughly the appendage's own radius — flesh actually
wrapped on the bone. A vertex sitting beside the shaft of a
*neighbouring* bone is not a seed for this one. A bone that somehow
has no seeds (its segment lies in a hollow) falls back to its 8
nearest vertices, so the field is always defined.

CAPPING: the veto only needs to know whether a vertex is within a
bone's reach radius or beyond it, so each bone's Dijkstra run stops
once the frontier exceeds that radius. Unreached vertices report
``inf`` — which is exactly "beyond reach" for the veto, and also
marks genuinely disconnected shells (debris that survived cleanup)
as unreachable rather than silently assigning them a small number.
"""

import heapq

import numpy as np


def segment_distances(heads, tails, verts):
    """(verts x bones) Euclidean distance from each vertex to each
    bone segment. Mirrors rig_blender._segment_distances; duplicated
    here because rig_blender.py imports bpy and cannot be imported
    by the unit tests."""
    heads = np.asarray(heads, dtype=np.float64)
    tails = np.asarray(tails, dtype=np.float64)
    seg = tails - heads
    seg_len2 = (seg ** 2).sum(axis=1)
    seg_len2 = np.where(seg_len2 < 1e-12, 1e-12, seg_len2)
    t = np.zeros((len(verts), len(heads)))
    for i in range(len(heads)):
        t[:, i] = ((verts - heads[i]) * seg[i]).sum(axis=1) / seg_len2[i]
    t = np.clip(t, 0.0, 1.0)
    closest = heads[None, :, :] + t[:, :, None] * seg[None, :, :]
    return np.linalg.norm(verts[:, None, :] - closest, axis=2)


def build_graph(verts, faces):
    """Adjacency of the mesh: a list, per vertex, of
    [(neighbour_index, edge_length), ...]. Duplicate edges are
    collapsed; isolated vertices get an empty list. ``verts`` is
    (n, 3), ``faces`` is (m, 3). Edge extraction and lengths are
    numpy-vectorized — the per-vertex lists are the only Python-level
    loop, and they iterate the UNIQUE edges (~1.5 per face), which
    keeps a 100k-face mesh at about a second."""
    verts = np.asarray(verts, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    edges = faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2)
    edges = np.unique(np.sort(edges, axis=1), axis=0)
    edges = edges[edges[:, 0] != edges[:, 1]]
    lengths = np.linalg.norm(verts[edges[:, 0]] - verts[edges[:, 1]],
                             axis=1)
    adj = [[] for _ in range(len(verts))]
    for (u, v), w in zip(edges, lengths):
        adj[u].append((int(v), float(w)))
        adj[v].append((int(u), float(w)))
    return adj


def dijkstra_capped(adj, seeds, cap):
    """Shortest graph distances from any seed vertex, capped at
    ``cap``: vertices farther than the cap (or unreachable) report
    ``inf``. The search stops as soon as the heap's smallest entry
    exceeds the cap, so a small radius only explores a local patch.
    ``seeds`` is an iterable of vertex indices; ``adj`` is the output
    of build_graph."""
    dist = np.full(len(adj), np.inf)
    heap = []
    for s in seeds:
        if dist[s] > 0.0:
            dist[s] = 0.0
            heapq.heappush(heap, (0.0, int(s)))
    while heap:
        d, u = heapq.heappop(heap)
        if d > cap:
            break
        if d != dist[u]:
            continue
        for v, w in adj[u]:
            nd = d + w
            if nd < dist[v] and nd <= cap:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist


def geodesic_distance_matrix(verts, faces, heads, tails, radii,
                              seed_frac=0.5, fallback_k=8):
    """(verts x bones) graph-geodesic distance from each vertex to
    each bone's seed set (see the module docstring), capped per bone
    at ``radii``. ``radii`` is the per-bone reach radius — the same
    radius the veto uses, so entries are directly comparable to it:
    a vertex with geodesic distance > radius is beyond reach. The
    seed sleeve is ``seed_frac`` times each bone's own length.

    Returns a float array with ``inf`` for unreached vertices."""
    verts = np.asarray(verts, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    euclid = segment_distances(heads, tails, verts)
    nearest = np.argmin(euclid, axis=1)
    adj = build_graph(verts, faces)
    lengths = np.linalg.norm(
        np.asarray(tails, dtype=np.float64)
        - np.asarray(heads, dtype=np.float64), axis=1)
    out = np.full((len(verts), len(heads)), np.inf)
    for b in range(len(heads)):
        sleeve = seed_frac * max(lengths[b], 1e-6)
        seeds = [int(v) for v in range(len(verts))
                 if nearest[v] == b and euclid[v, b] <= sleeve]
        if not seeds:
            seeds = [int(v) for v in
                     np.argsort(euclid[:, b])[:fallback_k]]
        out[:, b] = dijkstra_capped(adj, seeds, float(radii[b]))
    return out
