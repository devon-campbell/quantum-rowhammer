# Standard library
import os
import json
import itertools
from collections import defaultdict, Counter
import datetime as dt

# Third-party libraries
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Qiskit
from qiskit import QuantumCircuit, transpile, ClassicalRegister
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
from qiskit_experiments.library import StandardRB
from qiskit_experiments.framework import ParallelExperiment

# Local utilities
from utils import *

# ------------------------------------------
# 0. Define center groups to hammer
# ------------------------------------------
center_groups = [
    [15, 34, 54],
    [72, 93, 109],
    [15, 54, 109],  
]

# ------------------------------------------
# 1. Define global parameters
# ------------------------------------------
CENTER_QS      = [15, 34, 54, 72, 93, 109]
BACKEND_NAME   = "ibm_brisbane"   # or any heavy-hex backend
TOTAL_SHOTS   = 10_000        # per circuit execution
CSV_PATH      = "sweep.csv"
n_cycles      = 20          # total cycles (10 hammer + 10 baseline)
apply_H       = False       # set True to test in |±⟩ basis
gate          = 'cx'        # or 'cz'
rb_every      = 2           # run RB every 2 cycles
rb_cliffords  = 20          # length of each RB sequence
rb_seeds      = 1           # random seed for RB Clifford sequences
CNOT_ROUNDS = 30
RB_SHOTS       = 20
# -------------------------------------
backend   = service.backend(BACKEND_NAME)
coupling  = backend.configuration().coupling_map
n_qubits  = backend.num_qubits

def write_epc_json(rb_data, tag, backend, timestamp):
    df = rb_data.analysis_results(dataframe=True)
    df_epc = df[df['name'] == 'EPC']
    records = []

    for _, row in df_epc.iterrows():
        q_ind = row['components'][0].index
        record = {
            'name':row['name'],
            'q_ind':q_ind,
            'value':row['value'].nominal_value,
            'quality':row['quality'],
            't1': backend.qubit_properties(q_ind).t1,
            't2': backend.qubit_properties(q_ind).t2,
        }
        records.append(record)
    
    with open(f"soak_data/{tag}_soak_{backend.name}_{timestamp}.json", "w") as f:
        json.dump(records, f, indent=2)

def benchmark(rb_expts, tag, backend, timestamp):
    rb = ParallelExperiment(experiments=rb_expts)
    rb_data = rb.run(backend=backend, shots=RB_SHOTS, job_tags=[f"{tag}_soak"]).block_for_results()
    write_epc_json(rb_data, tag, backend, timestamp)

def extract_qubit_counts(counts, n_qubits):
    """Convert full-shot strings to per-qubit 0/1 tallies."""
    tallies = {q: {'0': 0, '1': 0} for q in range(n_qubits)}
    for bitstring, freq in counts.items():
        bitstring = bitstring.zfill(n_qubits)
        for q in range(n_qubits):
            b = bitstring[-(q + 1)]
            if b in tallies[q]:
                tallies[q][b] += freq
    return tallies

# ---------------------------------------------------------------------
# 1. RB helper – build 1Q and 2Q randomized benchmarking experiments
# ---------------------------------------------------------------------
def build_rb_suite(target_qubits, lengths=[1, 2, 4, 8, 16, 32]):
    """
    Return a list of StandardRB experiments covering:
      • Single-qubit RB on each qubit in `target_qubits`
      • Two-qubit RB on each valid CX pair within `target_qubits`
    """
    rb_expts = []
    
    # 1Q RB on each qubit
    for q in target_qubits:
        rb_expts.append(StandardRB(physical_qubits=[q], lengths=lengths))

    # 2Q RB on each supported coupling within the target set
    cm = set(map(tuple, backend.coupling_map))
    for q0, q1 in itertools.combinations(sorted(target_qubits), 2):
        if (q0, q1) in cm or (q1, q0) in cm:
            rb_expts.append(StandardRB(physical_qubits=[q0, q1], lengths=lengths))
    
    return rb_expts

def build_multi_hammer_circuit(centers, init_state=1, hammer=True,
                               apply_H=False, gate='cx', n_q=None):

    n_q = n_q or backend.num_qubits
    qc  = QuantumCircuit(n_q, n_q)

    # 1) Initialise chosen data qubits
    if init_state:
        for c in centers:
            qc.x(c)

    # 2) Optional H-basis shift so we hit |+⟩/|–⟩ instead of |0⟩/|1⟩
    if apply_H:
        for c in centers:
            qc.h(c)

    # 3) Rowhammer proper
    if hammer:
        # full neighbourhood of every center
        all_neighs = [get_neighbors(c) for c in centers]

        for neigh in all_neighs:
            for q in neigh:
                qc.x(q)                              # strong microwave burst

        # `CNOT_ROUNDS` rounds of pair-wise CX/CZ on the neighbour set
        for _ in range(CNOT_ROUNDS):
            for neigh in all_neighs:
                for i, q in enumerate(neigh):
                    tgt = neigh[-(i + 1)]
                    if gate == 'cx':
                        qc.cx(q, tgt)
                    else:
                        qc.cz(q, tgt)
            qc.barrier(*range(n_q))

    # 4) Undo basis change
    if apply_H:
        for c in centers:
            qc.h(c)

    # 5) ***Measure every qubit*** so we can build heat-maps later
    qc.measure(range(n_q), range(n_q))
    return qc

def run_rounds_with_calibration(center_groups,
                                INIT_STATE,
                                n_cycles      = 20,
                                apply_H       = False,
                                gate          = 'cx',
                                rb_every      = 2,
                                rb_cliffords  = 20,
                                rb_seeds      = 1):

    sampler      = SamplerV2(mode=backend)
    n_qubits     = backend.num_qubits
    csv_exists   = os.path.exists(CSV_PATH)

    for cycle in range(n_cycles):
        hammer_flag = (cycle % 2 == 0)
        centers     = center_groups[cycle % len(center_groups)]
        timestamp   = dt.datetime.utcnow().strftime('%Y%m%dT%H%M%S')

        print(f"[Cycle {cycle:02}] hammer={hammer_flag}  centers={centers}")

        # 1) Build and run the circuit
        qc = build_multi_hammer_circuit(
            centers,
            init_state=INIT_STATE,
            hammer=hammer_flag,
            apply_H=apply_H,
            gate=gate,
            n_q=n_qubits
        )
        qc   = transpile(qc, backend, optimization_level=0)
        job  = sampler.run([qc], shots=TOTAL_SHOTS)
        counts = job.result()[0].data.c.get_counts()
        bit_counts = extract_qubit_counts(counts, n_qubits)

        # 2) Write this cycle’s results immediately
        cycle_rows = []
        for q in range(n_qubits):
            cycle_rows.append({
                'timestamp':     timestamp,
                'cycle':         cycle,
                'hammer':        hammer_flag,
                'init_state':    INIT_STATE,
                'center_group':  str(centers),
                'qubit':         q,
                'count_0':       bit_counts[q]['0'],
                'count_1':       bit_counts[q]['1']
            })

        df = pd.DataFrame(cycle_rows)
        df.to_csv(CSV_PATH, mode='a', header=not csv_exists, index=False)
        csv_exists = True  # Header only needed once

        # 3) Run RB if needed
        if (cycle + 1) % rb_every == 0:
            print(f"[Cycle {cycle:02}]  ‣ running RB calibration…")
            rb_expts = build_rb_suite(
                target_qubits=set().union(*center_groups),
                lengths=[rb_cliffords]
            )
            benchmark(rb_expts, tag=f"cycle{cycle}", backend=backend, timestamp=timestamp)

