import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sparclur",
    version="0.1.0",
    author="Shawn Davis",
    author_email="shawn@levelupresearch.com",
    description="Tools for analyzing PDF files and compare PDF parsers",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/pypa/sampleproject",
    packages=setuptools.find_packages('sparclur', 'sparclur.*'),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
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
        'ghostscript'
    ]
)