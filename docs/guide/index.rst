.. _tcpm_guide:

######################
Guide
######################

.. note::

    Under Construction. Sorry. There really is a lot to document in this little tool so we're waiting to see how much
    interest there is from the community before investing in a full set of documents. For now all we have is the
    :ref:`tryme_page` tutorial.

.. invisible-code-block: python

    from tcpm import cli_main
    import pytest

.. code-block:: python

    with pytest.raises(SystemExit) as wrapped_exception:
        cli_main(["--help"])

Comments
================================================

TCPM preserves ``$comment`` strings and arrays as literal documentation, including in its vendor metadata and
shape templates. Braces and pQuery expressions inside comments are not evaluated. Comments in parameter maps,
shape maps, and exclusion rules do not participate in preset generation.

When shapes contribute different comments to the same object, TCPM combines them into an array without adding
duplicate entries. Existing comments are retained on regenerated presets with the same name, including when
``--clean`` is repeated. Nested comments are retained where the containing object survives; comments belonging
to removed presets or fields are removed with them.
