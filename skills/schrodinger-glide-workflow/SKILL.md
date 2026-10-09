---
name: schrodinger-glide-workflow
description: 'Schrodinger Glide virtual screening on Windows with N-way parallel execution

  as the DEFAULT strategy (split-and-merge, 12x+ speedup). Covers LigPrep,

  grid setup, chirality verification (InChI-based, mandatory before docking),

  result analysis, cross-ranking, and Maestro GUI multi-core alternative.

  Use for ANY virtual screening project -- target-agnostic workflow with

  bundled automation scripts (parallel_glide.py, chirality_tools.py).

  '
metadata:
  agent_created: true
---

# Schrodinger Glide Virtual Screening -- General Workflow

Platform-independent workflow for running Glide SP/XP virtual screening on
Windows from the command line or programmatic interface. All procedures are
target-agnostic -- replace protein, grid, ligand paths with project-specific values.

---

## Phase 1: Target Research & Reference Compound Retrieval

### 1.1 Target Information Gathering

Use MCP tools to retrieve authoritative target data before designing any compounds:

```
ChEMBL    -> target info, known inhibitors, bioactivities, MOA
PubChem   -> compound structures, bioassay data, drug indications
UniProt   -> protein sequence, domains, variants, PTMs, interactions
AlphaFold -> predicted/experimental structures, confidence scores
```

Key data to collect for any target:
- **Protein family and catalytic mechanism** (e.g. phosphatase, kinase, GPCR)
- **Active site residues** and cofactor requirements (metal ions, coenzymes)
- **Available PDB structures** with resolution and key binding interactions
- **Known inhibitors**: ChEMBL `search_compounds` + `get_target_compounds` -> gather chemotypes, binding modes, potency ranges
- **Patent landscape**: identify core scaffolds to avoid (patent circumvention strategy)

### 1.2 Reference Compound Selection

Identify 1-3 reference inhibitors with:
- Published co-crystal structures (preferred)
- Well-characterized binding mode
- Clear stereochemistry requirements (if chiral)

Extract reference SMILES, binding pose, and key pharmacophore features.
Verify stereochemistry via InChI (see Phase 3 Chirality Protocol) -- the
reference compound's chirality is the gold standard for the entire library.

### 1.3 Binding Site Definition

Define the docking site from reference co-crystal or literature:
- Binding pocket residues
- Grid center coordinates
- Key interaction residues (H-bond donors/acceptors, hydrophobic contacts)

---

## Workflow Strategy (IFD-Validated Evolution)

### Lesson from PPM1D Project

The naive workflow (enumerate -> dock -> filter) produced ~95% false positives
when validated by Induced Fit Docking. The corrected strategy:

```
BEFORE docking (Phase 2):
  Library generation: manual enumeration OR AI (REINVENT4/GenMol/EvoMol/DiffSBDD)
  -> SA_Score filter (<4.0)
  -> USR dual-reference pre-filter (GSK + BRD, USR < 0.50 to either)
  -> Chirality verify
  -> LigPrep only the survivors
  -> Glide SP only the survivors

AFTER docking (Phase 5):
  PARAMETERS: DockScore + USR + Strain + SA (4 dimensions only for Hit phase)
  -> Percentile tiering (not absolute thresholds)
  -> IFD on top 5-10 candidates
  -> Only IFD-confirmed compounds become synthesis candidates
```

**Key insight: USR is the most important pre-docking filter for allosteric pockets.**
Compounds that dock well in rigid grids but fail IFD (e.g. L1381, L2368) can be
eliminated BEFORE wasting compute on docking if USR > 0.50 to the reference.

### Dual-Reference USR

Always use at least TWO known inhibitors as USR references when available.
Different chemotypes may target the same pocket with different shapes.

| Reference count | Strategy |
|----------------|----------|
| 1 known inhibitor | USR vs single reference, threshold 0.50 |
| 2+ known inhibitors | USR vs ALL references, pass if ANY < 0.50 |

The BRD reference (thiadiazolo-pyrimidine core) captured compounds that GSK
(thiophene-benzamide core) missed, because their core shapes differ.

