from pathlib import Path
from typing import List

from setuptools import setup


def get_version(file_path: str, member: str) -> str:
    """Return the version string found in `path` as `member`."""
    path = Path(__file__).parent.joinpath(file_path).absolute()
    with open(path, 'r') as fp:
        for line in fp:
            if line.startswith(member):
                return line.split('=')[1].strip(' \'\t\n"')
    return ''


def get_requirements(file_path: str) -> List[str]:
    """Return the list of requirements found in `path`."""
    path = Path(__file__).parent.joinpath(file_path).absolute()
    requirements = []
    with open(path, 'r') as fp:
        for line in fp:
            line = line.strip(' \t\n')
            if not line.startswith('#'):
                requirements.append(line)
    return requirements


setup(
    name="link-sync",
    version=get_version('link_sync/__main__.py', '__VERSION__'),
    description="Synchronize GCode files across your printer farm.",
    author="Martin Koistinen",
    author_email="mkoistinen@gmail.com",
    url="https://github.com/mkoistinen/link-sync",
    readme="README.md",
    python_requires=">=3.10",
    keywords=["prusalink", "prusa-link"],
    license='Apache-2.0',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Environment :: Console',
    ],
    packages=['link_sync'],
    install_requires=get_requirements('requirements.in'),
    entry_points={
        'console_scripts': [
            'link-sync=link_sync.__main__:main',
        ]
    }
)
