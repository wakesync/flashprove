"""Bounded top-k R1CS constraint prototype. NOT a cryptographic proof system.
All witnesses are disclosed to the checker. No publisher arithmetic fidelity.
"""
P = 2**64 - 2**32 + 1
SCALE = 256


def plus(*terms):
    out = {}
    for term in terms:
        for i, c in term.items():
            out[i] = out.get(i, 0) + c
    return {i: c for i, c in out.items() if c}


def times(a, c):
    return {i: v*c for i, v in a.items()}


class Circuit:
    def __init__(self):
        self.values = [1]
        self.names = ['one']
        self.rows = []
        self.public = {}

    def wire(self, name, value):
        self.names.append(name)
        self.values.append(value % P)
        return {len(self.values)-1: 1}

    def val(self, a):
        return sum(self.values[i]*c for i, c in a.items()) % P

    def row(self, a, b, c):
        self.rows.append((a, b, c))

    def eq(self, a, b):
        self.row(plus(a, times(b, -1)), {0: 1}, {})

    def mul(self, name, a, b):
        c = self.wire(name, self.val(a)*self.val(b))
        self.row(a, b, c)
        return c

    def bounded(self, name, a, bits):
        value = self.val(a)
        digits = []
        for j in range(bits):
            d = self.wire(f'{name}.bit{j}', (value >> j) & 1)
            self.row(d, plus(d, {0: -1}), {})
            digits.append(times(d, 1 << j))
        self.eq(a, plus(*digits))

    def input(self, name, value):
        a = self.wire(name, value)
        self.public[next(iter(a))] = value % P
        return a

    def check(self, witness=None):
        w = self.values if witness is None else witness
        if len(w) != len(self.values) or any(type(v) is not int or not 0 <= v < P for v in w):
            return False
        if w[0] != 1 or any(w[i] != v for i, v in self.public.items()):
            return False
        ev = lambda a: sum(w[i]*c for i, c in a.items()) % P
        return all((ev(a)*ev(b)-ev(c)) % P == 0 for a, b, c in self.rows)

    def export(self, path, witness=None):
        # Trusted circuit and public assignment are supplied by verifier, not prover.
        w = self.values if witness is None else witness
        lines = [f'{len(w)} {len(self.rows)} {len(self.public)}', ' '.join(map(str, w))]
        lines += [f'{i} {v}' for i, v in self.public.items()]
        for row in self.rows:
            for a in row:
                lines.append(str(len(a)) + ''.join(f' {i} {c % P}' for i, c in a.items()))
        path.write_text('\n'.join(lines)+'\n')


def build(scores, biases, k, *, order=None, weights=None):
    """Public scores/biases and claimed selected ids/weights, private permutation.
    Optional dishonest order/weights are for malicious witness construction, not checked
    against a sorting oracle. The constraints, not the builder, reject them.
    """
    n = len(scores)
    if not 2 <= n <= 8 or len(biases) != n or type(k) is not int or not 1 <= k <= n:
        raise ValueError('shape')
    if any(type(s) is not int or not 0 <= s <= 255 for s in scores):
        raise ValueError('unsigned eight-bit score')
    if any(type(b) is not int or not -128 <= b <= 127 for b in biases):
        raise ValueError('signed eight-bit bias')
    if order is None:
        order = sorted(range(n), key=lambda i: (-(scores[i]+biases[i]), i))
    if len(order) != n or any(type(i) is not int or not 0 <= i < n for i in order):
        raise ValueError('order shape')
    denominator = sum(scores[i] for i in order[:k])
    if weights is None:
        weights = [SCALE*scores[i]//denominator if denominator else 0 for i in order[:k]]
    if len(weights) != k or any(type(w) is not int or not 0 <= w <= 256 for w in weights):
        raise ValueError('weight shape')
    c = Circuit()
    s = [c.input(f'score{i}', x) for i, x in enumerate(scores)]
    b = [c.input(f'bias_offset{i}', x+128) for i, x in enumerate(biases)]
    for i in range(n):
        c.bounded(f'score{i}', s[i], 8)
        c.bounded(f'bias{i}', b[i], 8)
    # key in [0, 4087], unique even at ties; larger is preferred.
    keys = [plus(times(plus(s[i], b[i]), n), {0: n-1-i}) for i in range(n)]
    select = [[c.wire(f'p{j}.{i}', int(order[j] == i)) for i in range(n)] for j in range(n)]
    for row in select:
        for x in row:
            c.row(x, plus(x, {0: -1}), {})
        c.eq(plus(*row), {0: 1})
    for i in range(n):
        c.eq(plus(*(select[j][i] for j in range(n))), {0: 1})
    ranked, chosen = [], []
    for j in range(n):
        ranked.append(plus(*(c.mul(f'key{j}.{i}', select[j][i], keys[i]) for i in range(n))))
        chosen.append(plus(*(c.mul(f'select_score{j}.{i}', select[j][i], s[i]) for i in range(n))))
        if j < k:
            idx = c.input(f'index{j}', order[j])
            c.eq(idx, plus(*(times(select[j][i], i) for i in range(n))))
    for j in range(n-1):
        c.bounded(f'ordered{j}', plus(ranked[j], times(ranked[j+1], -1), {0: -1}), 12)
    d = plus(*chosen[:k])
    # d >= 1, d <= 2040 follows from eight-bit scores and permutation.
    c.bounded('denominator_minus_one', plus(d, {0: -1}), 11)
    for j in range(k):
        w = c.input(f'weight{j}', weights[j])
        c.bounded(f'weight{j}', w, 9)
        product = c.mul(f'weight_times_denominator{j}', w, d)
        remainder = c.wire(f'remainder{j}', SCALE*scores[order[j]]-weights[j]*denominator)
        c.bounded(f'remainder{j}', remainder, 11)
        c.bounded(f'remainder_upper{j}', plus(d, times(remainder, -1), {0: -1}), 11)
        c.eq(plus(product, remainder), times(chosen[j], SCALE))
    return c
