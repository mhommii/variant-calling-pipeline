#!/usr/bin/env nextflow

/*
 * A small variant-calling pipeline: FASTQ in, VCF out.
 *
 *   reads --> FastQC ---------------------------\
 *         \-> BWA-MEM --> sorted BAM --> bcftools --> VCF
 *                                    \--> stats --> MultiQC report
 *
 * The point of writing this in Nextflow rather than a shell script is
 * reproducibility. Each process declares its own container, so the exact
 * version of bwa or bcftools is pinned and does not depend on what happens
 * to be installed. Nextflow handles staging files between steps, running
 * independent steps in parallel, and resuming from where a failed run
 * stopped (-resume).
 *
 * This is deliberately small: it calls variants with bcftools rather than
 * GATK, and has no base-quality recalibration, joint genotyping or variant
 * filtering. nf-core/sarek is the production-grade version of this idea.
 */

nextflow.enable.dsl = 2

params.reads     = "$projectDir/data/reads/*_{1,2}.fastq.gz"
params.reference = "$projectDir/data/reference.fasta"
params.outdir    = "results"

process FASTQC {
    tag "$sample_id"
    container 'quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0'
    publishDir "${params.outdir}/fastqc", mode: 'copy'

    input:
    tuple val(sample_id), path(reads)

    output:
    path "*_fastqc.{zip,html}", emit: reports

    script:
    """
    fastqc --threads ${task.cpus} ${reads}
    """
}

process BWA_INDEX {
    container 'quay.io/biocontainers/bwa:0.7.18--he4a0461_1'

    input:
    path reference

    output:
    path "${reference}.*", emit: index

    script:
    """
    bwa index ${reference}
    """
}

process BWA_MEM {
    tag "$sample_id"
    container 'quay.io/biocontainers/mulled-v2-fe8faa35dbf6dc65a0f7f5d4ea12e31a79f73e40:8110a70be2bfe7f75a2ea7f2a89cda4cc7732095-0'
    publishDir "${params.outdir}/alignment", mode: 'copy'

    input:
    tuple val(sample_id), path(reads)
    path reference
    path index

    output:
    tuple val(sample_id), path("${sample_id}.sorted.bam"),
                          path("${sample_id}.sorted.bam.bai"), emit: bam

    script:
    // The read group (-R) matters: downstream tools use it to tell samples
    // apart, and bcftools will not name the sample correctly without it.
    """
    bwa mem -t ${task.cpus} \\
        -R "@RG\\tID:${sample_id}\\tSM:${sample_id}\\tPL:ILLUMINA" \\
        ${reference} ${reads} \\
    | samtools sort -@ ${task.cpus} -o ${sample_id}.sorted.bam -
    samtools index ${sample_id}.sorted.bam
    """
}

process SAMTOOLS_STATS {
    tag "$sample_id"
    container 'quay.io/biocontainers/samtools:1.21--h50ea8bc_0'
    publishDir "${params.outdir}/stats", mode: 'copy'

    input:
    tuple val(sample_id), path(bam), path(bai)

    output:
    path "${sample_id}.stats", emit: stats

    script:
    """
    samtools stats ${bam} > ${sample_id}.stats
    """
}

process BCFTOOLS_CALL {
    tag "$sample_id"
    container 'quay.io/biocontainers/bcftools:1.21--h8b25389_0'
    publishDir "${params.outdir}/variants", mode: 'copy'

    input:
    tuple val(sample_id), path(bam), path(bai)
    path reference

    output:
    path "${sample_id}.vcf.gz", emit: vcf
    path "${sample_id}.vcf.gz.tbi"

    script:
    // mpileup walks the alignment column by column and reports the bases
    // seen at each position; call then decides which positions differ from
    // the reference. -mv keeps only variant sites.
    """
    bcftools mpileup -Ou -f ${reference} ${bam} \\
    | bcftools call -mv -Oz -o ${sample_id}.vcf.gz
    bcftools index --tbi ${sample_id}.vcf.gz
    """
}

process MULTIQC {
    container 'quay.io/biocontainers/multiqc:1.25.1--pyhdfd78af_0'
    publishDir "${params.outdir}", mode: 'copy'

    input:
    path '*'

    output:
    // MultiQC names the data folder after the report: <filename>_data.
    path "multiqc_report.html"
    path "multiqc_report_data"

    script:
    """
    multiqc . --filename multiqc_report.html
    """
}

workflow {
    reads = Channel.fromFilePairs(params.reads, checkIfExists: true)
    reference = file(params.reference, checkIfExists: true)

    FASTQC(reads)
    BWA_INDEX(reference)
    BWA_MEM(reads, reference, BWA_INDEX.out.index)
    SAMTOOLS_STATS(BWA_MEM.out.bam)
    BCFTOOLS_CALL(BWA_MEM.out.bam, reference)

    // Collect every QC output into one report.
    MULTIQC(
        FASTQC.out.reports.mix(SAMTOOLS_STATS.out.stats).collect()
    )

    // Registered inside the workflow block: Nextflow's strict syntax
    // (default from 25.x) rejects top-level statements outside a workflow.
    // `workflow` and `params` are both null inside the handler when it runs,
    // so capture what it needs first.
    def run    = workflow
    def outdir = params.outdir
    run.onComplete {
        log.info """
        Pipeline finished
          status   : ${run.success ? 'OK' : 'failed'}
          duration : ${run.duration}
          results  : ${outdir}/
        """.stripIndent()
    }
}