## Phase 2: Virtual Library Design

### 2.1 Scaffold Strategy

Two complementary approaches:

**Scaffold hopping (patent circumvention):**
- Identify core scaffold of reference inhibitor
- Generate bioisosteric replacements using medicinal chemistry rules
- Use RDKit/datamol for scaffold decomposition and fragment replacement

**De novo enumeration:**
- Define pharmacophore elements based on reference binding mode
- Modular building blocks: cores x linkers x terminal groups
- Full matrix enumeration via SMILES string assembly

### 2.2 AI-Assisted Library Generation (Advanced)

For projects needing larger or more diverse libraries, integrate generative AI
methods. These tools require Python environment setup (see individual docs).

**REINVENT4 (AstraZeneca) -- recommended primary choice:**
- De novo design, scaffold hopping, R-group replacement, linker design
- Transfer learning: fine-tune on known active compounds to bias generation
- Multi-parameter optimization: simultaneously optimize potency + drug-likeness
- Install: `pip install reinvent-models` (or conda environment)
- Usage: define scaffold/reference SMILES -> generate focused library

**DiffSBDD -- pocket/structure-based generation:**
- Generates ligands conditioned on 3D binding pocket structure
- SE(3)-equivariant diffusion model preserves spatial geometry
- Install: `git clone https://github.com/arneschneuing/DiffSBDD`
- Usage: provide PDB pocket + reference ligand -> generate novel chemotypes

**Choice matrix:**
| Goal | Tool | Input | Notes |
|------|------|-------|-------|
| Scaffold hopping | REINVENT4 | Reference SMILES | AstraZeneca, most mature |
| R-group optimization | REINVENT4 | Core scaffold + fragments | Transfer learning ready |
| Diffusion-based generation | GenMol (NVIDIA) | Chemical space prior | SAFE representation, discrete diffusion |
| Evolutionary generation | EvoMol | Fitness function | Genetic algorithm, no pretrained model needed |
| Pocket-aware 3D generation | DiffSBDD | PDB pocket + co-crystal | SE(3)-equivariant, Nature 2024 |
| Pocket-aware (fragment) | DiffDecip | PDB pocket | Fragment-based assembly with diffusion |
| Pocket-aware (language) | BindGPT | PDB pocket | Protein-ligand language model |
| Pocket-aware (language) | Delete | PDB pocket + SMILES | Conditional generation from reference |
| Pocket-aware (fragment) | SeFMol | PDB pocket | Structure-enhanced fragment molecular generation |
| Large diverse library | REINVENT4 + filtering | Reference actives for TL | Scale with transfer learning |
| Custom constraints | REINVENT4 scaffold mode | Scaffold SMILES + property targets | Multi-parameter optimization |

### 2.2b Tool Installation & Usage

**REINVENT4 (AstraZeneca) -- CLI-driven, most mature:**
```bash
git clone https://github.com/MolecularAI/REINVENT4.git
conda create --name reinvent4 python=3.10
conda activate reinvent4
cd REINVENT4 && python install.py cpu all
reinvent --help  # verify
```
Usage: `reinvent -l run.log sampling.toml`
Config TOML files define run mode (sampling, RL, transfer learning), scaffold
constraints, and property targets. Place generated SMILES into the filtering pipeline.

**GenMol (NVIDIA) -- SAFE representation, HuggingFace model:**
```bash
pip install genmol  # or from GitHub
# Load pretrained: nvidia/NV-GenMol-89M-v2 on HuggingFace
```
Input: SAFE sequence with masked fragments. Output: completed molecules.
Best for fragment-based generation with specific scaffold constraints.

**EvoMol -- genetic algorithm, no GPU needed:**
```bash
pip install evomol
```
```python
from evomol import run_model
run_model({
    "obj_function": "qed",  # or custom scoring
    "optimization_parameters": {"max_steps": 1000}
})
```
Good for quick exploration when GPU/pretrained models unavailable.

