suppressPackageStartupMessages(library(BSgenome))
tryCatch({
  forgeBSgenomeDataPkg('BSgenome.Aluchuensis.NCBI.IFO4308.seed')
}, error = function(e) {
  message('Error occurred: ', e$message)
  dir.create('./BSgenome.Aluchuensis.NCBI.IFO4308/inst/extdata/', recursive = TRUE, showWarnings = FALSE)
  file.copy('./GCF_016861625.1_AkawachiiIFO4308_assembly01_genomic.2bit', './BSgenome.Aluchuensis.NCBI.IFO4308/inst/extdata/single_sequences.2bit')
})
system('R CMD build BSgenome.Aluchuensis.NCBI.IFO4308')
system('R CMD INSTALL BSgenome.Aluchuensis.NCBI.IFO4308')
