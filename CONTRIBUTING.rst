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

.. code-block:: bash

    git clean -Xdf

Setting up a local development environment:

.. code-block:: bash

    tox --devenv .venv-py3.13 -e py313
    source .venv-py3.13/bin/activate
    code .

Running the tests:

.. code-block:: bash

    tox run-parallel

Generating coverage reports:

.. code-block:: bash

    tox run -e report

.. note::

    Report generation will fail if you haven't run the tests first to generate the intermediate artifacts this step
    consumes.

Running linters:

.. code-block:: bash

    tox run -e lint

Building the docs:

.. code-block:: bash

    tox run -e docs


pre-commit hooks
================================================

.. code-block:: bash

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


************************************************
Releasing tcpm
************************************************

Releases are built and published by ``.github/workflows/CI.yml``. The commands below assume
you are in the repository root, have a clean working tree, and are authenticated with the
GitHub CLI (``gh``) with permission to merge pull requests and create releases.

Prepare the version bump
================================================

Choose an unused version and the previous release tag. For example, to release 0.3.5 after
0.3.4, run the following commands in the same shell:

.. code-block:: bash

    TCPM_RELEASE_VERSION=0.3.5
    TCPM_PREVIOUS_TAG=v0.3.4
    git switch main
    git pull --ff-only origin main
    git switch -c "codex/release-${TCPM_RELEASE_VERSION}"

Update ``__version__`` in ``src/tcpm/version.py`` to match ``TCPM_RELEASE_VERSION``. This is
the version Flit embeds in the distribution metadata. Check the tag/version match and build
the wheel and source distribution locally:

.. code-block:: bash

    tox run -e checked_build -- --tag="refs/tags/v${TCPM_RELEASE_VERSION}"

Commit the version bump and open a pull request:

.. code-block:: bash

    git add src/tcpm/version.py
    git commit -m "release: bump version to ${TCPM_RELEASE_VERSION}"
    git push -u origin HEAD
    gh pr create --base main \
        --title "release: bump version to ${TCPM_RELEASE_VERSION}" \
        --body "Bump the package version to ${TCPM_RELEASE_VERSION}."
    gh pr checks --watch

Merge the pull request only after all required checks pass. If GitHub requires the branch
to be updated, update it and wait for the new checks before merging:

.. code-block:: bash

    gh pr merge --squash

Publish the release
================================================

Update local ``main`` and create the release at its exact commit. GitHub creates the tag if
it does not exist:

.. code-block:: bash

    git switch main
    git pull --ff-only origin main
    TCPM_RELEASE_COMMIT=$(git rev-parse HEAD)
    gh release create "v${TCPM_RELEASE_VERSION}" \
        --repo thirtytwobits/the-cmake-preset-matrix \
        --target "${TCPM_RELEASE_COMMIT}" \
        --title "v${TCPM_RELEASE_VERSION}" \
        --generate-notes \
        --notes-start-tag "${TCPM_PREVIOUS_TAG}"

.. important::

    Create the release directly without saving a draft. The workflow listens for
    ``release.created``; pushing a tag alone or publishing a previously saved draft does
    not start publishing. See `GitHub release events
    <https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#release>`_.

The release workflow runs validation, verifies that the tag matches the embedded version,
and builds both distributions. It then publishes to PyPI using trusted publishing through
the ``pypi`` GitHub environment. Finally, it signs the distributions with Sigstore and
creates a separate ``v<VERSION>.signed`` GitHub release containing the distributions and
their ``.sigstore.json`` bundles. That signed release is created automatically.

Verify publication
================================================

Find the release-triggered CI run:

.. code-block:: bash

    gh run list --workflow CI.yml --event release --branch "v${TCPM_RELEASE_VERSION}"

Use its run ID with ``gh run watch RUN_ID --exit-status`` and wait for validation, building,
PyPI publishing, and signing to succeed. Confirm that:

* ``https://pypi.org/project/tcpm/<VERSION>/`` lists the new version with both a wheel and a
  source distribution.
* The ``v<VERSION>.signed`` GitHub release contains both distributions and their Sigstore
  bundles.

Fetch the release tags locally:

.. code-block:: bash

    git fetch --tags origin
