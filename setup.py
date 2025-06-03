rom setuptools import setup, find_packages

setup(
    name="f5_bigip",
    version="0.1.0",
    author="Techie First",
    author_email="techie.first87@gmail.com",
    description="This Package contains F5 basic modules which can be used in VIP creation, VIP Validation, Pool Creation and Pool Modifications",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/TechieFirst/f5bigip",
    packages=find_packages(),
    install_requires=[
        "requests>=2.0",
        "f5-sdk==3.0.21",
        "pyYaml",
        "setuptools"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)