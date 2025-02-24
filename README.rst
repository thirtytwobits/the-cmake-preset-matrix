################################################
 TCPM: (the) Cmake Preset Matrix
################################################

|badge_build|_ |badge_pypi_support|_ |badge_pypi_version|_ |badge_docs|_

`TCPM`_ is a `CMakePresets.json`_ transformation tool that generates presets for the cartesian product of a set of
parameters. For example, given two toolchains :

.. code-block:: json

    "toolchain": [
        "gcc",
        "clang"
    ],

and two different c++ language standards:

.. code-block:: json

    "standard": [
        "cpp-20",
        "cpp-23"
    ],

the ``tcpm`` tool will generate four (4) configuration presets:

.. code-block:: json

    {
        "name": "configure-gcc-cpp-20"
    },
    {
        "name": "configure-gcc-cpp-23"
    },
    {
        "name": "configure-clang-cpp-20"
    },
    {
        "name": "configure-clang-cpp-23"
    },


If you added a third parameter list with two items then `TCPM`_ would generate eight (8) configurations, the cartesian
product producing :math:`|A| \times |B| = |A| * |B|` items.

`TCPM`_ also provides a template language to allow generation of various preset fields like ``"cacheVariables"``. These
templates, called "shapes" in the json, are given contextual tokens to use in string expansion and, for more complex
logic, the ``pQuery`` DSL embedded in `TCPM`_ allows procedural expansion of fields based on the state of a presets
document at the time a given preset is generated.

There's a lot more to it, of course, and `TCPM`_ provides a complete JSON transformation language for presets json in
in addition to other features. To get started we reccommend starting with the
`Try Me`_ exercise or heading over to the `Guide`_.

.. note ::

    This is alpha software. A lot will change before 1.0. Your input is required to get there.
    Thanks for helping ❤️

    This project is an experiment, a proposal, a tool. One of these three things will become the roadmap for it over
    time. As an experiment, this tool will explore the utility of `CMakePresets.json`_ which makes direct integration
    of cmake with CI worflows possible. As a proposal, this project demonstrates certain functionality not available in
    the current version of `CMakePresets.json`_ as a suggestion to `Kitware`_ when evolving this part of their product.
    Finally, this is a tool that will continue to aid complex projects in the management of their preset files
    whether or not `Kitware`_ adds similar features supporting matrix builds in the future.


Key Features
************************************************

* **Matrix Builds** – Provides a way to manage large matrices of build types for complex projects that doesn't require
  copy-and-paste or a lot of typing 😩
* **Idempotent** – The tool will continue to produce the same output given the same parameters as inputs. This allows
  automated generation of `CMakePresets.json`_ files from themselves or using separate template files.
* **Preserves Existing Presets** – Any presets that are manually added to a `CMakePresets.json`_ file will be maintained
  when using the "expand-in-place" features of this tool.

.. _`TCPM`: https://github.com/thirtytwobits/the-cmake-preset-matrix

.. _`Kitware`: https://www.kitware.com/

.. _`CMakePresets.json`: https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html

.. _`Try Me`: tryme/

.. _`Guide`: docs/guide/

.. |tcpm_logo| image:: /docs/static/SVG/matrix_logo.svg
   :width: 50px

.. |badge_build| image:: https://github.com/thirtytwobits/the-cmake-preset-matrix/actions/workflows/CI.yml/badge.svg
    :alt: Build status
.. _badge_build: https://github.com/thirtytwobits/the-cmake-preset-matrix/actions/workflows/CI.yml

.. |badge_pypi_support| image:: https://img.shields.io/pypi/pyversions/tcpm.svg
    :alt: Supported Python Versions
.. _badge_pypi_support: https://pypi.org/project/tcpm/

.. |badge_pypi_version| image:: https://img.shields.io/pypi/v/tcpm.svg
    :alt: PyPI Release Version
.. _badge_pypi_version: https://pypi.org/project/tcpm/

.. |badge_docs| image:: https://img.shields.io/github/deployments/thirtytwobits/the-cmake-preset-matrix/github-pages?label=docs&logo=github
   :alt: GitHub deployments
.. _badge_docs: https://thirtytwobits.github.io/the-cmake-preset-matrix
