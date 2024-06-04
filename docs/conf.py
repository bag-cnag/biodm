# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

# import os
# import sys
# sys.path.insert(0, os.path.abspath("../src/biodm/"))


from typing import Any, Sequence
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
    'python': ('https://docs.python.org/3', None),
    'sqlalchemy': ('https://docs.sqlalchemy.org/en/20/', None),
    # 'marshmallow': ('https://marshmallow.readthedocs.io/', None),
}


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = 'alabaster'
html_theme = "sphinx_rtd_theme"
html_static_path = ['_static']

# Flags
add_module_names = False

# Homebrew rules.
# def remove_after_marker(marker: str, what: Sequence[str] | None = None):
#     """Returns a listerner that skims all that's after the last line equal to '---'."""
#     def process(app, 
#                 what_: str, 
#                 name: str, obj: Any, 
#                 options: Any, 
#                 lines: list[str]
#     ) -> None:
#         if what and what_ not in what:
#             return
#         try:
#             lines = lines[lines.index(marker):]
#         except ValueError:
#             pass
#         # make sure there is a blank line at the end
#         if lines and lines[-1]:
#             lines.append('')
#     return process

# def remove_yaml_from_docstrings(app, what, name, obj, options, lines):
#     if what and "---" not in what:
#         return
#     try:
#         del lines[lines.index("---"):]
#     except ValueError:
#         return
#     if lines and lines[-1]:
#         lines.append('')

def setup(app):
    # app.connect('autodoc-process-docstring', remove_yaml_from_docstrings)
    # app.connect('autodoc-process-docstring', remove_after_marker('---'))
    app.connect('autodoc-process-docstring', between(marker="---"))
    return app
