"""
testcase_generator/generator_interface.py
==========================================
Re-exports the canonical ``ITestCaseGenerator`` ABC from the project-wide
interfaces package so that all generators in this package can use a single,
consistent local import path.

Concrete generators inside ``testcase_generator/`` should import from here:

    from testcase_generator.generator_interface import ITestCaseGenerator

The authoritative definition lives in:
    interfaces/generator_interface.py

Do NOT duplicate the class definition here.
"""

from interfaces.generator_interface import ITestCaseGenerator  # noqa: F401

__all__ = ["ITestCaseGenerator"]
