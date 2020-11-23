# SPARCLUR - Some PDF Analyzers and Renderer Comparators: LevelUp Research

SPARCLUR (Sparclur) is a a collection of various wrappers for extant PDF 
parsers and renderers and tools for comparing and analyzing the outputs from
these parsers.

## Parsers
The following parsers need to either be installed or the binaries need to be built and accessible to fully leverage Sparclur. The version numbers listed with the parsers indicate the most recent compatible versions tested with Sparclur, though various previous versions of all parsers have been as well.

* MuPDF (1.16.1)
* QPDF (9.1.0)
* Poppler (pdftoppm and pdftocairo) (0.65.0)
  * XPDF (20.11.0) binaries have also been substituted
* Ghostscript (9.53.3)

## Tools
## Parser Trace Comparator (PTC)
Gather and normalize warning and error messages from extant parsers.

## PDF Renderer Comparator (PRC)

The PRC compares different renderers over the same documents and can also be used
to visualize the differences and produce a similarity metric.

## Streamlit Interface

Running light_the_sparclur.sh will launch a Streamlit web app that will provide an interface for 
exploring PDF's using the PTC and PRC.
![](./images/lit_sparclur_ptc_no_warnings.png)
![](./images/lit_sparclur_prc_2.png)
![](./images/lit_sparclur_ptc_warnings.png)

# Acknowledgements

This material is based upon work supported by the Defense Advanced Research 
Projects Agency (DARPA) under Contract No. HR0011-18-S-0054. Any opinions, 
findings and conclusions or recommendations expressed in this material are 
those of the author(s) and do not necessarily reflect the views of the 
Defense Advanced Research Projects Agency (DARPA).

# Contributors

