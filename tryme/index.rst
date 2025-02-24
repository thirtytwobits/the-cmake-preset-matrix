.. _tryme_page:

################################################
Try Me
################################################

In the `TCPM try me <tryme_>`_ directory we provide a ready-made template so you can see how `TCPM`_ works for yourself.
Simply `download this file <tryme_raw>`_ into a new directory, ``cd`` into the directory, and do:

.. code-block:: bash

    tcpm

What just happened?
************************************************

You should now have a, relatively large, ``CMakePresets.json`` file in this directory. It was generated from
``CMakePresetsVendorTemplate.json`` which is the default name for `TCPM`_ templates. Let's take a look at this file:

.. literalinclude:: CMakePresetsVendorTemplate.json
  :language: JSON
  :linenos:

The first thing you might notice is this is a valid `CMakePresets.json`_ file with a single ``"configurePresets"``
entry, ``"configure-common"``. The template part of this file is found in the top-level ``"vendor"`` section starting
with the ``tcpm`` object on line 29. In this object the ``preset-groups`` object should look a bit familiar having
objects named "configure", "build", and "workflow". Each of these corresponds to preset groups by simple textual
concatenation of "Presets" to the end of the identifier (e.g. "configure" => "configurePresets").

On line 41, the ``"configure"`` object contains all of the information used to generate ``"configurePresets"``. Let's
go over each item in this object:

.. list-table::
  :header-rows: 1

  * - Key
    - Req'd?
    - Type
    - Description
  * - ``"name"``
    - no
    - string
    - A name for this object to allow direct addressing in pQuery statements as ``$('#{identifier}')``.
  * - ``"common"``
    - no
    - array[string]
    - A list of ``"configurePresets"`` entries that all generated configure presets will inherit from.
      This field is only used for for ``"configure"`` presets group.
  * - ``"parameters"``
    - yes
    - object[string, array[string]]
    - This is where the magic happens. Parameters define each dimension of a matrix and it is the cartesian product of
      each of these parameter lists that `TCPM`_ uses to generate new presets.
  * - ``"shape-parameters"``
    - no
    - object[string, array[string]]
    - The same as parameters except these are not used to create presets but, for any presets created, are used to
      instatiate parameterized shapes for each preset.
  * - ``"shape"``
    - no
    - object[string, object]
    - Shapes act like templates for parameters and shape-parameters. Each shape is used when a given parameter is part
      of a new preset definition to append additional data to the preset object. ``"cacheVariables"``, for example, can
      be defined for new presets using shapes whereas worflow steps can be defined using shape-parameterized shapes.

In our example we generated every posible configuration needed to build a project for three different toolchains using
three different C++ standards. Let's suppose we want to run these build presets using Github Actions. We'd find that
this system supports a similar syntax for defining a matrix of build jobs:

.. code-block:: yaml

  jobs:
    example_matrix:
      strategy:
        matrix:
          toolchain: ["gcc-native", "gcc-native-32", "clang-native"]
          standard:  ["cpp-14", "cpp-17", "cpp-20"]
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - run: cmake --workflow --preset workflow-${{ matrix.toolchain }}-${{ matrix.standard }}

Let's say we don't want to build ``"cpp-20"`` using the ``"gcc-native-32"`` toolchain. Github actions allows pruning the
result set using ``exclude``. For example:

.. code-block:: yaml

  jobs:
    example_matrix:
      strategy:
        matrix:
          toolchain: ["gcc-native", "gcc-native-32", "clang-native"]
          standard:  ["cpp-14", "cpp-17", "cpp-20"]
        exclude:
          - toolchain: gcc-native-32
            standard: cpp-20
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - run: cmake --workflow --preset workflow-${{ matrix.toolchain }}-${{ matrix.standard }}


`TCPM`_ supports a similar syntax in JSON form to prevent generation of this workflow:

.. code-block:: json

  "exclude": [
      {
          "toolchain": "gcc-native-32",
          "standard": "cpp-20"
      }
  ],

Try adding the above exclude to the ``CMakePresetsVendorTemplate.json`` under
``["vendor"]["tcpm"]["preset-groups"]["workflow"]``. Now do ``tcpm -f`` (``-f`` to force overwrite of the existing
``CMakePresets.json`` file) and you'll have a slightly smaller presets file that does not provide a workflow for this
combination of parameters.

.. _`CMakePresets.json`: https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html
.. _`TCPM`: https://github.com/thirtytwobits/the-cmake-preset-matrix
.. _`tryme`: https://github.com/thirtytwobits/the-cmake-preset-matrix/tree/main/tryme
.. _`tryme_raw`: https://raw.githubusercontent.com/thirtytwobits/the-cmake-preset-matrix/refs/heads/main/tryme/CMakePresetsVendorTemplate.json