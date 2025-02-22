# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
from tcpm.version import __version__ as tcpm_version

project = "tcpm"
copyright = "Amazon.com Inc. or its affiliates."
author = "thirtytwobits"
release = tcpm_version

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.doctest",
    "sphinx.ext.coverage",
    "sphinx.ext.imgmath",
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",
    "sphinx.ext.extlinks",
    "sphinxarg.ext",
    "sphinx.ext.intersphinx",
    "sphinxemoji.sphinxemoji",
]

exclude_patterns = ["**/tests", ".vscode/*", ".github/*"]

with open(".gitignore", encoding="utf-8") as gif:
    for line in gif:
        stripped = line.strip()
        if len(stripped) > 0 and not stripped.startswith("#"):
            exclude_patterns.append(stripped)

language = "en"

source_suffix = [".rst"]

pygments_style = "monokai"

# Classes should inherit documentation from ancestors.
autodoc_inherit_docstrings = True

# -- Options for HTML output -------------------------------------------------

html_theme = "furo"

html_context = {
    "display_github": True,
    "github_user": "OpenCyphal",
    "github_repo": "nunavut",
    "github_version": "main",
    "conf_py_path": "",
}

html_static_path = ["docs/static"]

html_logo = "docs/static/SVG/matrix_logo.svg"

html_favicon = "docs/static/SVG/matrix_logo.svg"

# -- Options for intersphinx extension ---------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
