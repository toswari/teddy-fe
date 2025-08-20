# Compilation Instructions

This code requires a C++ extension, which modifies OpenCV's Hough lines function to also return the number of votes per line. To use this code:

 1. Download a copy of OpenCV's source code from [GitHub](https://github.com/opencv/opencv/releases/tag/4.12.0). Unzip the code into a subdirectory of this directory; I'll assume the subdirectory is named opencv-4.12.0.

 2. Build OpenCV by running:
```
cd opencv-4.12.0
mkdir -p build && cd build
cmake -DCMAKE_INSTALL_PREFIX=../../opencv ..
make -j8
make install
```

For further instructions on building OpenCV from source, look [here](https://docs.opencv.org/4.x/d7/d9f/tutorial_linux_install.html).

 3. Build the Python extension by returning to this directory and running:

```
python3 setup.py build
```

 4. Move the built library into this directory:

```
mv build/lib.*-cpython-*/hough.cpython-*.so .
```

 5. Test that you can import the lines object:

```
python3 -c "import lines"
```

If this runs without error, you're good to go.