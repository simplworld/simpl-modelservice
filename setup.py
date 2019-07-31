import os
from setuptools import setup, find_packages

VERSION = '0.7.15'

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
        "simpl_client==0.7.5",
        "django>=1.11.15,<2.0",
        "djangorestframework==3.6.4",
        "aiorwlock",
        "aiojobs==0.2.1",
        "attrs>=17.4.0",
        "autobahn==17.10.1",
        "click==6.7",
        "crossbar==17.10.1",
        "django-markup==1.2",
        "django-click==2.0.0",
        "thorn==1.5.0",
        "boto3==1.5.28",
        "botocore==1.8.42",
    ],
    test_suite='runtests',
    tests_require=["asynctest>=0.12"],
)
