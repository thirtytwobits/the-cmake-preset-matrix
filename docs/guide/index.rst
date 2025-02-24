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
