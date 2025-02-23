.. _tryme_page:

################################################
Try Me
################################################

In the `TCPM try me <tryme_>`_ directory we provide a ready-made template so you can see how `TCPM`_ works for yourself.
Simply pull this file (or ``cd`` into the `tryme`_ directory if you are working with the source) and do:

.. code-block:: bash

    tcpm

What just happened?
************************************************

You should have a file in your directory; a ``CMakePresets.json`` file (the output). This will be a relatively large
file. It was generated from ``CMakePresetsVendorTemplate.json`` which is the default name of `TCPM`_ templates. Let's
take a look at this file:

.. literalinclude:: CMakePresetsVendorTemplate.json
  :language: JSON
  :linenos:

The first thing you should notice is this is a valid `CMakePresets.json`_ file with a single ``"configurePresets"``
entry, ``"config-common"``. Other standards preset sections are defined but are empty (e.g. ``"buildPresets": []`` etc).
The template part of this file is found in the top-level ``"vendor"`` section starting with the ``tcpm`` object on line
33. In this object the ``preset-groups`` object should look a bit familiar in it's

.. _`CMakePresets.json`: https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html
.. _`TCPM`: https://github.com/thirtytwobits/the-cmake-preset-matrix
.. _`tryme`: https://github.com/thirtytwobits/the-cmake-preset-matrix/tree/main/tryme