# Quantum Rowhammer on Superconducting Qubits

> **Phase‑error fault injection via dense gate scheduling**
> *Devon Campbell (Columbia University) · Advisor [Simha Sethumadhavan](https://www.cs.columbia.edu/~simha/) · Spring 2025*

This repository contains the **first open‑source implementation of the Quantum Rowhammer attack**—an analogue of the classical DRAM Rowhammer phenomenon applied to superconducting qubit processors.  By densely scheduling native basis‑gate operations on *aggressor* qubits, we induce **phase and bit‑flip errors exceeding 70 %** on adjacent *victim* qubits **without pulse‑level access**.  We benchmark the spatial reach, temporal persistence, and error‑mitigation strategies, and we release fully reproducible scripts for the community to explore this new class of multi‑tenant vulnerabilities.


## Project Highlights

| Capability                           | Summary                                                                                                                          |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| **Phase error injection**            | Demonstrates that residual electromagnetic cross‑talk can flip qubit phases when *only* standard gate scheduling is available.   |
| **High‑probability fault induction** | Surpasses 70 % bit‑flip probability on IBM heavy‑hex devices with 30 CNOT bursts.                                                |
| **Spatiotemporal characterization**  | Maps fault radius and decay using Hadamard‑basis probes and hammer/control alternation cycles (`sweep.py`).                      |
| **Dynamic error mitigation**         | Implements dynamical decoupling (`dd.py`) and a three‑qubit repetition code (`postselect.py`), cutting error rates by ≈36 %.     |
| **Covert‑channel proof‑of‑concept**  | Sketches a prime‑and‑probe channel via spatially correlated error bursts, highlighting risks for future multi‑tenant schedulers. |

---

## Repository Structure

```
├── scripts/
│   ├── hammer.py        # Core Rowhammer experiment
│   ├── dd.py            # Dynamical‑decoupling mitigation study
│   ├── postselect.py    # 3‑qubit repetition‑code post‑selection
│   ├── sweep.py         # Multi‑center sweeps + RB calibration
│   └── utils.py         # Shared helpers (neighbour lookup, circuit builders)
├── notebooks/           # Analysis & visualisation 
├── docs/                # Manuscript 
└── README.md            # You are here
```

---

## Quick Start

### 1 · Install dependencies

```bash
conda create -n qrowhammer python=3.11
conda activate qrowhammer
pip install -r requirements.txt      # qiskit==1.x, qiskit‑experiments, seaborn, …
```

### 2 · Configure IBM Quantum credentials

```bash
export QISKIT_IBM_TOKEN="<your‑IBM‑cloud‑API‑token>"
```

### 3 · Run the baseline Rowhammer attack

```bash
python scripts/hammer.py \
       --backend        ibm_brisbane \
       --center‑qs      15 34 54 72 93 109 \
       --cnots          30 \
       --shots          2000
# ➜  hammer.csv  ← raw counts per centre qubit
```

### 4 · Evaluate mitigation with dynamical decoupling

```bash
python scripts/dd.py --dd‑mode uhrig --n‑pulses 8
```

### 5 · Post‑select with a 3‑qubit repetition code

```bash
python scripts/postselect.py --init‑state 1 --apply‑h
# ➜  postselect.csv  ← per‑shot ancilla vote vs data qubit outcome
```

All CLI flags are documented via `‑‑help`.

---

## Experimental Reproduction

| Script          | Output CSV         | Purpose                                           |
| --------------- | ------------------ | ------------------------------------------------- |
| `hammer.py`     | `hammer.csv`       | Single‑centre baseline & fault‑probability curves |
| `dd.py`         | `dd_H.csv`         | Dynamical‑decoupling sweep (uniform vs Uhrig)     |
| `postselect.py` | `postselect.csv`   | Repetition‑code post‑selection accuracy           |
| `sweep.py`      | `sweep.csv` + JSON | 6‑centre soak test with RB calibration            |

Notebooks in `notebooks/` load the CSVs and reproduce figures from the associated manuscript.

---

## Hardware & Backends

The scripts target **IBM heavy‑hex devices** (e.g. `ibm_brisbane`, `ibm_washington`).  Update `BACKEND_NAME` in the config block of each script to match your subscription tier and qubit availability.

> **Ethics policy:** This code is for *research and defensive purposes only*.  Always comply with provider terms of service and obtain explicit permission before running fault‑injection workloads on shared hardware.

## Acknowledgements

* **IBM Quantum** for public cloud access to heavy‑hex devices.
* Columbia **Cybersecurity for Quantum Computing Lab** for feedback and testing.
* All contributors and issue reporters—please open a PR!
