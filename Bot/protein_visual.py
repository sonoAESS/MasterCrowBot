from Bio.PDB import PDBParser, PPBuilder
import matplotlib.pyplot as plt
import os

def analyze_pdb(file_path):
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("protein", file_path)

    num_chains = len(structure.get_chains())
    num_residues = sum(len(chain) for chain in structure.get_chains())

    ppb = PPBuilder()
    first_chain = next(structure.get_chains())
    sequence = ""
    for pp in ppb.build_peptides(first_chain):
        sequence += pp.get_sequence()

    plt.bar(range(num_chains), [len(chain) for chain in structure.get_chains()])
    plt.xlabel("Cadenas")
    plt.ylabel("Número de residuos")
    plt.title("Longitud de cadenas proteína")
    plt.tight_layout()
    plt.savefig("chain_lengths.png")
    plt.close()

    return num_chains, num_residues, str(sequence)

def cleanup_files():
    if os.path.exists("chain_lengths.png"):
        os.remove("chain_lengths.png")
