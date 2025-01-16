from setuptools import setup, find_packages

setup(
    name='nputop',
    version='0.0.1',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'nputop = nputop.main:main',
        ],
    },
    install_requires=[
        'textual',
        'psutil',
        'rich'
    ],
    description='NPU monitoring tool with TUI interface',
    author='Rvelamen',
    author_email='your.email@example.com',
    url='https://github.com/Rvelamen/nputop',
)