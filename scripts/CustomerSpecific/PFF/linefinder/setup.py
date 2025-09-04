from setuptools import find_packages, setup

import cv2
from pybind11.setup_helpers import Pybind11Extension


COMPILE_ARGS = []

REQUIREMENTS = [
    'opencv-python',
    'pybind11',
]


if __name__ == '__main__':
    # Create pybind11 extension
    ext_modules = [
        Pybind11Extension(
            'hough',
            ['hough.cpp'],
            cxx_std=17,
            extra_compile_args=COMPILE_ARGS,
            include_dirs=['opencv/include/opencv4/'],
            library_dirs=['opencv/lib/'],
            libraries=['opencv_core', 'opencv_imgproc'],
            runtime_library_dirs=['opencv/lib/'],
        ),
    ]

    setup(
        name='hough',
        version='0.1',
        author='Mark Lowell',
        packages=find_packages(),
        install_requires=REQUIREMENTS,
        ext_modules=ext_modules,
    )
