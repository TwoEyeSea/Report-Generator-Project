"""Pure geometry for stratigraphy-column hatch fills.

No matplotlib import here -- each pattern's `generate()` takes the rectangle's
(width, height) plus an angle/size and returns a flat list of primitives
(LineSegment / Dot) already tiled and rotated in the rectangle's local
(0, 0)-(width, height) frame. Primitives are deliberately over-tiled past the
rectangle's edges; the caller (tp_drawer/drawing.py) clips them to the exact
band boundary when converting them to matplotlib artists, so no bounds
checking happens here.

`size` is a scale factor (roughly: spacing between repeats, in the same
inches used elsewhere in this project) -- larger size means a coarser,
more widely spaced pattern, mirroring AutoCAD's HPSCALE.

PLAIN-ENGLISH OVERVIEW:
Every soil symbol on the drawing (dots for sand, dashes for clay, circles
for gravel, and so on) is built from a small number of basic shapes --
LineSegment (a straight line), Dot (a filled or outline circle), and Blob
(an irregular closed outline). Think of these like Lego bricks: each
`_generate_xxx` function below is a recipe that scatters a bunch of these
bricks across a rectangle in some pattern, and drawing.py is what
actually paints them onto the page. Splitting "what shapes, where" (this
file) from "how do we draw a shape" (drawing.py) means this file can be
tested with plain numbers, and drawing.py doesn't need to know anything
about sand vs. clay vs. gravel -- it just draws whatever list of
LineSegment/Dot/Blob it's handed.

The trickiest part of this file by far is the gravel ("circles") pattern
-- see _pack_grains and _inject_perimeter_contacts below for a full
explanation, but in short: real gravel is made of stones of different
sizes touching each other, not a neat grid of identical dots, so that
pattern uses a small physics-like simulation (greedily dropping stones of
random sizes, biggest first, letting them bump up against whatever's
already there) to make something that reads as "real gravel" rather than
"a regular grid of circles".
"""

import math
import random
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class LineSegment:
    """A single straight line from (x1, y1) to (x2, y2), in the pattern's
    local coordinate frame (inches, with (0, 0) at the bottom-left corner
    of the rectangle being filled)."""

    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class Dot:
    """A circle of radius `r` centered at (cx, cy). `filled=True` draws a
    solid dot; `filled=False` draws just its outline -- used for the rare
    "hollow pebble" look mixed into the gravel pattern."""

    cx: float
    cy: float
    r: float
    filled: bool = True


@dataclass(frozen=True)
class Blob:
    """A closed, unfilled outline (irregular rounded polygon) -- used for the gravel/pebble pattern."""

    points: tuple[tuple[float, float], ...]


# ADVANCED TECHNIQUE -- a "union type" alias (the | symbol):
# `Primitive` isn't a class of its own -- it's just a short name that
# means "any one of LineSegment, Dot, or Blob". Writing `list[Primitive]`
# as a return type elsewhere in this file is shorthand for
# `list[LineSegment | Dot | Blob]`, so a function that returns a mix of
# different shape types (like _generate_circles, which returns both Dot
# and Blob objects) has one tidy type to declare instead of spelling the
# whole union out every time.
Primitive = LineSegment | Dot | Blob

# ADVANCED TECHNIQUE -- a fixed random seed:
# random.Random(_PATTERN_SEED) below produces a "random" sequence that
# looks unpredictable but is actually 100% reproducible -- the same seed
# number always produces the exact same sequence of "random" values,
# every time the program runs, on any machine. Without a fixed seed, the
# gravel pattern would look slightly different every single time the PDF
# was regenerated, which would make automated tests (which check for an
# exact expected result) fail randomly, and would make it impossible to
# tell whether a code change actually altered the pattern or you just got
# unlucky with a different random roll. Think of it like shuffling a deck
# of cards using a specific, repeatable shuffling recipe instead of just
# "randomly" -- follow the same recipe twice and you get the same order
# both times.
#
# Fixed seed for every randomized pattern (currently just "circles") -- keeps
# generate() a pure function of its (width, height, angle, size) inputs, so
# the same band renders identically every time and stays test-deterministic.
_PATTERN_SEED = 20240823

# How far a grain is allowed to push its boundary into a neighbor's boundary, as a fraction of
# the *larger* of the two grains' radii. A grain-supported fabric needs grains in genuine contact
# with each other, not separated by a fine matrix of ever-shrinking filler grains -- so packing
# permits a bounded amount of clipping between neighbors rather than forbidding it outright.
# Scaling by the larger radius (rather than a flat fraction of `spacing`) is what lets a large
# grain end up in contact with several neighbors around its bigger perimeter, instead of just
# whichever one happens to be nearest -- any candidate near a big already-placed grain inherits
# that grain's bigger overlap budget, not just its own.
_CONTACT_OVERLAP_FRACTION = 0.2