**DiffSBDD -- pocket-aware:**
```bash
git clone https://github.com/arneschneuing/DiffSBDD.git
conda env create -f environment.yml
```
Requires PDB pocket file + reference co-crystal ligand. Best for structure-based
de novo design when high-quality crystal structure is available.

**Unified integration pattern:**
```python
# All tools produce SMILES output -> feed into pipeline
smiles_list = run_generator(tool, config)  # REINVENT4 / GenMol / EvoMol / DiffSBDD
filtered = apply_medchem_filters(smiles_list)  # PAINS, NIBR, SA_Score
verified = verify_chirality(filtered)           # Phase 3
# -> LigPrep -> Glide (Phase 4)
```
| Custom constraints | REINVENT4 scaffold mode | Scaffold SMILES + property targets | Multi-parameter optimization |

**Post-generation workflow (same as manual library):**
AI output -> PAINS/NIBR/ChEMBL filter -> SA_Score -> chirality verify -> LigPrep -> Glide

### 2.3 Manual Modular Enumeration (Basic)

For small focused libraries or when AI tools are unavailable:

```python
cores = [...]      # N heterocycles/scaffolds
linkers = [...]    # M connecting groups  
tails = [...]      # P terminal fragments

library = []
for core in cores:
    for linker in linkers:
        for tail in tails:
            smi = assemble(core, linker, tail)  # String concatenation
            library.append(smi)
```

**Critical SMILES assembly rules:**
- Validate each SMILES with RDKit after assembly (`Chem.MolFromSmiles`)
- Check for duplicate atoms (e.g. tail already has -NH-, do not add extra N in template)
- Verify chirality IMMEDIATELY after each enumeration batch (see Phase 3)

### 2.4 Compound Filtering Pipeline

Apply filters in this order (use `medchem` and `rdkit` skills):

```
Raw library
  -> PAINS filter    (pan-assay interference)
  -> NIBR filter     (structural alerts)
  -> ChEMBL filter   (known problematic substructures)
  -> Drug-likeness   (Lipinski Rule of 5, Veber)
  -> SA_Score        (synthetic accessibility, Ertl method)
  -> Property filters (MW, LogP, TPSA, rotatable bonds)
  -> Final library
```

Typical thresholds:
- SA_Score < 4.0 (synthetically accessible)
- MW 250-550 Da
- LogP 1-5
- TPSA < 140 A^2
- HBD <= 5, HBA <= 10

### 2.5 Library Documentation

Save the final library as JSON with per-compound metadata:
```json
[
  {"id": "C0001", "smiles": "...", "MW": 350.4, "LogP": 2.8,
   "SA": 2.93, "core": "pyrrole", "tail": "4-fluorophenyl"},
  ...
]
```

This metadata is essential for post-docking SAR analysis and hit expansion.

---

## Phase 3: Chirality Verification (MANDATORY -- BEFORE docking)

### The Problem

SMILES `@`/`@@` notation encodes chirality relative to **atom ordering in the
SMILES string**, NOT directly to CIP absolute configuration. When building
virtual libraries by SMILES string concatenation, the same `@` template can
produce different absolute configurations depending on substituent context.

### Mandatory Verification

Before docking, verify that all compounds have the intended absolute
configuration using InChI stereo layers:

```python
from rdkit import Chem
from rdkit.Chem.inchi import MolToInchi

mol = Chem.MolFromSmiles(smiles)
inchi = MolToInchi(mol)
is_match = '/m0/s1' in inchi  # True if matches target configuration
```

### InChI Stereo Layer Reference

```
/m0/s1  ->  S absolute configuration (verified against L-Alanine)
/m1/s1  ->  R absolute configuration
```

### Correction Protocol

Use `scripts/chirality_tools.py correct`:
1. Identify the chiral center via CIP code
2. Invert chirality at that center with `atom.InvertChirality()`
3. Re-verify via InChI
4. Output corrected SMILES

### Rule

**Verify chirality before docking. Fix the library, do not filter post-docking.**

## Phase 4: Docking Execution

### Multi-Core Strategy (DEFAULT -- always use parallel)

**How:** Split ligand maegz into N batches, launch N independent `glide.exe -WAIT` processes.

