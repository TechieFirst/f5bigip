import os
import f5_bigip

from setuptools import setup, find_packages


if 'rpm' not in os.getcwd():
    with open('requirements.txt') as fh:
        required = [x for x in fh.read().splitlines() if not x.startswith('#')]
else:
    required = []

setup(
    name="f5_bigip",
    version=f5_bigip.__version__,
    author="Techie First",
    author_email="techie.first87@gmail.com",
    description="This Package contains F5 basic modules which can be used in VIP creation, VIP Validation, Pool Creation and Pool Modifications",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/TechieFirst/f5bigip",
    packages=find_packages(),
    install_requires=required,

    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)