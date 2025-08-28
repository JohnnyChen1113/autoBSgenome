###
###

.pkgname <- "BSgenome.Aluchuensis.NCBI.IFO4308"

.seqnames <- NULL

.circ_seqs <- character(0)

.mseqnames <- NULL

.onLoad <- function(libname, pkgname)
{
    if (pkgname != .pkgname)
        stop("package name (", pkgname, ") is not ",
             "the expected name (", .pkgname, ")")
    extdata_dirpath <- system.file("extdata", package=pkgname,
                                   lib.loc=libname, mustWork=TRUE)

    ## Make and export BSgenome object.
    bsgenome <- BSgenome(
        organism="Aspergillus luchuensis",
        common_name="Aspergillus luchuensis",
        genome="IFO4308",
        provider="NCBI",
        release_date="09. 2024",
        source_url="",
        seqnames=.seqnames,
        circ_seqs=.circ_seqs,
        mseqnames=.mseqnames,
        seqs_pkgname=pkgname,
        seqs_dirpath=extdata_dirpath
    )

    ns <- asNamespace(pkgname)

    objname <- pkgname
    assign(objname, bsgenome, envir=ns)
    namespaceExport(ns, objname)

    old_objname <- "Aluchuensis"
    assign(old_objname, bsgenome, envir=ns)
    namespaceExport(ns, old_objname)
}

