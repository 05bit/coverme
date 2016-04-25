#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Asynchronous interface for peewee ORM powered by asyncio.
"""
import os
from setuptools import setup

__version__ = ''

with open('coverme.py') as file:
    for line in file:
        if line.startswith('__version__'):
            __version__ = line.split('=')[1].strip().strip("'").strip('"')
            break

setup(
    name="coverme",
    version=__version__,
    author="Alexey Kinëv",
    author_email='rudy@05bit.com',
    url='https://github.com/05bit/coverme',
    description=__doc__,
    # long_description=__doc__,
    license='Apache-2.0',
    zip_safe=False,
    install_requires=(
        'click',
        'pyyaml',
        'boto3',
    ),
    py_modules=[
        'coverme',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
    ],
    # test_suite='tests',
    # test_loader='unittest:TestLoader',
)
