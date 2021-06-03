import os
from setuptools import setup, find_packages

VERSION = '0.10.1'

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as f:
    readme = f.read()

setup(
    name='simpl-modelservice',
    version=VERSION,
    description='Python Library to implement Simulations, built on Crossbar.io and Django.',
    long_description=readme,
    long_description_content_type="text/markdown",
    author='',
    author_email='',
    url='https://github.com/simplworld/simpl-modelservice',
    include_package_data=True,
    packages=find_packages(exclude=['tests']),
    scripts=['bin/aws_profile.sh', 'bin/profile.sh'],
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Framework :: Django',
    ],
    install_requires=[
        "simpl-authenticator==0.7.3",
        "simpl_client~=0.8.0",
        "django~=2.2.0",
        "djangorestframework~=3.9.0",
        "aiorwlock",
        "aiojobs==0.2.1",
        "attrs>=17.4.0",
        "autobahn==17.10.1",
        "click==6.7",
        "crossbar==17.10.1",
        "django-markup==1.2",
        "django-click==2.1.0",
        "thorn",
        "twisted==20.3.0"
    ],
    dependency_links=[
        "thorn==https://github.com/robinhood/thorn.git@486a53e",  # compatible with Django 2
    ],
    test_suite='runtests',
    tests_require=["asynctest>=0.12"],
)