**When:** ALWAYS. This is the default strategy. Works from sandbox, command line,
and any environment without Schrodinger Job Control.

**Tested:** 12 compounds / 3 batches: ~70s (vs ~210s single-core = 3x speedup).
1159 compounds / 12 batches: estimated ~30 min (vs ~6 hours single-core = 12x).

### Strategy 2: Maestro GUI Multi-Core (alternative, requires desktop)

**How:** Open Maestro -> Ligand Docking -> select ligands and grid -> Job Settings ->
set "Processors" to desired count (up to detected logical cores).

**When:** User has Maestro GUI access and needs maximum throughput. Not available
from WorkBuddy sandbox.

### Strategy 3: Single-Core Direct (ONLY for tiny tests)

**How:** `glide.exe -WAIT input.in`

**When:** Testing <10 compounds, or when both parallel and GUI are impossible.

**Never use single-core for production runs without explicit user confirmation.**
Always offer the parallel alternative with time estimates first.

### Input File (.in) Specification

**Mandatory keywords (verified working):**
```
FORCEFIELD OPLS_2005
GRIDFILE "C:\path\to\grid.zip"
LIGANDFILE "C:\path\to\ligands.maegz"
PRECISION SP
POSTDOCK False
POSE_OUTTYPE ligandlib
DOCKING_METHOD confgen
```

**Optional performance keywords:**
```
NENHANCED_SAMPLING 4    # Expands Glide funnel for better sampling
AMIDE_MODE penal         # Penalizes non-planar amides
```

**Critical rules:**
- Always quote paths containing spaces with double quotes
- Do NOT add `CSVFILE` -- it is not a valid keyword (causes immediate Glide exit)
- `PRECISION SP` = Standard Precision; use `XP` for Extra Precision
- `DOCKING_METHOD confgen` = flexible docking; use `rigid` for rigid ligands

### LigPrep Workflow

Convert SMILES to Glide-ready 3D structures:

```
ligprep -ismi input.smi -omae output.maegz -epik -s 1 -g -WAIT
```

Key flags:
- `-ismi`: Input SMILES file (format: `SMILES TITLE` per line)
- `-omae`: Output Maestro format
- `-epik`: Epik protonation state enumeration (pH 7.0?2)
- `-s 1`: Generate 1 stereoisomer per ligand (preserves input chirality)
- `-g`: Generate 3D coordinates
- `-WAIT`: Run synchronously (required when bypassing Job Control)

**SMILES file format:**
```
Cc1ccccc1C(=O)NC COMPOUND_001
O=C(O)c1ccccc1 COMPOUND_002
```

LigPrep typically generates 1-4 protonation/tautomer states per compound.

## Phase 5: Result Analysis & Ranking

### 5.1 Reference Compound Validation (MANDATORY)

Before analyzing results, validate the docking protocol by re-docking the known reference compound:

1. Prepare reference inhibitor as isolated SMILES (e.g. `reference.smi`)
2. LigPrep + Glide in the SAME grid, SAME parameters as the screening run
3. Confirm: (a) docking succeeds, (b) DockScore is in a reasonable range, (c) the protocol discriminates the known inhibitor from decoys

Report the reference compound's percentile: "GSK2830371 DS=-9.32, rank #1/2150 (top 0.05%)"

Two acceptable outcomes:
- **Reference scores #1**: Protocol is highly selective (common for high-quality grids)
- **Reference in top 5-10%**: Protocol is appropriately discriminative (most realistic)
- **Reference below top 20%**: Protocol may need re-evaluation (wrong grid, wrong protonation state, etc.)

### 5.2 Multi-Parametric Analysis Framework

Single-score ranking (DockScore only) is insufficient. For credible results, compute ALL of:

