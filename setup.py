#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Lightweight and easy configurable server backup utility.
"""
import sys
from setuptools import setup

# NOTE: Steps for publishing
# - pip install twine wheel
# - python setup.py sdist bdist_wheel
# - twine check dist/*
# - twine upload dist/*

PY2 = sys.version_info[0] == 2

__version__ = ''

long_description = """
coverme
=======

Lightweight and easy configurable server backup utility.

Install::

    pip install coverme

Command line help::

    coverme --help

More details available at:
https://github.com/05bit/coverme
"""

with open('coverme.py') as file:
    for line in file:
        if line.startswith('__version__'):
            __version__ = line.split('=')[1].strip().strip("'").strip('"')
            break

install_requires = [
    'click',
    'pyyaml',
    'boto3',
]

if PY2:
    install_requires += [
        'future'
    ]

setup(
    name="coverme",
    version=__version__,
    author="Alexey Kinëv",
    author_email='rudy@05bit.com',
    url='https://github.com/05bit/coverme',
    description=__doc__.strip(),
    long_description=long_description,
    long_description_content_type='text/x-rst',
    license='Apache-2.0',
    zip_safe=False,
    install_requires=install_requires,
    py_modules=[
        'coverme',
    ],
    entry_points={
        'console_scripts': [
            'coverme = coverme:main',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
    ],
    # test_suite='tests',
    # test_loader='unittest:TestLoader',
)
