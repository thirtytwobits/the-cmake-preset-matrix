#####################
Contributor Notes
#####################

|:wave:| Thanks for contributing. This page contains all the details about getting
your dev environment setup.

.. note::

    This is documentation for contributors developing tcpm. If you are
    a user of this software you can ignore everything here.


************************************************
Tools
************************************************

tox
================================================

Starting clean:

    git clean -Xdf

Setting up a local development environment:

    tox --devenv .venv-py3.13 -e py313
    source .venv-py3.13/bin/activate
    code .

Running the tests:

    tox run-parallel

Generating coverage reports:

    tox run -e report

.. note::

    Report generation will fail if you haven't run the tests first to generate the intermediate artifacts this setup
    consumes.

Running linters:

    tox run -e lint

Building the docs:

    tox run -e docs


pre-commit hooks
================================================


    pip install pre-commit
    pre-commit install


Sybil Doctest
================================================

This project makes extensive use of `Sybil <https://sybil.readthedocs.io/en/latest/>`_ doctests.
These take the form of docstrings with a structure like thus::

    .. invisible-code-block: python

        from tcpm._pquery import default_replace_value_if_predicate, ReturnValue

    .. code-block:: python

        my_return_value = ReturnValue(["result value"])

    >>> default_replace_value_if_predicate("dynamic value", my_return_value)
    False

The invisible code block is executed but not displayed in the generated documentation and,
conversely, ``code-block`` is both rendered using proper syntax formatting in the documentation
and executed. REPL works the same as it does for :mod:`doctest` but ``assert`` is also a valid
way to ensure the example is correct especially if used in a trailing ``invisible-code-block``::

    .. invisible-code-block: python

        assert not default_replace_value_if_predicate("dynamic value", my_return_value)

These tests are run as part of the regular pytest build. You can see the Sybil setup in the
``conftest.py`` found under the project directory but otherwise shouldn't need to worry about
it. The simple rule is; if the docstring ends up in the rendered documentation then your
``code-block`` tests will be executed as unit tests and will be counted in the project's
coverage numbers.
