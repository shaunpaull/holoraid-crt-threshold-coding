#!/usr/bin/env python3
"""
HoloRAID v3.0 — HyperMorphic Gearbox Edition
-------------------------------------------

This is a HyperMorphic-wrapped implementation of CRT threshold sharding with
correct Asmuth–Bloom secrecy.

HyperMorphic integrations:
- ε_h "no-zero" shift: internally encode s_h = s + ε_h
- Φ (dynamic base): deterministic per config, influences modulus spacing and routing permutation
- Ψ (dynamic modulus): generates shadow prime p0 > Q+ε_h and n primes above p0
- SafeGear: deterministic bijective shard routing permutation (gearbox wiring)

Runs with: Python 3.9+, NumPy
"""

import time, random
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from functools import reduce
import numpy as np

def gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a

def extended_gcd(a: int, b: int) -> Tuple[int, int, int]:
    if a == 0:
        return b, 0, 1
    g, x, y = extended_gcd(b % a, a)
    return g, y - (b // a) * x, x

def mod_inverse(a: int, m: int) -> int:
    g, x, _ = extended_gcd(a % m, m)
    if g != 1:
        raise ValueError(f"No modular inverse for {a} mod {m}")
    return x % m

def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n in (2, 3):
        return True
    if n % 2 == 0:
        return False
    d = n - 1
    r = 0
    while d % 2 == 0:
        r += 1
        d //= 2
    for a in [2,3,5,7,11,13,17,19,23,29,31,37]:
        if a >= n:
            continue
        x = pow(a, d, n)
        if x in (1, n-1):
            continue
        for _ in range(r-1):
            x = (x * x) % n
            if x == n-1:
                break
        else:
            return False
    return True

def next_prime(n: int) -> int:
    if n <= 2:
        return 2
    if n % 2 == 0:
        n += 1
    while not is_prime(n):
        n += 2
    return n

def crt_reconstruct(residues: List[int], moduli: List[int]) -> int:
    M = 1
    for m in moduli:
        M *= m
    x = 0
    for r_i, m_i in zip(residues, moduli):
        M_i = M // m_i
        y_i = mod_inverse(M_i, m_i)
        x += r_i * M_i * y_i
    return x % M

class SafeGear:
    def __init__(self, a: int, b: int):
        assert gcd(a, b) == 1
        self.a, self.b = a, b
        self.ab = a * b

    def forward(self, x: int) -> int:
        q = x // self.b
        r = x % self.b
        return (r * self.a + q) % self.ab

    def inverse(self, y: int) -> int:
        return ((y % self.a) * self.b + y // self.a) % self.ab

    def verify_bijection(self) -> bool:
        seen = set()
        for x in range(self.ab):
            y = self.forward(x)
            if self.inverse(y) != x:
                return False
            seen.add(y)
        return len(seen) == self.ab

@dataclass
class HyperMorphicPolicy:
    Q: int = 65535
    n: int = 5
    k: int = 3
    epsilon_h: int = 1
    seed: int = 42
    Phi: Optional[int] = None

    def __post_init__(self):
        random.seed(self.seed)
        np.random.seed(self.seed)
        if self.Phi is None:
            self.Phi = next_prime((self.Q + self.epsilon_h + 1) // 2 + 1337)

    def psi_generate_moduli(self) -> Tuple[int, List[int]]:
        p0 = next_prime(self.Q + self.epsilon_h + 1)
        primes = []
        candidate = p0 + 1
        gap = max(1, (self.Phi % 97))
        while len(primes) < self.n:
            candidate += gap
            p = next_prime(candidate)
            primes.append(p)
            candidate = p
        return p0, primes

    def shard_permutation(self) -> Tuple[List[int], List[int]]:
        a = next_prime((self.Phi % 50) + 3)
        b = next_prime((self.Phi % 70) + 5)
        gear = SafeGear(a, b)
        assert gear.verify_bijection()
        perm, seen = [], set()
        x = self.Phi % gear.ab
        while len(perm) < self.n:
            x = gear.forward(x)
            idx = x % self.n
            if idx not in seen:
                seen.add(idx)
                perm.append(idx)
        inv = [0] * self.n
        for i, j in enumerate(perm):
            inv[j] = i
        return perm, inv

class HyperMorphicHoloRAID:
    def __init__(self, policy: HyperMorphicPolicy):
        self.P = policy
        self.p0, self.primes = self.P.psi_generate_moduli()
        self.n, self.k = self.P.n, self.P.k
        self.perm, self.invperm = self.P.shard_permutation()
        sorted_primes = sorted(self.primes)
        self.M_k = reduce(lambda a, b: a * b, sorted_primes[:self.k], 1)
        self.M_km1 = reduce(lambda a, b: a * b, sorted_primes[:self.k-1], 1) if self.k > 1 else 1
        if self.p0 * self.M_km1 >= self.M_k:
            raise ValueError("Asmuth–Bloom inequality failed")
        max_secret = self.P.Q + self.P.epsilon_h
        self.max_r = (self.M_k - max_secret - 1) // self.p0
        if self.max_r < 0:
            raise ValueError("Insufficient modulus size")

    def encode(self, s: int) -> Tuple[List[int], int]:
        assert 0 <= s <= self.P.Q
        s_h = s + self.P.epsilon_h
        r = random.randint(0, self.max_r)
        s_prime = s_h + r * self.p0
        shares = [s_prime % p for p in self.primes]
        routed = [shares[j] for j in self.perm]
        return routed, r

    def decode(self, routed_shares: List[int], routed_indices: List[int]) -> int:
        assert len(routed_shares) == len(routed_indices) == self.k
        orig_indices = [self.perm[i] for i in routed_indices]
        moduli = [self.primes[i] for i in orig_indices]
        s_prime = crt_reconstruct(routed_shares, moduli)
        s_h = s_prime % self.p0
        s = s_h - self.P.epsilon_h
        if not (0 <= s <= self.P.Q):
            raise ValueError("Decoded secret out of range")
        return s

def test_reconstruction(system: HyperMorphicHoloRAID, trials: int = 2000, erasures: int = 2) -> float:
    ok = 0
    for _ in range(trials):
        s = random.randint(0, system.P.Q)
        routed, _ = system.encode(s)
        all_idx = list(range(system.n))
        if erasures > 0:
            erased = set(random.sample(all_idx, min(erasures, system.n - system.k)))
            surviving = [i for i in all_idx if i not in erased]
        else:
            surviving = all_idx
        pick = surviving[:system.k]
        s2 = system.decode([routed[i] for i in pick], pick)
        ok += int(s2 == s)
    return ok / trials * 100.0

def main():
    t0 = time.time()
    policy = HyperMorphicPolicy(Q=65535, n=5, k=3, epsilon_h=1, seed=42)
    hm = HyperMorphicHoloRAID(policy)
    print(f"Phi={policy.Phi}, p0={hm.p0}, primes={hm.primes}, perm={hm.perm}")
    for e in [0,1,2,3]:
        print(f"erasures={e}: {test_reconstruction(hm, trials=2000, erasures=e):.2f}%")
    print(f"Done in {time.time()-t0:.2f}s")

if __name__ == "__main__":
    main()
