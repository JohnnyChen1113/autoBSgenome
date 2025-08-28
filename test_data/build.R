suppressPackageStartupMessages(library(BSgenome))

tryCatch({
  if (dir.exists('BSgenome.Aluchuensis.NCBI.IFO4308')) { unlink('BSgenome.Aluchuensis.NCBI.IFO4308', recursive = TRUE) }
  forgeBSgenomeDataPkg('BSgenome.Aluchuensis.NCBI.IFO4308.seed')
}, error = function(e) {
  message('Error occurred during forgeBSgenomeDataPkg: ', e$message)
  # Fallback to manual creation if forging fails at certain steps
  dir.create('./BSgenome.Aluchuensis.NCBI.IFO4308/inst/extdata/', recursive = TRUE, showWarnings = FALSE)
  file.copy('./GCF_016861625.1_AkawachiiIFO4308_assembly01_genomic.2bit', './BSgenome.Aluchuensis.NCBI.IFO4308/inst/extdata/single_sequences.2bit')
})
system('R CMD build BSgenome.Aluchuensis.NCBI.IFO4308')
system('R CMD INSTALL BSgenome.Aluchuensis.NCBI.IFO4308')