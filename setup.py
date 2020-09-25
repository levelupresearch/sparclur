import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sparclur", # Replace with your own username
    version="0.0.1",
    author="Shawn Davis",
    author_email="shawn@levelupresearch.com",
    description="Tools for analyzing PDF files and compare PDF parsers",
    long_description=long_description,
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
        pandas,
        numpy,
        dask,
        sklearn,
        pebble,
        tqdm,
        fitz,
        pdf2image,
        PIL,
        torch,
        torchvision
    ]
)