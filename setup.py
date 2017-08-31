#!/usr/bin/env python

from setuptools import setup

setup(
    name='tap-exacttarget',
    version='0.0.1',
    description='Singer.io tap for extracting data from the ExactTarget API',
    author='Fishtown Analytics',
    url='http://fishtownanalytics.com',
    classifiers=['Programming Language :: Python :: 3 :: Only'],
    py_modules=['tap_exacttarget'],
    install_requires=[
        'singer-python==1.8.1',
        'python-dateutil==2.6.0',
        'FuelSDK==0.9.4'
    ],
    dependency_links=[
        'git+https://github.com/cmcarthur/FuelSDK-Python.git#egg=FuelSDK-0.9.4'
    ],
    entry_points='''
    [console_scripts]
    tap-exacttarget=tap_exacttarget:main
    ''',
    packages=['tap_exacttarget']
)