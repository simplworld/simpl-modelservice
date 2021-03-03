import os
from setuptools import setup, find_packages

VERSION = "1.0.0rc1"

with open(os.path.join(os.path.dirname(__file__), "README.md")) as f:
    readme = f.read()

setup(
    name="simpl-modelservice",
    version=VERSION,
    description="Python Library to implement Simulations, built on Crossbar.io and Django.",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="",
    author_email="",
    url="https://github.com/simplworld/simpl-modelservice",
    include_package_data=True,
    packages=find_packages(exclude=["tests"]),
    scripts=["bin/aws_profile.sh", "bin/profile.sh"],
    zip_safe=False,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Framework :: Django",
    ],
    install_requires=[
        "simpl_client~=0.8.0",
        "django~=2.2.16",
        "aiorwlock",
        "aiojobs==0.2.2",
        "attrs>=17.4.0",
        "autobahn==20.7.1",
        "crossbar==20.7.1",
        "django-markup==1.5",
        "boto3==1.5.28",
        "botocore==1.8.42",
        "click==7.1.2",
        "django-click==2.2.0",
    ],
    test_suite="runtests",
    tests_require=["asynctest>=0.12"],
)
