import pathlib

from setuptools import setup, find_packages

from exegol import __version__

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / 'README.md').read_text(encoding='utf-8')

# Additional non-code data used by Exegol to build local docker image from source
data_files_dict = {}
data_files = []
for path in pathlib.Path('exegolbuild').rglob('*'):
    key = str(path.parent)
    if data_files_dict.get(key) is None:
        data_files_dict[key] = []
    if path.is_dir():
        continue
    data_files_dict[key].append(str(path))
for k, v in data_files_dict.items():
    data_files.append((k, v))

setup(
    name='Exegol',
    version=__version__,
    license='GNU (GPLv3)',
    author="Shutdown & Dramelac",
    author_email='nwodtuhs@pm.me',
    description='Python wrapper to use Exegol, a container based fully featured and community-driven hacking environment.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    python_requires='>=3.7, <4',
    url='https://github.com/ShutdownRepo/Exegol',
    keywords='pentest redteam ctf exegol',
    classifiers=[
        'Development Status :: 3 - Alpha',  # TODO change status
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'docker~=5.0.3',
        'requests',
        'rich~=11.2.0',
        'PyYAML'
    ],
    packages=find_packages(exclude=["assets"]),
    include_package_data=True,
    data_files=data_files,

    entry_points={
        'console_scripts': [
            'exegol = exegol.manager.ExegolController:main',
        ],
    },

    project_urls={
        'Bug Reports': 'https://github.com/ShutdownRepo/Exegol/issues',
        'Source': 'https://github.com/ShutdownRepo/Exegol',
        'Documentation': 'https://github.com/ShutdownRepo/Exegol/wiki',  # TODO add doc url
        'Funding': 'https://patreon.com/nwodtuhs',
    },
    test_suite='tests'  # TODO check tests
)