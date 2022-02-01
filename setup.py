import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sparclur",
    version="2022.01.00",
    author="Shawn Davis",
    author_email="shawn@levelupresearch.com",
    description="Tools for analyzing PDF files and compare PDF parsers",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/pypa/sampleproject",
    packages=setuptools.find_packages('sparclur', 'sparclur.*'),
    python_requires='>=3.8',
    install_requires=[
        'pandas',
        'numpy',
        'scikit-image',
        'Pebble',
        'tqdm',
        'PyMuPDF',
        'Pillow',
        'matplotlib',
        'Pillow',
        'pytesseract',
        'spacy',
        'dill',
        'pdfminer-six',
        'opencv-python',
        'imagehash',
        'PyYAML',
        'mmh3',
        'seaborn',
        'plotly'
    ]
)
