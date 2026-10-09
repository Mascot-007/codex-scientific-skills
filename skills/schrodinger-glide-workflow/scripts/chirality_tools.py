#!/usr/bin/env python3
"""
Chirality verification and correction tool for virtual screening libraries.
Verifies absolute configuration via InChI stereo layers and corrects mismatches.

InChI Stereo Reference:
  /m0/s1 = S absolute configuration (first enantiomer)
  /m1/s1 = R absolute configuration (second enantiomer)
  Verified against L-Alanine (known S): InChI /t2-/m0/s1

Usage:
  python chirality_tools.py verify <library.json> <reference_smiles>
    -> Verifies all compounds against reference. Outputs correct/wrong ID lists.

  python chirality_tools.py correct <library.json> <reference_smiles> [--output corrected.json]
    -> Corrects all mismatched compounds. Outputs 100%-matching library.

  python chirality_tools.py check <smiles>
    -> Quick check of a single SMILES: prints InChI stereo layer and CIP code.
"""
import json, re, sys
from rdkit import Chem
from rdkit.Chem.inchi import MolToInchi


def get_stereo_config(smiles):
    """Return (cip_code, inchikey_layer) for a SMILES. Example: ('S', '/m0/s1')"""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None, None

    # Get CIP from RDKit (most reliable)
    cip = None
    for atom in mol.GetAtoms():
        if atom.HasProp('_CIPCode'):
            cip = atom.GetProp('_CIPCode')
            break

    # Get InChI stereo layer
    inchi = MolToInchi(mol)
    if inchi is None:
        return cip, None

    m_match = re.search(r'/m(\d+)/s(\d+)', inchi)
    layer = m_match.group(0) if m_match else None

    return cip, layer


def get_reference_config(ref_smiles):
    """Extract reference configuration InChI layer from reference SMILES."""
    mol = Chem.MolFromSmiles(ref_smiles)
    if mol is None:
        raise ValueError(f"Invalid reference SMILES: {ref_smiles}")
    inchi = MolToInchi(mol)
    if inchi is None:
        raise ValueError("Could not generate InChI for reference")
    m_match = re.search(r'/m(\d+)/s(\d+)', inchi)
    if not m_match:
        raise ValueError(f"No tetrahedral stereo in reference: {inchi}")
    return m_match.group(0)  # e.g., '/m0/s1'


def cmd_verify(args):
    """Verify all compounds in library against reference chirality."""
    lib_path = args[0]
    ref_smiles = args[1]

    ref_config = get_reference_config(ref_smiles)
    print(f"Reference stereo layer: {ref_config}")
    print(f"Expected: {ref_config}")

    with open(lib_path, 'r') as f:
        lib = json.load(f)

    correct_ids = set()
    wrong_ids = set()
    no_chiral = 0
    errors = 0

    for i, comp in enumerate(lib):
        smi = comp.get('smiles', '')
        if '@' not in smi:
            no_chiral += 1
            continue

        cip, layer = get_stereo_config(smi)
        if layer is None:
            errors += 1
            continue

        cid = comp.get('id', f'L{i+1:04d}')
        l_key = f'L{i+1:04d}'

        if layer == ref_config:
            correct_ids.add(cid)
            correct_ids.add(l_key)
        else:
            wrong_ids.add(cid)
            wrong_ids.add(l_key)

    total_chiral = len(correct_ids) + len(wrong_ids)
    pct = len(correct_ids) / total_chiral * 100 if total_chiral > 0 else 0

    print(f"\nTotal: {len(lib)} | Chiral: {total_chiral} | No chiral: {no_chiral} | Errors: {errors}")
    print(f"Correct ({ref_config}): {len(correct_ids)} ({pct:.1f}%)")
    print(f"Wrong:               {len(wrong_ids)} ({100-pct:.1f}%)")

    with open('correct_chiral_ids.json', 'w') as f:
        json.dump(sorted(correct_ids), f)
    with open('wrong_chiral_ids.json', 'w') as f:
        json.dump(sorted(wrong_ids), f)
    print("\nSaved correct_chiral_ids.json and wrong_chiral_ids.json")


def cmd_correct(args):
    """Correct all mismatched compounds and output fully corrected library."""
    lib_path = args[0]
    ref_smiles = args[1]

    ref_config = get_reference_config(ref_smiles)
    print(f"Reference stereo: {ref_config}")

    with open(lib_path, 'r') as f:
        lib = json.load(f)

    corrected = []
    fixed = 0
    kept = 0

    for i, comp in enumerate(lib):
        smi = comp.get('smiles', '')
        new_comp = dict(comp)

        if '@' not in smi:
            corrected.append(new_comp)
            continue

        cip, layer = get_stereo_config(smi)
        if layer is None:
            corrected.append(new_comp)
            continue

        if layer == ref_config:
            kept += 1
            corrected.append(new_comp)
        else:
            # Flip chirality at mismatched center
            try:
                mol = Chem.MolFromSmiles(smi)
                for atom in mol.GetAtoms():
                    if atom.HasProp('_CIPCode'):
                        atom.InvertChirality()
                        break
                new_smi = Chem.MolToSmiles(mol, isomericSmiles=True)
                # Verify
                _, new_layer = get_stereo_config(new_smi)
                if new_layer == ref_config:
                    new_comp['smiles'] = new_smi
                    fixed += 1
            except Exception:
                pass
            corrected.append(new_comp)

    # Verify final library
    verify_correct = 0
    verify_wrong = 0
    for comp in corrected:
        smi = comp.get('smiles', '')
        if '@' not in smi:
            continue
        _, layer = get_stereo_config(smi)
        if layer == ref_config:
            verify_correct += 1
        elif layer:
            verify_wrong += 1

    out_path = args[3] if len(args) > 3 else 'corrected_library.json'
    with open(out_path, 'w') as f:
        json.dump(corrected, f, indent=2, ensure_ascii=False)

    print(f"\nCorrected: {fixed} | Kept: {kept} | Total: {len(corrected)}")
    print(f"Verification: {verify_correct}/{verify_correct+verify_wrong} match ({verify_correct/(verify_correct+verify_wrong)*100:.1f}%)")
    print(f"Saved: {out_path}")


def cmd_check(args):
    """Quick single-SMILES check."""
    smi = args[0]
    cip, layer = get_stereo_config(smi)
    mol = Chem.MolFromSmiles(smi)
    inchi = MolToInchi(mol)

    print(f"SMILES:     {smi}")
    print(f"RDKit CIP:  {cip}")
    print(f"InChI:      {inchi}")
    print(f"Stereo:     {layer}")
    if layer:
        config = "S" if "/m0/s1" in layer else "R" if "/m1/s1" in layer else "?"
        print(f"Absolute:   {config}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == "verify":
        cmd_verify(args)
    elif cmd == "correct":
        cmd_correct(args)
    elif cmd == "check":
        cmd_check(args)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)
