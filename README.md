# holoraid-crt-threshold-coding
# HoloRAID v3.0 (Colab Ready)
**CRT-Based Threshold Erasure Coding with Correct Asmuth–Bloom Secrecy**

HoloRAID v3 is a single-file, zero-dependency (beyond NumPy/Matplotlib) reference implementation + benchmark suite for:

- **k-of-n CRT sharding** (erasure coding / redundancy)
- **Correct Asmuth–Bloom secret sharing** (information-theoretic secrecy)
- Two auxiliary “holographic” primitives:
  - **SafeGear**: a bijective winding permutation on ℤ\_{ab}
  - **HoloMix**: a multi-frequency interference layer (differentiable relaxation)

It’s written to run as-is in **Google Colab** (no pip installs).  
It also generates a publication figure: `holoraid_v3_benchmarks.png`.

---

## What problem this solves (in plain terms)

Holographic / interference-style representations are *robust* in theory, but brittle in practice:

- devices fail
- shards go missing
- copies diverge
- and naïve “split the number” schemes often leak the secret or reconstruct incorrectly

**HoloRAID** treats a holographic “state” (here represented as an integer secret `s ∈ [0, Q]`) as something you can:

1. **Split into shards**
2. **Lose some shards**
3. **Still reconstruct exactly**
4. And (in secrecy mode) ensure **< k shards reveal nothing** about the underlying state

---

## The critical bug fixed in v3 (why v1/v2 were wrong)

Asmuth–Bloom requires:

- `p₀ < p₁ < ... < pₙ`
- and critically: **secret `s < p₀`**

Earlier versions used small primes like `[53, 59, 61, 67, 71]` while `Q = 65535`.  
That means for most secrets:

- `s mod p₀ ≠ s` (because `p₀` was tiny)
- so the recovered “secret” was silently wrong

### v3 fix (the whole point)
Choose a **shadow prime** `p₀` strictly larger than `Q`.

For `Q = 65535`:
- `p₀ = 65537` (the Fermat prime `2^16 + 1`)
- then pick `p₁..pₙ` as primes **greater than** `p₀`

This makes **every secret** satisfy `s < p₀`, so `s mod p₀ = s` always.

---

## Two modes in this repo

### 1) Standard HoloRAID (no secrecy)
`HoloRAIDStandard(primes, k, Q)`

- Shards are just residues: `share_i = v mod p_i`
- Any `k` shards reconstruct `v` via CRT
- **Not secret sharing**: fewer than `k` shards leak partial information (`v mod M_t`)

Use-case: **fault tolerance**, not secrecy.

---

### 2) HoloRAID with Asmuth–Bloom secrecy (correct)
`HoloRAIDAsmuthBloom(Q=65535, n=5, k=3)`

Encode secret `s`:

1. Choose random `r`
2. Form: `s' = s + r·p₀`
3. Publish shares: `share_i = s' mod p_i`

Decode from any `k` shares:

1. CRT reconstruct `s'`
2. Recover secret: `s = s' mod p₀`

**Security intuition (info-theoretic):**  
With fewer than `k` shares, you only learn `s' mod M_t`, but `r` randomizes `s'` enough that `s` remains hidden.

---

## What the benchmark suite does

Running the file executes:

1. **Standard HoloRAID accuracy** under erasures (small primes)
2. **Asmuth–Bloom accuracy** under erasures (large primes, correct `p₀`)
3. **Comparison** across 0–3 erasures
4. **SafeGear bijection proof-by-exhaustion** on several (a,b)
5. **HoloMix Jacobian boundedness** scan + orthogonality checks
6. **Fault tolerance** vs no redundancy baseline

Then it prints a summary and saves:

- `holoraid_v3_benchmarks.png`

---

## Quick start (Google Colab)

1. Create a new Colab notebook
2. Paste the entire `.py` file into one cell
3. Run the cell

That’s it — Colab already has NumPy + Matplotlib.

---

## Running locally

```bash
python3 holoraid_v3.py
