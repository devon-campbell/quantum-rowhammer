# Standard library
import os
import time
from collections import defaultdict, Counter
from typing import List, Optional

# Third-party libraries
import numpy as np
import pandas as pd

# Qiskit
from qiskit import QuantumCircuit, transpile, ClassicalRegister
from qiskit.circuit.library import XGate
from qiskit.transpiler import (
    PassManager,
    InstructionDurations,
    Target,
    CouplingMap,
)
from qiskit.transpiler.passes import ALAPScheduleAnalysis, PadDynamicalDecoupling
from qiskit.visualization import timeline_drawer
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

# Local utilities
from utils import *

# ----------  configuration ----------
BACKEND_NAME   = "ibm_brisbane"   # or any heavy-hex backend
CENTER_QS      = [15, 34, 54, 72, 93, 109]
CNOT_ROUNDS    = 30               
APPLY_H        = True
TOTAL_SHOTS    = 15_000                # 40k shots
INIT_STATE     = 1
CSV_PATH       = "dd_H.csv"
# -------------------------------------
backend   = service.backend(BACKEND_NAME)
coupling  = backend.configuration().coupling_map
n_qubits  = backend.num_qubits

def _uhrig_spacing(n: int) -> List[float]:
    """Return inter-pulse spacings that implement Uhrig DD with n π-pulses."""
    # absolute positions in [0,1]
    t = [np.sin(np.pi * (k + 1) / (2 * n + 2)) ** 2 for k in range(n)]
    # convert to spacings (first interval, …, last interval)
    spacing = [t[0]] + [t[i] - t[i - 1] for i in range(1, n)] + [1 - t[-1]]
    return spacing

def apply_dd(
    circ,
    backend,
    mode: str = "uniform",           # "uniform" or "uhrig"
    qubits: Optional[List[int]] = None,
    n: int = 2,                      # # of π-pulses for Uhrig
):
    """
    Return a new circuit padded with dynamical-decoupling gates.
    """
    # ------------------------------------------------------------------
    # 1) Build an InstructionDurations table from the backend
    # ------------------------------------------------------------------
    durations = InstructionDurations.from_backend(backend)

    # ------------------------------------------------------------------
    # 2) Choose the DD sequence and (optional) spacing array
    # ------------------------------------------------------------------
    if mode == "uniform":
        dd_sequence = [XGate(), XGate()]          # balanced X-I-X
        spacing = None                            # Qiskit will space evenly
    elif mode == "uhrig":
        if n < 1:
            raise ValueError("n must be ≥1 for Uhrig DD")
        dd_sequence = [XGate()] * n
        spacing = _uhrig_spacing(n)
    else:
        raise ValueError("mode must be 'uniform' or 'uhrig'")

    # ------------------------------------------------------------------
    # 3) Construct the transpiler pass manager
    # ------------------------------------------------------------------
    pm = PassManager(
        [
            ALAPScheduleAnalysis(durations),                  # push gates late
            PadDynamicalDecoupling(                           # fill idle time
                durations,
                dd_sequence,
                qubits=qubits,
                spacing=spacing,
                pulse_alignment=40,
            ),
        ]
    )

    # ------------------------------------------------------------------
    # 4) Run the passes and return the protected circuit
    # ------------------------------------------------------------------
    return pm.run(circ.copy())        # keep the original intact

def run_hammer_circ(hammer=True, gate='cx', apply_H=True):
    sampler = SamplerV2(mode=backend)
    rows = []
    for CENTER_Q in CENTER_QS:
        print(CENTER_Q)
        for INIT_STATE in [0, 1]:
            print(f'init state: {INIT_STATE}')
            circ  = hammer_circ(CENTER_Q, INIT_STATE, apply_H=True)
            circ  = transpile(circ, backend,
                              optimization_level=0,
                              scheduling_method="asap")
            
            circ_dd_uh  = apply_dd(circ, backend, mode="uhrig", qubits=[CENTER_Q], n=8)
            circ_dd_un = apply_dd(circ, backend, mode="uniform")
            circ_map = {0:'circ', 1:'dd_uniform', 2:'dd_uhrig'}
    
            for i, curr_circ in enumerate([circ, circ_dd_un, circ_dd_un]):
                print(circ_map[i])
                job     = sampler.run([curr_circ], shots=TOTAL_SHOTS)
                counts  = job.result()[0].data.c.get_counts()
                print(counts)
    
                rows.append({
                    'backend':  backend.name,
                    'circ': circ_map[i],
                    'INIT_STATE': INIT_STATE,
                    'CENTER_Q': CENTER_Q,
                    'count_0': counts.get('0'),
                    'count_1': counts.get('1'),
                })
                
                time.sleep(1.0)

    # write once at the end
    pd.DataFrame(rows).to_csv(CSV_PATH, mode='a',
                              header=not os.path.exists(CSV_PATH),
                              index=False)