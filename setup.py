"""
avira.deployplugin.cloudstack
=============================

THe cloudstack provider for the avira.deploy tool.
"""

from setuptools import setup
from setuptools import find_packages

version = '1.1.4'

setup(
    name='avira.deployplugin.cloudstack',
    version=version,
    description="Avira Deployment Tool Cloudstack provider",
    long_description=__doc__,
    classifiers=[],
    # Get strings from
    #http://pypi.python.org/pypi?%3Aaction=list_classifiers
    keywords='',
    author='Lars van de Kerkhof',
    author_email='lars@permanentmarkers.nl',
    url='https://github.dtc.avira.com/VDT/avira.deployplugin.cloudstack',
    license='Avira VDT 2012',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    namespace_packages=['avira', 'avira.deployplugin'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'distribute',
        'cloudstack',
        'straight.plugin',
        'avira.deploy',
        # -*- Extra requirements: -*-
    ],
    entry_points={},
)
