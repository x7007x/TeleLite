from setuptools import setup, find_packages

setup(
    name='telelite',
    version='0.1.2',
    description='Lightweight Telegram Bot Library',
    author='YourName',
    packages=find_packages(),
    install_requires=[
        'Flask>=2.2.5',
        'aiohttp>=3.8.4',
        'requests>=2.31.0',
        "quart"
    ],
    python_requires='>=3.7',
)
