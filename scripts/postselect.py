# Standard library
import os
from collections import defaultdict, Counter

# Third-party libraries
import numpy as np
import pandas as pd

# Qiskit
from qiskit import QuantumCircuit, transpile, ClassicalRegister
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
from qiskit.circuit.library import XGate
from qiskit.transpiler import PassManager, InstructionDurations, Target, CouplingMap
from qiskit.transpiler.passes import ALAPScheduleAnalysis, PadDynamicalDecoupling
from qiskit.visualization import timeline_drawer

# Local utilities
from utils import *

# ----------  configuration ----------
BACKEND_NAME   = "ibm_brisbane"   # or any heavy-hex backend
CENTER_QS      = [15, 34, 54, 72, 93, 109]
CNOT_ROUNDS    = 30               
APPLY_H        = True
TOTAL_SHOTS    = 15_000                # 40k shots
CSV_PATH       = "postselect.csv"
# -------------------------------------
backend   = service.backend(BACKEND_NAME)
coupling  = backend.configuration().coupling_map
n_qubits  = backend.num_qubits

def entangle(qc, q0, anc1, anc2, anc3, bit_q0, bit_anc1, bit_anc2, bit_anc3):
    # Decode: compare ancillas to q0
    qc.cx(q0, anc1)
    qc.cx(q0, anc2)
    qc.cx(q0, anc3)

    # Measure ancillas
    qc.measure(anc1, bit_anc1)
    qc.measure(anc2, bit_anc2)
    qc.measure(anc3, bit_anc3)

    # Majority-vote correction in post-processing, or use classical logic later
    qc.measure(q0, bit_q0)

def hammer_circ(CENTER_Q, INIT_STATE, hammer=True, apply_H=False, gate='cx',
                use_repetition=True, anc1=None, anc2=None, anc3=None):
    neighs = get_neighbors(CENTER_Q)
    n_classical = 4 if use_repetition else 1
    qc = QuantumCircuit(n_qubits, n_classical)
    
    if use_repetition:
        if anc1 is None or anc2 is None:
            raise ValueError("Must specify anc1 and anc2 when use_repetition=True")
        if INIT_STATE:
            qc.x(CENTER_Q)
    else:
        if INIT_STATE:
            qc.x(CENTER_Q)

    if apply_H:
        qc.h(CENTER_Q)

    if hammer:
        for i in neighs:
            qc.x(i)
        for _ in range(CNOT_ROUNDS):
            for i, val in enumerate(neighs):
                if gate == 'cx':
                    qc.cx(val, neighs[-(i + 1)])
                elif gate == 'cz':
                    qc.cz(val, neighs[-(i + 1)])
        qc.barrier(*range(n_qubits))

    if apply_H:
        qc.h(CENTER_Q)

    if use_repetition:
        entangle(qc, CENTER_Q, anc1, anc2, anc3,
                       bit_q0=3, bit_anc1=0, bit_anc2=1, bit_anc3=2)
    else:
        qc.measure(CENTER_Q, 0)

    return qc

def run_hammer_circ(INIT_STATE, hammer=True, gate='cx', apply_H=False, use_repetition=True):
    rows = []
    for CENTER_Q in CENTER_QS:
        print(CENTER_Q, INIT_STATE)
        
        # Pick ancillas ≠ CENTER_Q
        available = [i for i in range(n_qubits) if i != CENTER_Q]
        anc1, anc2, anc3 = available[:3] if use_repetition else (None, None)

        circ = hammer_circ(CENTER_Q, INIT_STATE,
                   hammer=True,
                   apply_H=False,
                   gate='cx',
                   use_repetition=True,
                   anc1=anc1,
                   anc2=anc2,
                   anc3=anc3)

        circ = transpile(circ, backend,
                         optimization_level=0)
        
        sampler = SamplerV2(mode=backend)
        job = sampler.run([circ], shots=TOTAL_SHOTS)
        counts = job.result()[0].data.c.get_counts()
    
        for bits, count in counts.items():
            bits = bits.zfill(4)
            anc1, anc2, anc3, q0 = map(int, bits)
            anc_vote = round((anc1 + anc2 + anc3) / 3)  # majority vote
            postselect = (anc_vote == INIT_STATE)
            correct = (q0 == INIT_STATE)
            print(bits, postselect, correct)
        
            rows.append({
                'backend': backend.name,
                'CENTER_Q': CENTER_Q,
                'INIT_STATE': INIT_STATE,
                'use_repetition': use_repetition,
                'bitstring': bits,
                'anc1': anc1,
                'anc2': anc2,
                'anc3': anc3,
                'q0': q0,
                'vote': anc_vote,
                'postselect': postselect,
                'correct': correct,
                'count': count
            })

    pd.DataFrame(rows).to_csv(CSV_PATH, mode='a',
                              header=not os.path.exists(CSV_PATH),
                              index=False)