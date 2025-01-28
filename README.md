# Image Correspondence Annotation Tool

How to build:

1. Clone the repo in your desired runtime environment. This could be windows or linux. If it is Linux, make sure that the version of glibc on the build machine is the same or older than on the machine you intend to run the tool on. Check the version by running `>ldd --version`.
2. In a clean venv\pipenv\conda env with python 3.9 or newer, install the requirements.
3. From the main project directory, run `pyinstaller main.spec`
4. The executable should be inside the `dist` directory.
