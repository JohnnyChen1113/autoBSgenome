# Test Accessions for AutoBSgenome

Use these accessions to test the web tool at https://autobsgenome.pages.dev

## NCBI (Small genomes — fast builds)

| Organism | Accession | Size | Notes |
|----------|-----------|------|-------|
| *Aspergillus luchuensis* | GCF_016861625.1 | ~33 MB | Koji mold, no circular seqs |
| *Saccharomyces cerevisiae* | GCF_000146045.2 | ~12 MB | Yeast, has MT |
| *Escherichia coli* K-12 | GCF_000005845.2 | ~4.6 MB | Bacteria, no plasmids in this strain |

## NCBI (Medium genomes)

| Organism | Accession | Size | Notes |
|----------|-----------|------|-------|
| *Drosophila melanogaster* | GCF_000001215.4 | ~140 MB | Fruit fly, has MT |
| *Caenorhabditis elegans* | GCF_000002985.6 | ~100 MB | Worm, has MT |
| *Arabidopsis thaliana* | GCF_000001735.4 | ~120 MB | Plant, has MT + Chloroplast |

## NCBI (Large genomes — slower builds)

| Organism | Accession | Size | Notes |
|----------|-----------|------|-------|
| *Danio rerio* | GCF_000002035.6 | ~1.4 GB | Zebrafish, has MT |
| *Mus musculus* | GCF_000001635.27 | ~2.7 GB | Mouse, has MT |
| *Homo sapiens* | GCF_000001405.40 | ~3.1 GB | Human, has MT |

## GenBank (GCA_ — tests GCF suggestion)

| Organism | Accession | Paired GCF | Notes |
|----------|-----------|------------|-------|
| *Danio rerio* | GCA_000002035.4 | GCF_000002035.6 | Should suggest switching to GCF |
| *Sorghum bicolor* | GCA_000003195.3 | GCF_000003195.3 | Crop plant |

## Ensembl

| Organism | URL/Name | Notes |
|----------|----------|-------|
| *Danio rerio* | `https://www.ensembl.org/Danio_rerio/Info/Index` | Zebrafish |
| *Saccharomyces cerevisiae* | `saccharomyces_cerevisiae` | Yeast (plain name) |
| *Arabidopsis thaliana* | `https://www.ensembl.org/Arabidopsis_thaliana/Info/Index` | Plant |
