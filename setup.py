import setuptools

from setuptools import setup
import pathlib
import os
import sys
module_path = os.path.abspath('.')
if module_path not in sys.path:
    sys.path.append(module_path)

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

setup(
    name="sparclur",
    version='2022.5.3',
    author="Shawn Davis",
    author_email="shawn@levelupresearch.com",
    description="Tools for analyzing PDF files and comparing PDF parsers",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/levelupresearch/sparclur",
    packages=setuptools.find_packages(),
    data_files=[('etc/sparclur/', ['resources/sparclur.yaml']),
                ('etc/sparclur/resources/',
                 ['resources/hello_world_hand_edit.pdf', 'resources/min_vi.pdf', 'resources/AH20210114-modified.pdf'])
                ],
    python_requires='>=3.8',
    license='Apache-2.0',
    install_requires=[
        'pandas',
        'func-timeout',
        'numpy',
        'scikit-image',
        'scikit-learn',
        'Pebble',
        'tqdm',
        'PyMuPDF',
        'Pillow',
        'matplotlib',
        'Pillow',
        'pytesseract',
        'spacy',
        'dill',
        'pdfminer.six',
        'pypdfium2',
        'opencv-python',
        'ImageHash',
        'PyYAML',
        'mmh3',
        'seaborn',
        'plotly',
        'docstring-inheritance'
    ]
)
