"""Build a tiny test dataset with variants we know the answer to.

Downloading real sequencing data to test a pipeline has a problem: you do
not know what the right answer is, so "it ran" is all you can check. Here
the data is generated instead, so the true variants are known exactly and
the pipeline's VCF can be compared against them.

  1. Make a random reference chromosome.
  2. Copy it and introduce a known set of SNVs at known positions.
  3. Simulate paired-end reads from that mutated copy, with sequencing
     errors and realistic quality strings.
  4. Write the truth set to data/truth.vcf.

A correct pipeline should recover the planted variants and call few others.

Run:  python bin/make_test_data.py
"""

import gzip
import io
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
READS = DATA / "reads"

REFERENCE_LENGTH = 20_000
VARIANT_COUNT = 25
READ_LENGTH = 150
FRAGMENT_LENGTH = 400
COVERAGE = 30
ERROR_RATE = 0.001
SEED = 42

random.seed(SEED)
DATA.mkdir(exist_ok=True)
READS.mkdir(exist_ok=True)

BASES = "ACGT"


def open_text(path: Path):
    """Text file with Unix line endings, whatever the OS.

    On Windows, Python's text mode writes CRLF, which makes the files differ
    by platform and leaves stray carriage returns in the FASTQ.
    """
    return path.open("w", newline="\n")


def open_gzip_text(path: Path):
    """Gzipped text with Unix line endings and a fixed header timestamp.

    gzip records the time of writing in its header, so without mtime=0 every
    regeneration gives different bytes even when the content is identical.
    """
    raw = gzip.GzipFile(filename=path, mode="wb", mtime=0)
    return io.TextIOWrapper(raw, newline="\n")


def reverse_complement(sequence: str) -> str:
    return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]


# --- 1. Reference ----------------------------------------------------------
# Fully random sequence would be unrealistically easy to align. Repeating a
# little structure makes it slightly more honest without being obscure.
reference = []
while len(reference) < REFERENCE_LENGTH:
    if random.random() < 0.05:
        motif = "".join(random.choices(BASES, k=random.randint(4, 8)))
        reference.extend(motif * random.randint(2, 4))
    else:
        reference.append(random.choice(BASES))
reference = "".join(reference)[:REFERENCE_LENGTH]

with open_text(DATA / "reference.fasta") as handle:
    handle.write(">testchr synthetic test chromosome\n")
    for position in range(0, len(reference), 60):
        handle.write(reference[position:position + 60] + "\n")

# --- 2. Plant known variants ----------------------------------------------
# Keep them away from the very ends, where coverage falls off.
positions = sorted(random.sample(range(500, REFERENCE_LENGTH - 500),
                                 VARIANT_COUNT))
sample = list(reference)
truth = []
for position in positions:
    original = reference[position]
    replacement = random.choice([b for b in BASES if b != original])
    sample[position] = replacement
    # VCF is 1-based.
    truth.append((position + 1, original, replacement))
sample = "".join(sample)

with open_text(DATA / "truth.vcf") as handle:
    handle.write("##fileformat=VCFv4.2\n")
    handle.write("##reference=reference.fasta\n")
    handle.write(f"##contig=<ID=testchr,length={REFERENCE_LENGTH}>\n")
    handle.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
    for position, original, replacement in truth:
        handle.write(f"testchr\t{position}\t.\t{original}\t{replacement}"
                     f"\t.\tPASS\tPLANTED\n")

# --- 3. Simulate paired-end reads -----------------------------------------
read_pairs = (REFERENCE_LENGTH * COVERAGE) // (2 * READ_LENGTH)


def add_errors(sequence: str) -> str:
    return "".join(
        random.choice([b for b in BASES if b != base])
        if random.random() < ERROR_RATE else base
        for base in sequence
    )


# Phred+33 quality string; 'I' is Q40. Drop quality towards the read end,
# the way real Illumina data does.
quality = "".join(
    chr(33 + max(20, 40 - (index * 12) // READ_LENGTH))
    for index in range(READ_LENGTH)
)

with open_gzip_text(READS / "sample1_1.fastq.gz") as forward, \
     open_gzip_text(READS / "sample1_2.fastq.gz") as reverse:
    for read_number in range(read_pairs):
        start = random.randint(0, len(sample) - FRAGMENT_LENGTH)
        fragment = sample[start:start + FRAGMENT_LENGTH]
        read_1 = add_errors(fragment[:READ_LENGTH])
        read_2 = add_errors(reverse_complement(fragment[-READ_LENGTH:]))
        name = f"read{read_number}"
        forward.write(f"@{name}/1\n{read_1}\n+\n{quality}\n")
        reverse.write(f"@{name}/2\n{read_2}\n+\n{quality}\n")

print(f"reference : data/reference.fasta ({REFERENCE_LENGTH:,} bp)")
print(f"variants  : data/truth.vcf ({VARIANT_COUNT} planted SNVs)")
print(f"reads     : data/reads/sample1_{{1,2}}.fastq.gz "
      f"({read_pairs:,} pairs, ~{COVERAGE}x coverage)")
print(f"seed      : {SEED} (regenerating gives identical data)")
