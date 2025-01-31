from pathlib import Path

from setuptools import find_packages, setup

readme_file = Path(__file__).parent / "README.md"
with readme_file.open() as f:
    long_description = f.read()

setup(
    name="girder-cli-oauth-client",
    description="A Python library for performing OAuth login to a Girder 4 (Django) server.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="Apache 2.0",
    url="https://github.com/girder/girder-cli-oauth-client",
    project_urls={
        "Bug Reports": "https://github.com/girder/girder-cli-oauth-client/issues",
        "Source": "https://github.com/girder/girder-cli-oauth-client",
    },
    author="Kitware, Inc.",
    author_email="kitware@kitware.com",
    keywords="",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python",
    ],
    python_requires=">=3.8",
    install_requires=[
        "authlib",
        "dataclasses-json",
        "pyxdg",
    ],
    extras_require={
        "dev": ["ipython", "tox"],
        "example": [
            "click",
            "requests",
            "django",
            "django-oauth-toolkit @ git+https://github.com/duzumaki/django-oauth-toolkit@add-device-flow",
        ],
    },
    packages=find_packages(),
)
