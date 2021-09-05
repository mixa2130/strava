"""I'm so sorry for the pre-release bug"""
import os
from setuptools import setup

version = '0.2.1'


def parse_requirements(filename):
    """ load requirements from a pip requirements file """
    lineiter = (line.strip() for line in open(filename))
    return [line for line in lineiter if line and not line.startswith("#")]


reqs = parse_requirements(os.path.join(os.path.dirname(__file__), 'requirements.txt'))

setup(
    name="strava",
    version=version,
    author='Michael S2pac',
    author_email='mixa21.11@mail.ru',
    description="Parse https://www.strava.com website using asyncio",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    license="MIT",
    packages=["async_strava"],
    install_requires=reqs,
    include_package_data=True,
    project_urls={"Source": "https://github.com/mixa2130/strava"},
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Internet",
        "Topic :: Software Development",
        "Topic :: Software Development :: Libraries",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Operating System :: MacOS",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
    zip_safe=True
)
