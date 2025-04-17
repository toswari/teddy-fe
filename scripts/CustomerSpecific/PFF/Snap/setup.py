from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="snap_detection",
    version="0.1.0",
    author="Chris Mulder",
    author_email="mulder@clarifai.com",
    description="A package for detecting the snap moment in football videos",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Image Processing",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "numpy>=1.19.0",
        "opencv-python>=4.5.0",
        "matplotlib>=3.3.0",
        "imageio>=2.9.0",
    ],
) 