# Largest a single grain's *desired* radius can be, as a fraction of `spacing` -- the top tier of
# _pebble_radius. Also sizes the packer's spatial-hash buckets and bounds how far contact overlap
# can reach, so both stay correct if that tier's range is retuned.
_MAX_GRAIN_FRACTION = 0.6

# Radius (as a fraction of `spacing`) above which a placed grain counts as a "large" host for the
# perimeter-contact pass -- also the floor of _pebble_radius's large tier, so "large" means the
# same thing everywhere in this file.
_LARGE_GRAIN_THRESHOLD_FRACTION = 0.50

# Radius (as a fraction of `spacing`) below which a placed grain is skipped by the perimeter pass
# entirely. These are filler-tier grains that are already dense from the base grid pass; forcing
# 2-4 extra contacts onto thousands of them would cost far more render time than it's worth.
_PERIMETER_PASS_MIN_FRACTION = 0.25

# How close (as a fraction of `spacing`) an existing neighbor must already be to a host's boundary
# to count as "occupying" its angular sector in the perimeter pass -- close enough to touching that
# forcing another contact into the same sector would just be redundant clutter.
_OCCUPIED_SECTOR_MARGIN_FRACTION = 0.22

# How many buckets out (in each of the 4 grid directions) the spatial hash scans around a point.
# Fixed at 3 because bucket_size is tied to the largest possible grain radius (see _pack_grains),
# which guarantees the true nearest neighbor is always within this radius. Shared by the packer's
# nearest-neighbor search and the perimeter pass's occupied-sector scan via _nearby_grains, so
# retuning it can't leave one of the two out of sync with the other.
_BUCKET_SEARCH_RADIUS = 3


