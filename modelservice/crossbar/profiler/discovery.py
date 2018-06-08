"""
This module contains methods for the discovery and importing of profiling tasks.
"""
import unittest


def _testMethod_path(testMethod):
    """
    Given a testMethod, returns the original method import path.

    This is necessary because for every test method in a test suite, the unittest's TestLoader
    returns a patched class instead of the method itself.

    :param testMethod: a testMethod
    :return path: the original test method's import path.
    """
    return '{}.{}.{}'.format(
        testMethod.__class__.__module__, testMethod.__class__.__name__, testMethod._testMethodName,
    )


def task_method(task):
    return getattr(task, task._testMethodName)


def pull_tasks(suite, memo=None):
    """
    Given a Task suite, recursively returns all the test methods in it.

    :param suite: A test suite from `unittest.TestLoader.discover()`
    :return: a list of test methods
    """
    if memo is None:
        memo = []
    tasks = suite._tests
    for task in tasks:
        if hasattr(task, '_testMethodName'):
            memo.append((_testMethod_path(task), task))
        else:
            pull_tasks(task, memo)
    return memo


def discover_tasks(module='modelservice.profiles'):
    """
    Give a python module path, return the task suite contained in it.

    A task suite is like a test suite, but the testcase filenames must be
    ``profile*.py``, and the task method names must have the ``profile`` prefix.

    :param module: a dotted python module path
    :return: a task suite
    """
    loader = unittest.TestLoader()
    loader.testMethodPrefix = 'profile'
    return loader.discover(module, pattern="profile*.py")
