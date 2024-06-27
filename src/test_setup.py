"""Ensures that python modules can be imported.

- https://stackoverflow.com/a/47188103/6847689
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
