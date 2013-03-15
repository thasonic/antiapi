from setuptools import setup, find_packages

setup(
    name='antiapi',
    version='0.1',
    description='A simple tools for creating API on Django and Werkzeug',
    long_description='',
    author='Alexander Pokatilov',
    author_email='thasonic@gmail.com',
    package_dir = {'': 'src'},
    packages = find_packages('src'),
)
