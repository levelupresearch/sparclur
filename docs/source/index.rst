.. SPARCLUR documentation master file, created by
   sphinx-quickstart on Fri May  6 10:25:59 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

SPARCLUR documentation
======================

SPARCLUR provides wrappers around PDF parsers and renderers, together with
tools for comparing validity, renders, text, traces, incremental updates, and
repeatability.

Getting started
---------------

Install the core package with ``pip install sparclur``. Python-backed parser
adapters and the Streamlit interface are optional extras:

.. code-block:: console

   pip install "sparclur[ui,mupdf,pdfium]"
   sparclur-ui

SPARCLUR supports Python 3.10 and newer. External parser wrappers also need
their respective command-line tools installed or configured. See the project
`README <https://github.com/levelupresearch/sparclur#readme>`_ for parser
prerequisites, configuration, the UI workflow, and example notebooks.

Configuration
-------------

SPARCLUR reads layered YAML configuration for parser defaults. The normal
user-editable path and current effective values are available from Python:

.. code-block:: python

   from sparclur.utils import get_config, get_config_path, update_config

   print(get_config_path())
   update_config({"Poppler": {"binary_path": "/path/to/poppler/bin"}})
   print(get_config())

Set ``SPARCLUR_CONFIG`` to use a specific YAML file. The packaged
``examples/sparclur.yaml`` file is a reference template, not an automatically
applied configuration.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
