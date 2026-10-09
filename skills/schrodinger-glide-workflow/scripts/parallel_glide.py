#!/usr/bin/env python3
"""
Parallel Glide Docking Runner
Splits ligand library into N batches and runs them concurrently.
Usage: python parallel_glide.py <ligands.maegz> <grid.zip> <N_batches> [--precision SP|XP]
       Must be run with Schrodinger Python (schrodinger/run).
"""
import argparse, csv, os, subprocess, sys, time, glob
from pathlib import Path
from schrodinger.structure import StructureReader, StructureWriter


GLIDE_EXE = r"C:\Program Files\Schrodinger2023-1\glide.exe"


def split_maegz(input_maegz, n_batches, output_dir):
    """Split a maegz file into N roughly equal batches."""
    structures = []
    with StructureReader(str(input_maegz)) as reader:
        for st in reader:
            structures.append(st)

    total = len(structures)
    per_batch = (total + n_batches - 1) // n_batches
    batch_files = []

    for i in range(n_batches):
        start = i * per_batch
        end = min(start + per_batch, total)
        if start >= total:
            break
        batch_file = output_dir / f"batch_{i+1:02d}.maegz"
        with StructureWriter(str(batch_file)) as writer:
            for st in structures[start:end]:
                writer.append(st)
        batch_files.append((i+1, batch_file, end-start))
        print(f"  Batch {i+1:02d}: ligands {start+1}-{end} ({end-start} structures)")

    return batch_files


def create_in_file(batch_id, batch_maegz, grid_zip, precision, output_dir):
    """Create a Glide input file for one batch."""
    in_file = output_dir / f"batch_{batch_id:02d}.in"
    content = f"""FORCEFIELD OPLS_2005
GRIDFILE "{grid_zip}"
LIGANDFILE "{batch_maegz}"
PRECISION {precision}
POSTDOCK False
POSE_OUTTYPE ligandlib
DOCKING_METHOD confgen
NENHANCED_SAMPLING 4
AMIDE_MODE penal"""
    in_file.write_text(content)
    return in_file


def launch_batch(batch_id, in_file, output_dir):
    """Launch one Glide process."""
    log_file = output_dir / f"batch_{batch_id:02d}.log"
    cmd = f'"{GLIDE_EXE}" -WAIT {in_file.name}'
    return subprocess.Popen(
        cmd,
        shell=True,
        cwd=str(output_dir),
        stdout=open(str(log_file), 'w'),
        stderr=subprocess.STDOUT,
    )


def merge_results(output_dir, n_batches):
    """Merge all batch CSV outputs into one merged_results.csv."""
    all_rows = []
    for i in range(1, n_batches + 1):
        csv_file = output_dir / f"batch_{i:02d}.csv"
        if csv_file.exists():
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                all_rows.extend(list(reader))

    if not all_rows:
        print("  WARNING: No batch CSV files found!")
        return 0

    merged = output_dir / "merged_results.csv"
    with open(merged, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_rows)

    return len(all_rows)


def main():
    parser = argparse.ArgumentParser(description="Parallel Glide Docking Runner")
    parser.add_argument("ligands", help="Input ligand maegz file")
    parser.add_argument("grid", help="Glide grid zip file")
    parser.add_argument("n_batches", type=int, help="Number of parallel batches")
    parser.add_argument("--precision", default="SP", choices=["SP", "XP"],
                        help="Docking precision (default: SP)")
    parser.add_argument("--output", default=".", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Validate inputs
    grid = Path(args.grid).resolve()
    ligands = Path(args.ligands).resolve()
    if not grid.exists():
        print(f"ERROR: Grid file not found: {grid}")
        sys.exit(1)
    if not ligands.exists():
        print(f"ERROR: Ligand file not found: {ligands}")
        sys.exit(1)

    print(f"Parallel Glide Docking: {args.n_batches} batches")
    print(f"  Ligands: {ligands}")
    print(f"  Grid:    {grid}")
    print(f"  Output:  {output_dir}")
    print()

    # Step 1: Split
    print("[1/5] Splitting ligands...")
    batches = split_maegz(ligands, args.n_batches, output_dir)
    actual_n = len(batches)
    print(f"  Created {actual_n} batches")

    # Step 2: Create .in files
    print("\n[2/5] Creating input files...")
    in_files = []
    for bid, batch_file, count in batches:
        inf = create_in_file(bid, batch_file, grid, args.precision, output_dir)
        in_files.append((bid, inf))

    # Step 3: Launch
    print(f"\n[3/5] Launching {actual_n} parallel processes...")
    procs = []
    for bid, inf in in_files:
        proc = launch_batch(bid, inf, output_dir)
        procs.append((bid, proc))
        print(f"  Batch {bid:02d}: PID {proc.pid}")

    # Step 4: Monitor
    print("\n[4/5] Monitoring...")
    start_time = time.time()
    while True:
        running = sum(1 for _, p in procs if p.poll() is None)
        if running == 0:
            break
        elapsed = time.time() - start_time
        print(f"  [{elapsed:.0f}s] {running}/{actual_n} batches running...")
        time.sleep(20)

    elapsed = time.time() - start_time
    print(f"  All completed in {elapsed:.0f}s ({elapsed/60:.1f} min)")

    # Check each batch
    failed = 0
    for bid, proc in procs:
        csv_file = output_dir / f"batch_{bid:02d}.csv"
        if proc.returncode != 0 or not csv_file.exists():
            print(f"  Batch {bid:02d}: FAILED (rc={proc.returncode})")
            failed += 1
        else:
            print(f"  Batch {bid:02d}: OK")

    if failed > 0:
        print(f"\nWARNING: {failed}/{actual_n} batches failed!")

    # Step 5: Merge
    print("\n[5/5] Merging results...")
    count = merge_results(output_dir, actual_n)
    print(f"  Merged {count} rows -> merged_results.csv")
    print(f"\n[DONE] Output in: {output_dir}")


if __name__ == "__main__":
    main()
