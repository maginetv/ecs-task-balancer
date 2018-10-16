#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='ecs_taskbalancer',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'boto3'
    ],
    zip_safe=False,
)
