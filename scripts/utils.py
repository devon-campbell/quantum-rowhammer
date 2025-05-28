from collections import defaultdict
from qiskit import QuantumCircuit

def get_all_centers(backend=backend):
    def add_adj(conns, i):
        ab = conns[i].copy()
        ab.extend([ab[0]+1, ab[1]+1, ab[0]-1, ab[1]-1])
        return ab
    
    conns = defaultdict(list)
    centers = defaultdict(list)
    
    for i, j in list(backend.coupling_map):
        conns[i].append(j)
        conns[j].append(i)
    
    for center in CENTER_QS:
        centers[center] = sorted(add_adj(conns, center))
    
    return centers

def get_neighbors(i, backend=backend, only_active = False):
    ext = get_all_centers(backend)[i]
    if only_active:
        ext.pop(1)
        ext.pop(-2)
    return ext

def hammer_circ(CENTER_Q, INIT_STATE, hammer=True, apply_H=False, gate='cx'):
    neighs = get_neighbors(CENTER_Q)
    qc = QuantumCircuit(n_qubits, 1)   

    # if INIT_STATE == 1 -> flip bit
    if INIT_STATE:
        qc.x(CENTER_Q)

    # shift to +/- basis
    if apply_H:
        qc.h(CENTER_Q)
        
    # apply hammer protocol
    if hammer:
        for i in neighs:
            qc.x(i)
        
        # apply cnots
        for _ in range(CNOT_ROUNDS):
            for i, val in enumerate(neighs):
                if gate=='cx':
                    qc.cx(val, neighs[-(i+1)])
                elif gate=='cz':
                    qc.cz(val, neighs[-(i+1)])
                    
            qc.barrier(*range(n_qubits))
        
    # shift back
    if apply_H: 
        qc.h(CENTER_Q)
        
    qc.measure(CENTER_Q, 0)
    return qc