**Docking-derived:**
| Metric | Source | What it measures | Interpretation |
|--------|--------|-----------------|----------------|
| DockScore | `r_i_docking_score` | Overall binding affinity | Lower = better (includes Epik+amide penalties) |
| Strain | E_int - GlobalMin | Conformational penalty | <10 kcal/mol = low strain; >30 = distorted |
| USR Shape | RDKit `GetUSRScore` vs reference | 3D shape similarity | <0.5 = highly similar to known binder |
| H-bond score | `r_i_glide_hbond` | Specific polar interactions | More negative = more H-bonds |
| vdW/Coulomb ratio | `r_i_glide_evdw` / `r_i_glide_ecoul` | Binding mode type | >70% vdW = shape-driven (typical for allosteric/hydrophobic pockets) |

**Drug-like properties:**
| Metric | Source | Threshold | Interpretation |
|--------|--------|-----------|----------------|
| SA_Score | Ertl method | <3.5 preferred | Synthetic accessibility |
| QED | RDKit `Descriptors.qed()` | >0.6 preferred | Quantitative drug-likeness |
| LLE | -DS*0.9 - LogP | >0 preferred | Lipophilic ligand efficiency (affinity not from hydrophobicity) |
| Fsp3 | `CalcFractionCSP3` | >0.3 preferred | Molecular complexity (correlates with selectivity) |
| Ro5 violations | MW/LogP/HBD/HBA | =0 preferred | Oral bioavailability |

### 5.3 Percentile-Based Tiering (NOT absolute thresholds)

Absolute thresholds (e.g. "DS < -7.0") are grid/target-dependent and hard to defend.
Use **percentile ranking within the screening library** instead:

```
For each compound, rank all 5 core dimensions (DS, USR, Strain, SA, QED)
against the full library:

Gold Standard:  Top 25% in >=4 of 5 dimensions
Strong:         Top 25% in >=3 of 5 dimensions
Recommended:    Top 50% in >=3 of 5 dimensions
Consider:       Below percentile thresholds
```

### 5.4 Phase-Appropriate Weighting

Different discovery phases need different metrics. Choose phase BEFORE analysis:

**Phase A: Hit Identification (IFD-validated pipeline)**
Parameters: DockScore 35% | USR Shape 25% | Strain 20% | SA 20%
4 dimensions only. NO drug-like filters. IFD on top 5-10. Only IFD-confirmed
compounds become synthesis candidates. This prevents the ~95% false positive
rate observed when relying on rigid docking alone.

**Phase B: Lead Optimization (post-assay SAR)**

**Phase B: Lead Optimization (DS 25% + USR 15% + Strain 15% + SA 10% + QED 10% + LLE 10% + Fsp3 5%)**
Full 7 dimensions. Drug-likeness matters when choosing WHICH hits to advance.

**Phase C: Fragment-Based (LE 30% + DS 20% + USR 15% + SA 15% + Strain 10%)**
Add Ligand Efficiency (DS/heavy_atoms) as primary. Fragments bind per-atom.

### 5.5 Composite Score Formula

For sorting within tiers:

```
Composite = SUM(dimension_pct * weight)
```

Weights rationale (Hit phase):
- **DockScore 35%**: Primary binding metric
- **USR Shape 25%**: 3D conformational match (higher for allosteric pockets)
- **Strain 20%**: Removes false positives from forced poses (NOT "less-strained-is-better" -- check binding mode relevance)
- **SA 20%**: Must be synthesizable to test the hypothesis

### 5.5 Reference Pose for USR

For USR shape comparison, use the BEST available reference conformation:

| Priority | Source | Quality | How to obtain |
|----------|--------|---------|---------------|
| 1 | Co-crystal pose (PDB) | Gold standard | Extract ligand from PDB |
| 2 | Re-docked reference | Good (same protocol, same grid) | Dock reference independently, `structconvert` to SDF |
| 3 | RDKit ETKDG global min | Acceptable (relative ranking still valid) | `AllChem.EmbedMolecule` |

Always document which reference was used and its limitation in the report.

### 5.6 Deliverables

Generate TWO independent reports (do NOT mix into one):

**Report A: Pure DockScore Ranking**
- All compounds ranked by DockScore only
- Reference compound position clearly marked
- No weights, no filtering -- this is the scientific result

