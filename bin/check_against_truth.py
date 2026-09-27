"""Compare the pipeline's calls against the variants we planted.

Because the test data was generated with known variants (bin/make_test_data.py),
this is a real known-answer test rather than a "did it run without crashing"
check. It reports:

  recall     - how many planted variants were found
  precision  - how many calls correspond to a planted variant

Perfect scores are not expected. Simulated sequencing errors at 30x coverage
produce a few spurious calls, and variants landing in the repeated stretches
of the reference can be missed because reads there align ambiguously. The
point is to see the numbers and be able to explain them.

Run:  python bin/check_against_truth.py
"""

import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
truth_path = ROOT / "data" / "truth.vcf"
called_dir = ROOT / "results" / "variants"


def read_vcf(path: Path) -> set:
    """Position, reference and alternate allele for each SNV in a VCF."""
    opener = gzip.open if path.suffix == ".gz" else open
    variants = set()
    with opener(path, "rt") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.split("\t")
            position, reference, alternate = fields[1], fields[3], fields[4]
            # Single-nucleotide changes only; indels are out of scope here.
            if len(reference) == 1 and len(alternate) == 1:
                variants.add((int(position), reference, alternate))
    return variants


if not truth_path.exists():
    sys.exit("data/truth.vcf missing - run bin/make_test_data.py first.")

called_files = sorted(called_dir.glob("*.vcf.gz")) if called_dir.exists() else []
if not called_files:
    sys.exit(f"No VCF found in {called_dir.relative_to(ROOT)} - "
             f"run the pipeline first.")

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
              f"{', '.join(str(p) for p, _, _ in shown)}"
              f"{' ...' if len(missed) > 5 else ''}")

    # A pipeline this simple should still find most planted variants. If it
    # finds well under half, something is wrong rather than merely noisy.
    if recall < 0.5:
        print("  FAIL: recall below 50% - the pipeline is not working "
              "as intended, not just noisy.")
        exit_code = 1

sys.exit(exit_code)
