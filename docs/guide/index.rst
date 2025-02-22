
######################
Guide
######################

.. invisible-code-block: python

    from tcpm import cli_main
    import pytest

.. code-block:: python

    with pytest.raises(SystemExit) as wrapped_exception:
        cli_main(["--help"])