**Report B: Multi-Parametric Recommendation**
- Percentile-based tiers (Gold/Strong/Rec/Consider)
- Weighted composite score for sorting
- Interaction fingerprint (H-bond, lipo, vdW/Coulomb ratio)
- Full parameter table per compound
- Clear statement of weights and their rationale

**Also produce:**
- **ADMET report**: Drug-likeness profile for top 50-100
- **Synthetic route analysis**: At minimum for Top 3 compounds
- **JSON**: Machine-readable complete ranking for downstream tools

### 5.7 Report Quality Checklist

Before finalizing any report, verify:

- [ ] Reference compound was re-docked and its percentile reported
- [ ] Tiering uses percentiles, not absolute thresholds
- [ ] Weights are explicitly stated with rationale
- [ ] USR reference source is documented (co-crystal / docked / RDKit)
- [ ] All chirality was verified BEFORE docking (not filtered post-hoc)
- [ ] Interaction energy decomposition (H-bond/lipo/vdW/Coulomb) included
- [ ] Limitations explicitly stated (e.g. "USR based on docked not co-crystal pose")
- [ ] Pure DockScore ranking exists SEPARATELY from weighted recommendations

## Phase 6: Cleanup & File Organization

### File Structure

```
project/
  ligands.smi / ligands.maegz       # Input library
  glide.in                          # Glide input (template)
  glide.rawcsv / glide_raw.maegz    # Output (per run)
  glide.log                         # Glide log
  library.json                      # Compound metadata (SMILES, properties)
  top50_results.csv                 # Final ranking
  docking_report.html               # Final report
  par_test/                         # Parallel test directory (cleanup after)
  par_run/                          # Full parallel run directory
```

### Cleanup Protocol

After confirming results, delete intermediate files:
- Failed batch artifacts (batch_*.log, batch_*.maegz from failed attempts)
- Temp grid directories (*-tmpgrid-*)
- Job control SQLite artifacts (.sqlite*, .jobdb*)
- LigPrep intermediate logs
- Test directories

Keep: final .rawcsv, _raw.maegz, .in template, library JSON, final ranking files.

## Common Errors

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `Could not create .jobdb2 directory` | Sandbox blocks AppData write | Use `glide.exe -WAIT` (Glide ok), or run LigPrep via PowerShell |
| `SEGV signal (memory access error)` | Subjob tmpgrid access issue | Do NOT use `-NJOBS -SUBLOCAL` from sandbox |
| Glide exits immediately, no log | Invalid keyword in .in file | Remove `CSVFILE`, quote all paths |
| `-HOST localhost:N` ignored | Needs job scheduler on Windows | Use N-way parallel or Maestro GUI |
| LigPrep `-WAIT` from bash fails (`.jobdb2` Permission denied) | LigPrep requires Job Control even with `-WAIT` | ALWAYS run LigPrep via PowerShell: `& "C:\Program Files\Schrodinger2023-1\ligprep" ... -WAIT` |
| Glide process shows as `glide_backend.exe` not `glide.exe` | Normal -- glide.exe is launcher, glide_backend.exe does the work | Use `tasklist | grep glide_backend` for monitoring |
| 55%+ wrong chirality in library | SMILES `@`/`@@` != CIP | Verify all compounds with InChI before docking |

## User Communication Standards

1. **Be transparent about limitations.** Report what works and what doesn't immediately.
2. **Distinguish "multi-core" (one job, N subjobs) from "parallel" (N independent jobs).**
3. **Before launching:** confirm grid path, parameter consistency with prior runs, estimated runtime.
4. **Verify chirality before presenting any results as actionable.**
5. **Monitor and report:** when processes are running, provide periodic status with log analysis.
6. **After cleanup:** confirm the final file inventory with the user.
7. **Pre-test then scale:** after a small-scale test succeeds, do NOT change the pipeline
   when scaling to full production. Only increase compound count and batch count.
9. **Multi-parametric analysis mandatory**: after docking, always compute USR, Strain, ADMET. Never present DockScore-only results as final.
10. **IFD mandatory before synthesis**: no compound should be recommended for synthesis without passing IFD in the target pocket. Glide SP alone has ~95% false positive rate for allosteric sites.
