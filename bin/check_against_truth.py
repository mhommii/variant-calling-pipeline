"""Compare the pipeline's calls against the variants we planted.

Because the test data was generated with known variants (bin/make_test_data.py),
this is a real known-answer test rather than a "did it run without crashing"
check. It reports:

  recall     - how many planted variants were found
  precision  - how many calls correspond to a planted variant

A perfect score is possible on the bundled data (seed 42 gets one) and shows
the steps are wired correctly, not that the calling is good: at 30x with a
0.1% error rate the test is easy. Lowering COVERAGE or raising ERROR_RATE in
make_test_data.py makes it harder. The point is to see the numbers and be
able to explain them.

Run:  python bin/check_against_truth.py [results_dir]

results_dir defaults to ./results in the repository, matching the pipeline's
default --outdir when it is launched from the repository root.
"""

import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
truth_path = ROOT / "data" / "truth.vcf"
results_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results"
called_dir = results_dir / "variants"


def read_vcf(path: Path) -> set:
    """Chromosome, position, reference and alternate allele for each SNV."""
    opener = gzip.open if path.suffix == ".gz" else open
    variants = set()
    with opener(path, "rt") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.split("\t")
            chrom, position = fields[0], int(fields[1])
            reference, alternate = fields[3], fields[4]
            # Single-nucleotide changes only; indels are out of scope here.
            if len(reference) == 1 and len(alternate) == 1:
                variants.add((chrom, position, reference, alternate))
    return variants


if not truth_path.exists():
    sys.exit("data/truth.vcf missing - run bin/make_test_data.py first.")

called_files = sorted(called_dir.glob("*.vcf.gz")) if called_dir.exists() else []
if not called_files:
    sys.exit(f"No VCF found in {called_dir} - run the pipeline first.")

truth = read_vcf(truth_path)

exit_code = 0
for vcf_path in called_files:
    called = read_vcf(vcf_path)
    found = truth & called
    missed = truth - called
    extra = called - truth

    recall = len(found) / len(truth) if truth else 0
    precision = len(found) / len(called) if called else 0

    print(f"\n{vcf_path.name}")
    print(f"  planted variants : {len(truth)}")
    print(f"  calls made       : {len(called)}")
    print(f"  correctly found  : {len(found)}  "
          f"(recall {recall:.0%})")
    print(f"  missed           : {len(missed)}")
    print(f"  not planted      : {len(extra)}  "
          f"(precision {precision:.0%})")

    if missed:
        shown = sorted(missed)[:5]
        print(f"  missed positions : "
              f"{', '.join(f'{c}:{p}' for c, p, _, _ in shown)}"
              f"{' ...' if len(missed) > 5 else ''}")

    # A pipeline this simple should still find most planted variants. If it
    # finds well under half, something is wrong rather than merely noisy.
    if recall < 0.5:
        print("  FAIL: recall below 50% - the pipeline is not working "
              "as intended, not just noisy.")
        exit_code = 1

sys.exit(exit_code)
