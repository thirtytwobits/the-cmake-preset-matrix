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

Preset prefixes
================================================

Each entry in ``vendor.tcpm.preset-groups`` accepts a ``prefix`` string, which defaults to the group name
(``configure``, ``build``, ``test``, ``package``, or ``workflow``). TCPM adds the separator between the prefix and
each parameter; the prefix does not need a trailing separator.

For example, a configure group with ``"prefix": "config"`` and ``"parameters": {"mode": ["debug"]}`` generates
the hidden preset ``config-mode-debug`` and the visible preset ``config-debug``. The visible preset inherits
from ``config-mode-debug``. Shape templates can use ``{prefix}`` for the current group's prefix and
``{groups[configure][prefix]}`` to reference the configure group's prefix from another group.

When upgrading files generated before custom prefixes were applied to hidden presets, use ``--clean`` to remove
legacy hidden names such as ``configure-mode-debug``. Cleanup recognizes the legacy namespaces of the configure
group's current parameter names, including obsolete values, while retaining presets listed in ``common``.
Without ``--clean``, existing presets remain in the document.

Hidden and visible presets must have distinct names. For example, ``"mode": ["debug", "mode-debug"]`` would
generate ``config-mode-debug`` as both a hidden and a visible preset. TCPM reports a name collision instead of
merging these objects; change the parameter names or values to remove the ambiguity.

Comments
================================================

TCPM preserves ``$comment`` strings and arrays as literal documentation, including in its vendor metadata and
shape templates. Braces and pQuery expressions inside comments are not evaluated. Comments in parameter maps,
shape maps, and exclusion rules do not participate in preset generation.

When shapes contribute different comments to the same object, TCPM combines them into an array without adding
duplicate entries. Existing comments are retained on regenerated presets with the same name, including when
``--clean`` is repeated. Nested comments are retained where the containing object survives; comments belonging
to removed presets or fields are removed with them.
