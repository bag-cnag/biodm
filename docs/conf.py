# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
from typing import Callable, Any, Sequence
from sphinx_pyproject import SphinxConfig
from sphinx.ext.autodoc import between
from biodm import __version__ as ver

config = SphinxConfig("../pyproject.toml", globalns=globals(), config_overrides = {"version": ver})

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx.ext.autodoc', 'sphinx_rtd_theme']

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = 'alabaster'
html_theme = "sphinx_rtd_theme"
html_static_path = ['_static']


### Homebrew rules.
def remove_after_marker(marker: str, what: Sequence[str] | None = None):
    """Returns a listerner that skims all that's after the last line equal to '---'."""
    def process(app, 
                what_: str, 
                name: str, obj: Any, 
                options: Any, 
                lines: list[str]
    ) -> None:
        if what and what_ not in what:
            return
        try:
            idx = lines.index(marker)
            del lines[idx:]
            # make sure there is a blank line at the end
            if lines and lines[-1]:
                lines.append('')
        except:
            pass
    return process

def setup(app):
    app.connect('autodoc-process-docstring', remove_after_marker('---'))
    return app