def _axes(angle: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """Unit vectors (u, v) for the tiling grid, u rotated by `angle` degrees, v perpendicular.

    A "unit vector" is just a direction with length exactly 1 -- e.g.
    (1, 0) points straight along the x-axis. u and v together define a
    little rotated coordinate system: normally you'd tile a pattern by
    stepping along the page's own x and y axes, but to support a
    user-chosen hatch angle (e.g. 45-degree cross-hatching), every
    pattern instead steps along u and v, which are the page's x/y axes
    rotated by `angle` degrees. v is built as (-sin, cos) rather than
    another cos/sin pair specifically so it's always exactly 90 degrees
    (perpendicular) from u, whatever angle is chosen -- like a compass
    where "east" and "north" always stay at a right angle to each other
    even as you rotate the whole compass face.
    """
    rad = math.radians(angle)
    u = (math.cos(rad), math.sin(rad))
    v = (-math.sin(rad), math.cos(rad))
    return u, v


def _grid_centers(width: float, height: float, spacing: float, u, v) -> list[tuple[float, float]]:
    """Grid points spaced `spacing` apart along (u, v), covering (width, height) plus a safety margin.

    Builds a regular lattice of points -- like graph paper -- but along
    the rotated (u, v) axes from _axes() instead of the page's own x/y,
    so the resulting grid can sit at any angle. i and j here play the
    role of "how many steps along u" and "how many steps along v" from
    the rectangle's center. The `+ 2` margin and the `half_diag`
    (half of the rectangle's corner-to-corner diagonal) generate more
    points than strictly needed to cover (width, height) -- deliberately
    over-tiling past the true edges, since a rotated pattern's own grid
    doesn't line up neatly with the rectangle's straight edges, and the
    caller in drawing.py clips away anything that spills outside the
    band's actual boundary anyway.
    """
    if spacing <= 0:
        return []
    cx, cy = width / 2, height / 2
    half_diag = math.hypot(width, height) / 2
    n = int(half_diag / spacing) + 2
    centers = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x = cx + i * spacing * u[0] + j * spacing * v[0]
            y = cy + i * spacing * u[1] + j * spacing * v[1]
            centers.append((x, y))
    return centers


def _row_centers(width: float, height: float, row_spacing: float, u, v) -> list[tuple[float, float]]:
    """Points spaced `row_spacing` apart along v only (one point per row, at the row's u=0 crossing);
    the caller extends each into a full-width segment along u.

    This is the "one point per row" half of building a set of full-width
    stripes (used by dashes, cross-hatch, and brick below): first find
    where each row crosses the rectangle's center line (this function),
    then in a second step stretch each of those points into a full line
    running the whole width of the rectangle along u
    (_full_span_segments below does that second step)."""
    if row_spacing <= 0:
        return []
    cx, cy = width / 2, height / 2
    half_diag = math.hypot(width, height) / 2
    n = int(half_diag / row_spacing) + 2
    return [(cx + j * row_spacing * v[0], cy + j * row_spacing * v[1]) for j in range(-n, n + 1)]


def _full_span_segments(width: float, height: float, row_centers, u) -> list[LineSegment]:
    """Turn each (x, y) row-center point into one long LineSegment running
    the full width of the rectangle along direction u -- generously
    over-length (`+ max(width, height)`) so it's guaranteed to reach both
    edges even at an angle, then gets clipped down to the real rectangle
    boundary later by drawing.py."""
    half_len = math.hypot(width, height) / 2 + max(width, height)
    segments = []
    for x, y in row_centers:
        segments.append(
            LineSegment(x - half_len * u[0], y - half_len * u[1], x + half_len * u[0], y + half_len * u[1])
        )
    return segments


def _generate_none(width: float, height: float, angle: float, size: float) -> list[Primitive]:
    """The "no fill" pattern -- just an empty list of shapes, so the layer
    draws as a plain outlined rectangle with no hatching at all (today's
    default look for any unit without a catalog entry)."""
    return []


def _generate_dots(width: float, height: float, angle: float, size: float) -> list[Primitive]:
    """Sand/silt symbol: small solid dots on a regular rotated grid."""
    spacing = max(size, 0.2) * 0.18
    u, v = _axes(angle)
    radius = spacing * 0.05
    return [Dot(x, y, radius, filled=True) for x, y in _grid_centers(width, height, spacing, u, v)]


def _angular_polygon(cx: float, cy: float, radius: float, rng: random.Random) -> Blob:
    """An irregular, angular polygon outline -- a faceted rock fragment, not a smooth pebble.
    Vertices never exceed `radius` from (cx, cy), so the shape stays within its packing circle.

    Picks a random number of corners (5 to 12), spaces them evenly around
    a full circle (2*pi radians = 360 degrees), then nudges each corner's
    *distance* from the center by a random amount (rng.uniform(0.5, 1.0)
    times radius) -- so the corners stay evenly spread around the circle
    (no two corners bunched together), but the shape's edge wobbles
    in and out unevenly, giving it a jagged, rock-like silhouette instead
    of a perfect circle or regular polygon."""
    n_sides = rng.randint(5, 12)
    start = rng.uniform(0, 2 * math.pi)
    points = []
    for k in range(n_sides):
        theta = start + 2 * math.pi * k / n_sides
        r = radius * rng.uniform(0.5, 1.0)
        points.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
    return Blob(tuple(points))


def _pebble_radius(spacing: float, rng: random.Random) -> float:
    """Bimodal-ish size mix (mostly medium grains, a few large ones, a few small fillers) --
    matches a real gravel symbol's variety better than a single uniform radius range. This is
    the *desired* radius before packing shrinks it to whatever room a grain's neighbors leave.

    rng.random() rolls a "die" between 0.0 and 1.0. Splitting that single
    roll into three ranges (below 0.15, 0.15-0.8, above 0.8) is how this
    function makes some sizes much rarer than others without needing
    three separate random calls: a 0.05 roll (15% chance) means "big
    grain", a 0.5 roll (65% chance, the 0.15-0.8 gap) means "medium
    grain", and a 0.9 roll (20% chance) means "small filler grain". This
    mirrors how a real handful of gravel looks -- mostly middling stones,
    a few standout large ones, and some small chips filling gaps."""
    roll = rng.random()
    if roll < 0.15:
        return spacing * rng.uniform(_LARGE_GRAIN_THRESHOLD_FRACTION, _MAX_GRAIN_FRACTION)
    if roll < 0.8:
        return spacing * rng.uniform(0.32, 0.45)
    return spacing * rng.uniform(0.2, 0.36)


# ADVANCED TECHNIQUE -- spatial hashing (the "buckets" dict below):
# The gravel pattern can place thousands of grains in one soil layer, and
# for every new candidate grain, the code needs to know "what are the
# grains closest to this point?" so it can figure out how much room is
# left. Checking a new candidate against *every* grain placed so far
# would get very slow as the grain count grows (the classic beginner
# approach, but it's what's called an O(n^2) algorithm -- if you double
# the number of grains, the work roughly quadruples).
#
# Spatial hashing fixes this by dividing the whole rectangle into a grid
# of square "buckets" (like the pigeonholes in a mail sorting room, or
# the squares on a chessboard), and only ever storing each grain in the
# one bucket its center falls into. Then, to find grains *near* some
# point, you only need to look inside that point's own bucket and a
# small fixed ring of neighboring buckets (see _BUCKET_SEARCH_RADIUS
# above) -- never the whole rectangle. Because bucket_size (set in
# _pack_grains below) is deliberately chosen to be at least as big as the
# largest grain that could ever be placed, checking `_BUCKET_SEARCH_RADIUS`
# buckets out is mathematically guaranteed to find every grain that could
# possibly be close enough to matter, however many thousand other grains
# exist far away elsewhere in the rectangle.
def _nearby_grains(
    bi: int, bj: int, buckets: dict[tuple[int, int], list[tuple[float, float, float]]]
):
    """Every already-placed grain in the fixed `_BUCKET_SEARCH_RADIUS`-bucket neighborhood around
    bucket (bi, bj). Shared by the nearest-neighbor gap search and the perimeter pass's
    occupied-sector scan so both always agree on how far out they're searching.

    ADVANCED TECHNIQUE -- this is a generator, not a normal function:
    Notice it uses `yield from` instead of `return`. A normal function
    computes its whole result and hands it back in one go; a *generator*
    (any function containing `yield`) instead hands back its results one
    at a time, on demand, as whoever's using it asks for the next one
    (e.g. in a `for grain in _nearby_grains(...):` loop). The advantage
    here is that it never needs to build one big combined list of every
    nearby grain in memory before the caller can start using them -- it
    just streams them out bucket by bucket. `yield from buckets.get(...)`
    means "yield every item from this bucket's list, one by one, then
    move on to the next di/dj pair" -- a shorthand for a small yield loop.
    """
    for di in range(-_BUCKET_SEARCH_RADIUS, _BUCKET_SEARCH_RADIUS + 1):
        for dj in range(-_BUCKET_SEARCH_RADIUS, _BUCKET_SEARCH_RADIUS + 1):
            yield from buckets.get((bi + di, bj + dj), ())


def _try_place(
    gx: float,
    gy: float,
    desired: float,
    buckets: dict[tuple[int, int], list[tuple[float, float, float]]],
    bucket_of: Callable[[float, float], tuple[int, int]],
    nearest_gap: Callable[[float, float, float, int, int], float],
    min_radius: float,
) -> tuple[float, float, float] | None:
    """Caps `desired` to whatever room its neighbors leave and, if what's left clears
    `min_radius`, places the grain and registers it in the spatial hash; returns None if there's
    no room worth keeping. Shared by the main grid pass and the perimeter pass so both place and
    register grains the exact same way.

    Every possible grain in this file is tried through this one function
    -- it's the single "place a grain (or don't)" gatekeeper, which is
    what guarantees a grain from the initial grid pass and a grain from
    the later perimeter-contact pass (see _inject_perimeter_contacts)
    always play by exactly the same rules."""
    bi, bj = bucket_of(gx, gy)
    radius = min(desired, nearest_gap(gx, gy, desired, bi, bj))
    if radius <= min_radius:
        # Whatever room was actually available is too small to bother
        # drawing (it would be an invisible speck) -- reject the
        # candidate outright rather than placing a near-zero-size grain.
        return None
    grain = (gx, gy, radius)
    buckets.setdefault((bi, bj), []).append(grain)
    return grain


def _pack_grains(width: float, height: float, spacing: float, u, v, rng: random.Random) -> list[tuple[float, float, float]]:
    """Greedily places (x, y, radius) grains for a grain-supported fabric: each candidate's radius
    is capped by its nearest already-placed neighbor, but is allowed to push past the point of
    exact tangency by `_CONTACT_OVERLAP_FRACTION` of whichever grain in the pair is larger --
    producing genuine grain-to-grain contact (and a bounded amount of imperceptible-to-modest
    clipping) instead of the fractal cascade of near-zero filler grains a strict no-overlap cap
    forces into every gap.

    ADVANCED TECHNIQUE -- a "greedy" algorithm:
    This function decides where every grain goes with a strategy called
    "greedy": it processes candidates one at a time, in a chosen order
    (biggest first -- see the comment further down about why), and for
    each one just makes the locally-best decision available *right now*
    (how big can this grain be, given only the grains already placed) and
    then never revisits that decision. It never backtracks to say "actually,
    let me reconsider grain #12 now that I've placed grain #500" --
    that would be far more accurate but combinatorially expensive (like
    trying every possible arrangement of a jigsaw puzzle rather than just
    fitting each piece into wherever looks best right now). Greedy
    algorithms trade perfect optimality for speed, and here that trade is
    a good one: the result only has to *look* like a plausible pile of
    gravel, not be a physically perfect one."""
    # `cell` is a fine grid of *candidate* starting positions -- far more
    # candidates than will actually end up as grains, since most get
    # shrunk down to nothing or rejected outright once their neighbors
    # are already placed (see _try_place's min_radius check). Nudging
    # each candidate off the perfectly regular grid by a random amount
    # (jitter_u/jitter_v) is what stops the final gravel from having any
    # visible regular-grid structure -- an evenly-spaced starting grid
    # with no jitter would still look artificially uniform even after
    # the sizes and packing are randomized.
    cell = spacing * 0.1
    half_diag = math.hypot(width, height) / 2
    n = int(half_diag / cell) + 2
    cx, cy = width / 2, height / 2
    candidates = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            jitter_u = rng.uniform(-0.35, 0.35)
            jitter_v = rng.uniform(-0.35, 0.35)
            gx = cx + (i + jitter_u) * cell * u[0] + (j + jitter_v) * cell * v[0]
            gy = cy + (i + jitter_u) * cell * u[1] + (j + jitter_v) * cell * v[1]
            candidates.append((gx, gy))

    # Draw each candidate's desired size up front and place largest-first, rather than in random
    # shuffled order. Random order let small grains get placed early right next to where a big
    # grain would later land, "claiming" territory the big grain then had to shrink around --
    # leaving a visible avoidance halo. Largest-first means big grains always stake their space
    # before smaller candidates compete for the same neighborhood.
    sized_candidates = [(gx, gy, _pebble_radius(spacing, rng)) for gx, gy in candidates]
    # ADVANCED TECHNIQUE -- sorting with a `key` function:
    # sort()'s `key` argument tells Python *what to compare* rather than
    # comparing the tuples themselves directly. `lambda c: c[2]` is a tiny
    # unnamed function that, given one candidate tuple `c`, returns just
    # its radius (index 2 of the (gx, gy, radius) tuple) -- so this sorts
    # the whole list by radius alone, ignoring gx and gy. reverse=True
    # sorts biggest-radius-first instead of the default smallest-first.
    sized_candidates.sort(key=lambda c: c[2], reverse=True)

    min_radius = spacing * 0.1

    # Spatial hash: bucket already-placed grains by position so each new candidate only scans
    # nearby buckets instead of every previously placed grain (brute-force nearest-neighbor scan
    # is O(n^2) and became the packing bottleneck once `cell` got fine enough for grains to
    # actually touch). bucket_size is tied to the largest possible grain radius so
    # `_BUCKET_SEARCH_RADIUS` buckets out is always enough to find the true nearest neighbor. An
    # earlier "expanding rings" version (bucket_size tied to `cell` instead) was tried to allow a
    # smaller search radius, but benchmarked slower at this density -- ruling out a hypothetical
    # large grain via that approach's pruning bound needed many rings, since max_grain_radius stays
    # large relative to small buckets. This simpler fixed-neighborhood version won on speed.
    bucket_size = spacing * _MAX_GRAIN_FRACTION
    buckets: dict[tuple[int, int], list[tuple[float, float, float]]] = {}

    # ADVANCED TECHNIQUE -- floor division to find a bucket coordinate:
    # math.floor(x / bucket_size) turns a continuous position (x, in
    # inches) into a whole-number bucket index -- e.g. with bucket_size=1,
    # every x from 0.0 up to (but not including) 1.0 maps to bucket 0,
    # every x from 1.0 up to 2.0 maps to bucket 1, and so on. This is the
    # same idea as figuring out which street block an address falls on:
    # you don't care about the exact position within the block, just
    # which block it's in, so you can quickly narrow down what's nearby.
    def bucket_of(x: float, y: float) -> tuple[int, int]:
        return (math.floor(x / bucket_size), math.floor(y / bucket_size))

    # ADVANCED TECHNIQUE -- a nested "closure" function:
    # bucket_of and nearest_gap are defined *inside* _pack_grains, rather
    # than as their own top-level functions. That means they automatically
    # have access to _pack_grains's own local variables (bucket_size,
    # buckets) without needing those passed in as arguments every time --
    # a function defined like this, that "remembers" the variables from
    # the scope it was created in, is called a closure. It's used here
    # because bucket_of/nearest_gap are only ever meaningful paired with
    # one specific `buckets` dict and `bucket_size` -- tying them together
    # this way means there's no way to accidentally call nearest_gap with
    # a mismatched buckets dict from a different pattern.
    def nearest_gap(gx: float, gy: float, desired: float, bi: int, bj: int) -> float:
        best = math.inf
        for px, py, pr in _nearby_grains(bi, bj, buckets):
            # Overlap budget scales with whichever grain in the pair is larger -- an
            # already-placed big neighbor lends *any* nearby candidate its bigger reach, which is
            # what lets a large grain end up in contact with several neighbors around its
            # perimeter rather than just whichever one happens to be nearest.
            allowance = max(desired, pr) * _CONTACT_OVERLAP_FRACTION
            gap_here = math.hypot(gx - px, gy - py) - pr + allowance
            if gap_here < best:
                best = gap_here
        return best

    placed: list[tuple[float, float, float]] = []
    for gx, gy, desired in sized_candidates:
        grain = _try_place(gx, gy, desired, buckets, bucket_of, nearest_gap, min_radius)
        if grain is not None:
            placed.append(grain)

    # A second, separate pass over the grains this first pass produced --
    # see _inject_perimeter_contacts's own docstring below for why the
    # base grid pass above isn't enough on its own to look like natural
    # gravel.
    placed += _inject_perimeter_contacts(placed, spacing, buckets, bucket_of, nearest_gap, min_radius, rng)
    return placed


def _inject_perimeter_contacts(
    hosts: list[tuple[float, float, float]],
    spacing: float,
    buckets: dict[tuple[int, int], list[tuple[float, float, float]]],
    bucket_of: Callable[[float, float], tuple[int, int]],
    nearest_gap: Callable[[float, float, float, int, int], float],
    min_radius: float,
    rng: random.Random,
) -> list[tuple[float, float, float]]:
    """Second pass: gives sufficiently large grains contact points spread around their whole
    perimeter, instead of relying on the base grid pass to have happened to leave a candidate
    nearby in every direction (which is what produces the "networked, contacts strung along
    channels" look rather than a natural, even spread).

    The perimeter is divided into fixed sectors (4 quadrants of 90 deg for small hosts, 12 sectors
    of 30 deg grouped into those same 4 quadrants for large hosts), but which sectors actually get
    a contact -- and where within each chosen sector -- is randomized, so the result doesn't read
    as a rigid ring of evenly-spaced dots. Contact counts are distributed round-robin across the 4
    quadrants so a large host's contacts can't all end up polarized on one side.

    PLAIN-ENGLISH ANALOGY: imagine slicing each big grain's surrounding
    space like a pizza -- either into 4 big quarter-slices, or into 12
    thinner slices grouped 3-per-quarter. This function first works out
    which slices are already "taken" (a neighboring grain from the first
    pass already sits in that direction), then randomly picks a handful
    of the remaining empty slices -- spread evenly across all 4 quarters,
    not just wherever happened to be checked first -- and drops one new
    grain into each chosen slice, at a random angle and distance within
    that slice. That's what keeps the extra contact points looking
    scattered and natural instead of forming a perfectly even ring."""
    small_min = spacing * _PERIMETER_PASS_MIN_FRACTION
    large_min = spacing * _LARGE_GRAIN_THRESHOLD_FRACTION
    occupied_margin = spacing * _OCCUPIED_SECTOR_MARGIN_FRACTION

    injected: list[tuple[float, float, float]] = []
    # `hosts` is the full list of grains the base grid pass placed --
    # loop over every one of them and consider adding perimeter contacts
    # around it (most will be skipped by the `hr < small_min` check right
    # below, since only sufficiently large grains get this treatment).
    for hx, hy, hr in hosts:
        if hr < small_min:
            # This grain is small filler -- the base grid pass already
            # placed plenty of grains densely around it, so forcing extra
            # contacts here would just be wasted work with no visible
            # benefit.
            continue

        if hr >= large_min:
            n_sectors, sector_width, k_lo, k_hi = 12, 30.0, 6, 12
        else:
            n_sectors, sector_width, k_lo, k_hi = 4, 90.0, 2, 4
        sectors_per_quadrant = n_sectors // 4

        # First, figure out which angular slices around this host are
        # already occupied by an existing nearby grain -- theta is that
        # neighbor's compass-bearing-style angle from the host (in
        # degrees, 0-360), and `theta // sector_width` (integer/floor
        # division) turns that angle into "which numbered slice does it
        # fall in" -- e.g. with 90-degree slices, an angle of 200 degrees
        # falls in slice 2 (the third slice, since slice numbering starts
        # at 0).
        bi, bj = bucket_of(hx, hy)
        occupied_sectors = set()
        for px, py, pr in _nearby_grains(bi, bj, buckets):
            if px == hx and py == hy and pr == hr:
                # Don't count the host itself as its own neighbor.
                continue
            dist = math.hypot(px - hx, py - hy)
            if dist <= hr + pr + occupied_margin:
                theta = math.degrees(math.atan2(py - hy, px - hx)) % 360
                occupied_sectors.add(int(theta // sector_width))

        # Decide how many new contacts to try for (k), then distribute
        # that count across the 4 quadrants round-robin (via `counts`, and
        # a shuffled quadrant visiting order) so the contacts spread
        # around the whole grain rather than clustering in whichever
        # quadrant happened to be considered first.
        k = rng.randint(k_lo, k_hi)
        quadrant_order = list(range(4))
        rng.shuffle(quadrant_order)
        counts = [k // 4 + (1 if i < k % 4 else 0) for i in range(4)]

        chosen_sectors = []
        for qi, quadrant in enumerate(quadrant_order):
            base = quadrant * sectors_per_quadrant
            available = [base + s for s in range(sectors_per_quadrant) if (base + s) not in occupied_sectors]
            rng.shuffle(available)
            chosen_sectors += available[: counts[qi]]

        # Finally, actually try to place one grain in each chosen
        # sector -- at a random angle inside that sector's degree range,
        # positioned just outside the host's own edge so the new grain
        # touches it. Same _try_place gatekeeper as the base pass, so a
        # sector that turns out to have no real room left (a neighbor the
        # occupied-sector check missed) is silently skipped rather than
        # forcing an overlapping grain in.
        for sector in chosen_sectors:
            angle_lo = sector * sector_width
            theta = math.radians(rng.uniform(angle_lo, angle_lo + sector_width))
            desired = _pebble_radius(spacing, rng)
            gx = hx + (hr + desired) * math.cos(theta)
            gy = hy + (hr + desired) * math.sin(theta)
            grain = _try_place(gx, gy, desired, buckets, bucket_of, nearest_gap, min_radius)
            if grain is not None:
                injected.append(grain)

    return injected


def _generate_circles(width: float, height: float, angle: float, size: float) -> list[Primitive]:
    """Gravel: a tightly packed, grain-supported cluster of irregularly-sized grain outlines
    (mostly angular, some rounded) in direct contact with their neighbors -- rather than a
    uniform grid of identical circles, or a matrix of grains kept strictly apart."""
    spacing = max(size, 0.01) * 0.4
    u, v = _axes(angle)
    # Every draw of this pattern gets its own fresh random.Random seeded
    # the same way, rather than reusing one shared random number
    # generator across calls -- see the _PATTERN_SEED comment above for
    # why a fixed seed matters. Creating a new Random object here (as
    # opposed to using the plain `random` module's global functions like
    # random.random()) also means this pattern's randomness can never
    # accidentally interfere with randomness used somewhere else in the
    # program.
    rng = random.Random(_PATTERN_SEED)
    primitives: list[Primitive] = []
    for gx, gy, radius in _pack_grains(width, height, spacing, u, v, rng):
        if rng.random() < 0.01:
            # A rare (1%) hollow-circle grain mixed in among the mostly
            # angular ones -- a small visual variety touch, standing in
            # for the occasional smooth, rounded pebble you'd see among
            # otherwise angular gravel fragments.
            primitives.append(Dot(gx, gy, radius, filled=False))
        else:
            primitives.append(_angular_polygon(gx, gy, radius, rng))
    return primitives


def _generate_dashes(width: float, height: float, angle: float, size: float) -> list[Primitive]:
    """Clay symbol: short dashes in a brick-like offset grid (every other
    row is shifted sideways by half a dash-spacing, via `row_offset`
    below) so the dashes don't line up into obvious straight columns."""
    row_spacing = max(size, 0.01) * 0.22
    dash_spacing = row_spacing * 1.3
    dash_length = dash_spacing * 0.55
    u, v = _axes(angle)
    half_diag = math.hypot(width, height) / 2
    n_rows = int(half_diag / row_spacing) + 2
    n_cols = int(half_diag / dash_spacing) + 2
    cx, cy = width / 2, height / 2
    segments = []
    for j in range(-n_rows, n_rows + 1):
        row_offset = 0.0 if j % 2 == 0 else dash_spacing / 2
        for i in range(-n_cols, n_cols + 1):
            along = i * dash_spacing + row_offset
            x = cx + along * u[0] + j * row_spacing * v[0]
            y = cy + along * u[1] + j * row_spacing * v[1]
            hx, hy = (dash_length / 2) * u[0], (dash_length / 2) * u[1]
            segments.append(LineSegment(x - hx, y - hy, x + hx, y + hy))
    return segments


def _generate_cross_hatch(width: float, height: float, angle: float, size: float) -> list[Primitive]:
    """Fill/made-ground symbol: two full sets of parallel lines, one along
    (u, v) and a second along (v, u) -- i.e. the same set of stripes drawn
    twice, the second time rotated 90 degrees from the first, producing a
    criss-cross grid pattern."""
    spacing = max(size, 0.01) * 0.3
    u, v = _axes(angle)
    segments = _full_span_segments(width, height, _row_centers(width, height, spacing, u, v), u)
    segments += _full_span_segments(width, height, _row_centers(width, height, spacing, v, u), v)
    return segments


def _generate_organic(width: float, height: float, angle: float, size: float) -> list[Primitive]:
    """Peat/topsoil symbol: a small "+"-like tick mark (one short line
    along u, a shorter one along v) repeated at every point of a regular
    grid -- a common surveying/geology convention for organic material."""
    spacing = max(size, 0.01) * 0.32
    u, v = _axes(angle)
    tick = spacing * 0.4
    segments = []
    for x, y in _grid_centers(width, height, spacing, u, v):
        hx, hy = (tick / 2) * u[0], (tick / 2) * u[1]
        segments.append(LineSegment(x - hx, y - hy, x + hx, y + hy))
        vx, vy = (tick / 3) * v[0], (tick / 3) * v[1]
        segments.append(LineSegment(x - vx, y - vy, x + vx, y + vy))
    return segments


def _generate_brick(width: float, height: float, angle: float, size: float) -> list[Primitive]:
    """Weathered-rock symbol: horizontal courses (full-width lines, same
    idea as cross-hatch's rows) plus short vertical "mortar joint" ticks
    between them, offset by half a brick-length on alternating rows --
    the same running-bond offset a real brick wall uses, so the joints
    don't line up into a continuous vertical seam."""
    row_spacing = max(size, 0.01) * 0.25
    brick_len = row_spacing * 2.2
    u, v = _axes(angle)
    row_centers = _row_centers(width, height, row_spacing, u, v)
    segments = _full_span_segments(width, height, row_centers, u)

    half_diag = math.hypot(width, height) / 2
    n_cols = int(half_diag / brick_len) + 2
    cx, cy = width / 2, height / 2
    for row_index, (rx, ry) in enumerate(row_centers):
        col_offset = 0.0 if row_index % 2 == 0 else brick_len / 2
        for i in range(-n_cols, n_cols + 1):
            along = i * brick_len + col_offset
            x0 = rx + along * u[0]
            y0 = ry + along * u[1]
            x1 = x0 + row_spacing * v[0]
            y1 = y0 + row_spacing * v[1]
            segments.append(LineSegment(x0, y0, x1, y1))
    return segments


@dataclass(frozen=True)
class HatchPattern:
    """Bundles one pattern's identity (id/display_name, shown in the
    catalog UI's dropdown) with its own sensible starting angle/size and
    a reference to the actual `_generate_xxx` function that draws it.

    ADVANCED TECHNIQUE -- storing a function as data:
    `generate` isn't a number or a string -- it's a reference to one of
    the `_generate_xxx` functions above (e.g. _generate_dots), stored as
    a plain field just like any other value. Python functions are
    "first-class objects", meaning they can be passed around, stored in
    variables, and put in data structures exactly like a number or a
    string can. This is what lets PATTERN_REGISTRY below be a single
    lookup table mapping a pattern's id (a string typed into the catalog
    editor, like "dots") straight to the actual code that draws it --
    without needing an if/elif chain like `if pattern_id == "dots":
    _generate_dots(...) elif pattern_id == "circles": ...` anywhere in
    the codebase. The type hint `Callable[[float, float, float, float],
    list[Primitive]]` just documents that shape: "a function that takes
    four floats and returns a list of Primitives".
    """

    id: str
    display_name: str
    default_angle: float
    default_size: float
    generate: Callable[[float, float, float, float], list[Primitive]]


# The single source of truth for "what hatch patterns exist" -- looked up
# by drawing.py (to actually render a layer's pattern) and by the webapp
# (to populate the pattern dropdown in the catalog editor), so adding a
# new pattern to the whole program is just: write a new `_generate_xxx`
# function above, then add one line here.
PATTERN_REGISTRY: dict[str, HatchPattern] = {
    "none": HatchPattern("none", "None (outline only)", 0.0, 1.0, _generate_none),
    "dots": HatchPattern("dots", "Dots (sand / silt)", 0.0, 1.0, _generate_dots),
    "circles": HatchPattern("circles", "Circles (gravel)", 0.0, 1.0, _generate_circles),
    "dashes": HatchPattern("dashes", "Dashes (clay)", 0.0, 1.0, _generate_dashes),
    "cross_hatch": HatchPattern("cross_hatch", "Cross-hatch (fill / made ground)", 45.0, 1.0, _generate_cross_hatch),
    "organic": HatchPattern("organic", "Organic ticks (peat / topsoil)", 0.0, 1.0, _generate_organic),
    "brick": HatchPattern("brick", "Brick (weathered rock)", 0.0, 1.0, _generate_brick),
}
