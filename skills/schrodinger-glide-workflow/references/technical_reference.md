# Schrodinger Glide -- Technical Reference

## InChI Stereo Layer Reference

| InChI Layer | Absolute Configuration | Verified |
|-------------|----------------------|----------|
| `/m0/s1` | S | L-Alanine, GSK2830371 |
| `/m1/s1` | R | D-Alanine |

Reference verified with L-Alanine (known S):
- SMILES: `N[C@@H](C)C(=O)O`
- InChI: `InChI=1S/C3H7NO2/.../t2-/m0/s1`
- RDKit CIP: S

## Glide Execution Modes

### 1. Direct (single-core, reliable)
```bash
"C:\Program Files\Schrodinger2023-1\glide.exe" -WAIT input.in
```
- Bypasses Job Control entirely
- Works from any environment (sandbox, command line)
- No multi-core

### 2. Parallel (N independent processes)
```bash
# Split ligands into N batches
# Launch N glide.exe -WAIT batch_NN.in simultaneously
```
- Nx speedup on N-core machine
- No Job Control dependency
- Requires post-run merge of results

### 3. Maestro GUI Multi-Core
- File -> Ligand Docking -> Job Settings -> Processors -> Run
- Uses Schrodinger Job Control (requires AppData write access)
- Maximum throughput for large libraries

### 4. Job Control (not from sandbox)
```bash
"$SCHRODINGER/run" glide_driver.py -NJOBS 12 -SUBLOCAL input.in
```
- Requires `.jobdb2` directory writable
- Fails from WorkBuddy sandbox with "Permission denied"

## LigPrep Quick Reference

```bash
# SMILES -> maegz with Epik protonation
ligprep -ismi input.smi -omae output.maegz -epik -s 1 -g -WAIT
```

| Flag | Purpose |
|------|---------|
| `-ismi` | Input SMILES format |
| `-omae` | Output Maestro format |
| `-epik` | Epik pKa-based protonation |
| `-s 1` | One stereoisomer per ligand |
| `-g` | Generate 3D coordinates |
| `-WAIT` | Synchronous execution |

Without `-WAIT`, LigPrep submits to Job Control and returns immediately
-- the job may not actually run if Job Control is unavailable.

## Glide .in Keyword Reference

| Keyword | Values | Required | Notes |
|---------|--------|----------|-------|
| FORCEFIELD | OPLS_2005 | Yes | |
| GRIDFILE | path/to/grid.zip | Yes | Quote if path has spaces |
| LIGANDFILE | path/to/ligands.maegz | Yes | Quote if path has spaces |
| PRECISION | SP, XP, HTVS | Yes | SP = Standard, XP = Extra |
| POSTDOCK | True/False | No | Post-docking minimization |
| POSE_OUTTYPE | ligandlib, maestro | No | ligandlib = compact CSV |
| DOCKING_METHOD | confgen, rigid, inplace | No | confgen = flexible |
| NENHANCED_SAMPLING | 1-4 | No | Wider funnel sampling |
| AMIDE_MODE | penal, trans | No | Penalize non-planar amides |

## Output File Naming

```
<input_name>.csv       -> CSV results (with POSE_OUTTYPE ligandlib)
<input_name>_raw.maegz -> Docked poses (maestro format)
<input_name>.log       -> Glide execution log
```

## Performance Estimates

SP docking on 24-logical-processor machine (single-core):
- ~5 sec/ligand for rigid-ish compounds (<5 rotatable bonds)
- ~15 sec/ligand for flexible compounds (8-12 rotatable bonds)
- ~30 sec/ligand for macrocycles or >15 rotatable bonds

Parallel split scaling:
- 12-way split on 24-core: ~12x speedup (diminishing returns beyond logical cores)
- Overhead: ~10-20% (grid loading, I/O)
