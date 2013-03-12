"""
vdt.deployplugin.cloudstack
=============================

THe cloudstack provider for the vdt.deploy tool.
"""

from setuptools import setup
from setuptools import find_packages

version = '1.1.9'

setup(
    name='vdt.deployplugin.cloudstack',
    version=version,
    description="vdt Deployment Tool Cloudstack provider",
    long_description=__doc__,
    classifiers=[],
    # Get strings from
    #http://pypi.python.org/pypi?%3Aaction=list_classifiers
    keywords='',
    author='Lars van de Kerkhof',
    author_email='lars@permanentmarkers.nl',
    url='https://github.com/devopsconsulting/vdt.deployplugin.cloudstack',
    license='BSD',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    namespace_packages=['vdt', 'vdt.deployplugin'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'distribute',
        'cloudstack',
        'straight.plugin',
        'vdt.deploy',
        # -*- Extra requirements: -*-
    ],
    entry_points={},
)
