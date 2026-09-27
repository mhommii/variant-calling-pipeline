# Variant Calling Pipeline

A small, reproducible Nextflow pipeline: paired-end FASTQ in, VCF out.

> **How this was made:** a guided learning project built with Claude Code (an AI assistant), which wrote the code and the explanations. It is a learning exercise, not independent research. The *My notes* sections are left for me to fill in.

> **Status: written and ready to run, but not yet executed.** Nextflow needs a POSIX environment, and WSL has been installed on this machine but requires a restart before it works. The pipeline code, the configuration and the test data are all complete; the run and its results will be added here once WSL is active. I would rather say that plainly than show output I have not produced.

## What it does

```text
                    ┌─> FastQC ──────────────────┐
paired FASTQ ───────┤                            ├─> MultiQC report
                    └─> BWA-MEM ─> sorted BAM ───┤
                                       │         └─> samtools stats
                                       └─> bcftools mpileup/call ─> VCF
```

| Step | Tool | Container |
|---|---|---|
| Read QC | FastQC | `biocontainers/fastqc:0.12.1` |
| Index reference | BWA | `biocontainers/bwa:0.7.18` |
| Align + sort | BWA-MEM, samtools | biocontainers mulled image |
| Alignment stats | samtools | `biocontainers/samtools:1.21` |
| Variant calling | bcftools | `biocontainers/bcftools:1.21` |
| Aggregate QC | MultiQC | `biocontainers/multiqc:1.25.1` |

Every process declares its own pinned container, so versions do not depend on what happens to be installed on the machine.

## The test data is a known-answer test

Most small pipelines are tested by running them on a sample file and checking nothing crashed. That only shows it ran, not that it was right.

Here `bin/make_test_data.py` generates the data instead:

1. a random 20 kb reference chromosome,
2. a copy with **25 SNVs planted at known positions**,
3. simulated 150 bp paired-end reads from that copy (~30× coverage, 0.1% sequencing error, quality dropping towards the read end),
4. `data/truth.vcf` recording exactly what was planted.

Then `bin/check_against_truth.py` compares the pipeline's VCF against the truth set and reports recall and precision, failing if recall drops below 50%.

The data is small enough to commit (135 KB) and the seed is fixed, so regenerating it gives identical files.

Perfect scores are not expected: at 30× with simulated errors, a few spurious calls are normal, and variants in the reference's repeated stretches can be missed where reads align ambiguously. Seeing and explaining those numbers is the point.

## Running it

Requires WSL (or Linux/macOS) with Docker and Java 17+.

```bash
# one-time setup inside WSL
sudo apt update && sudo apt install -y openjdk-17-jre-headless
curl -s https://get.nextflow.io | bash && sudo mv nextflow /usr/local/bin/
# Docker Engine inside WSL is lighter than Docker Desktop on a small machine:
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER      # then restart the shell

# generate the test data and run
python3 bin/make_test_data.py
nextflow run main.nf -profile test,docker

# check the calls against the planted variants
python3 bin/check_against_truth.py
```

`-resume` re-runs only what changed, which is the main practical reason to use Nextflow over a shell script.

Outputs land in `results/`: `variants/*.vcf.gz`, `multiqc_report.html`, and `pipeline_info/` with a timeline and per-process resource trace.

## My notes

*(to be written by me)*

### On why pipelines need containers

### On the QC report

### On recall and precision

## Limitations

- **Not yet run.** See the status note above.
- **Small and simplified.** bcftools calling with no base-quality recalibration, no joint genotyping, no variant filtering, and SNVs only in the comparison script. [nf-core/sarek](https://github.com/nf-core/sarek) is the production-grade version of this idea and is the right thing to use for real work.
- **Synthetic data.** Generated reads are cleaner and more uniform than real sequencing data. Good for checking correctness, not for judging how the pipeline behaves on a real sample.
- **Resources are set for a laptop.** 2 CPUs and 2–3 GB per process, tuned for a 5.9 GB machine. A real dataset needs both more resources and a larger reference than this will comfortably handle.

## References

- Di Tommaso, P. et al. (2017). Nextflow enables reproducible computational workflows. *Nature Biotechnology*. https://doi.org/10.1038/nbt.3820
- Li, H. & Durbin, R. (2009). Fast and accurate short read alignment with Burrows–Wheeler transform. *Bioinformatics*. https://doi.org/10.1093/bioinformatics/btp324
- Danecek, P. et al. (2021). Twelve years of SAMtools and BCFtools. *GigaScience*. https://doi.org/10.1093/gigascience/giab008
- Ewels, P. et al. (2016). MultiQC: summarize analysis results for multiple tools and samples in a single report. *Bioinformatics*. https://doi.org/10.1093/bioinformatics/btw354
- Ewels, P. A. et al. (2020). The nf-core framework for community-curated bioinformatics pipelines. *Nature Biotechnology*. https://doi.org/10.1038/s41587-020-0439-x
- Garcia, M. et al. (2020). Sarek: A portable workflow for whole-genome sequencing analysis of germline and somatic variants. *F1000Research*. https://doi.org/10.12688/f1000research.16665.2
- FastQC: https://www.bioinformatics.babraham.ac.uk/projects/fastqc/
