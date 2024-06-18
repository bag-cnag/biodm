# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

# import os
# import sys
# sys.path.insert(0, os.path.abspath("../src/biodm/"))


# from typing import Any, Sequence
from sphinx_pyproject import SphinxConfig
from sphinx.ext.autodoc import between
from biodm import __version__ as ver

config = SphinxConfig("../pyproject.toml", globalns=globals(), config_overrides = {"version": ver})

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx_rtd_theme',
    'sphinx_mdinclude',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', 'biodm.tests*', '*conftest*']
intersphinx_mapping = {
    'sqlalchemy': ('https://docs.sqlalchemy.org/en/20/', None),
}
# 'python': ('https://docs.python.org/3', None),
# 'marshmallow': ('https://marshmallow.readthedocs.io/en/stable/', None),


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = 'alabaster'
html_theme = "sphinx_rtd_theme"
html_static_path = ['_static']

# Flags
add_module_names = False

# Remove OpenAPI docstrings delimited by (---).
def setup(app):
    app.connect('autodoc-process-docstring', between(marker="---", exclude=True))
    return app
