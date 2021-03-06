.. _pyenv-install:

Installing python 3.4 as a user
-------------------------------

Pyenv (x86/x86_64 only)
=======================

Pyenv_ is a useful script that allows you to install several python versions
in your user directory, and lets you manage which one you want depending on
the directory you are in. It is therefore useful for people who are on
distributions not providing the latest stable version, such as Debian or
CentOS.

You can follow the step-by-step `installation tutorial`_ on github that will
help you install it to your home directory (on step 5, you should use 3.4.2
which is the latest python 3.4 release at the time of writing this page); or
you can use the `automated installer`_ and use ``pyenv install 3.4.2``
thereafter.

Then you only need to add a ``.python-version`` file containing ``3.4.2`` in
your poezio directory to make the python version in that directory default to
the python 3.4.2 installed with pyenv.

Building your own python 3
==========================

- Go to the `python download page`_
- Select the “Latest Python 3 Release”
- Download a tarball and extract it
- Run ``./configure && make`` (takes a few minutes even on old CPUs)
- Edit the poezio launch.sh script to make it call your user-compiled python


.. _Pyenv: https://github.com/yyuu/pyenv
.. _installation tutorial: https://github.com/yyuu/pyenv#installation
.. _automated installer: https://github.com/yyuu/pyenv-installer
.. _python download page: https://www.python.org/downloads/source/
