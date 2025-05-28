from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
from qiskit import QuantumCircuit, transpile, ClassicalRegister
import pandas as pd
from collections import defaultdict
import pandas as pd
import numpy as np
import os
from collections import Counter
from utils import *

# ----------  configuration ----------
BACKEND_NAME   = "ibm_brisbane"   # or any heavy-hex backend
CENTER_QS      = [15, 34, 54, 72, 93, 109]
CNOT_ROUNDS    = 30               
APPLY_H        = True
TOTAL_SHOTS    = 2000                # 40k shots
INIT_STATE     = 1
CSV_PATH       = "hammer.csv"
# -------------------------------------
backend   = service.backend(BACKEND_NAME)
coupling  = backend.configuration().coupling_map
n_qubits  = backend.num_qubits

def run_hammer_circ(INIT_STATE=1, hammer=True, gate='cx', apply_H=False):
    rows, props_after = [], None
    for CENTER_Q in CENTER_QS:
        print(CENTER_Q)
        circ  = hammer_circ(CENTER_Q, INIT_STATE, hammer=hammer, apply_H=apply_H, gate=gate)
        circ  = transpile(circ, backend,
                          optimization_level=0,
                          routing='none',
                          scheduling_method="asap")
        sampler = SamplerV2(mode=backend)
        job     = sampler.run([circ], shots=TOTAL_SHOTS)
        counts  = job.result()[0].data.c.get_counts()
        print(counts)

        rows.append({
            'backend':  backend.name,
            'INIT_STATE': INIT_STATE,
            'apply_H': apply_H,
            'gate':gate,
            'CENTER_Q': CENTER_Q,
            'hammer': hammer,
            'count_0': counts.get('0'),
            'count_1': counts.get('1'),
        })

    # write once at the end
    pd.DataFrame(rows).to_csv(CSV_PATH, mode='a',
                              header=not os.path.exists(CSV_PATH),
                              index=False)