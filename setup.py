import os
from setuptools import setup, find_packages

VERSION = '0.0.2'

f = open(os.path.join(os.path.dirname(__file__), 'README.md'))
readme = f.read()
f.close()

setup(
    name='modelservice',
    version=VERSION,
    description='',
    long_description=readme,
    author='',
    author_email='',
    url='',
    include_package_data=True,
    packages=find_packages(exclude=['tests']),
    scripts=[
        'bin/aws_profile.sh',
        'bin/profile.sh'
    ],
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Framework :: Django',
    ],
    install_requires=[
        "simpl-authenticator==0.0.7",
        "simpl_client==0.2.2",
        "genericclient-base==1.0.0",
        "Django==1.11.11",
        "djangorestframework==3.6.4",
        "aiorwlock",
        "aiojobs==0.0.3",
        "attrs>=17.4.0",
        "autobahn==17.10.1",
        "click==6.7",
        "crossbar==17.10.1",
        "django-markup==1.2",
        "django-click==2.0.0",
        "docutils==0.12",
        "thorn==1.2.0",
        "boto3==1.5.28",
        "botocore==1.8.42",
    ],
    dependency_links=[
        'https://7e1b08465a2c5d2ba410cad5559f02751278ba79@github.com/simplworld/simpl-authenticator/archive/v0.0.7.zip',
        'https://7e1b08465a2c5d2ba410cad5559f02751278ba79@github.com/simplworld/simpl-client/archive/v0.2.2.zip',
    ],
    test_suite='runtests',
    tests_require=[
        "asynctest>=0.12",
    ]
)
