from setuptools import setup, find_packages

with open('README.rst') as readme:
    long_description = readme.read()

setup(
    name='grust-gen',
    url='https://github.com/gi-rust/grust-gen',
    author='Mikhail Zabaluev',
    author_email='mikhail.zabaluev@gmail.com',
    description='Rust binding generator for GObject introspection',
    long_description=long_description,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)',
        'Programming Language :: Python :: 2',
        'Programming Language :: Rust',
        'Topic :: Software Development :: Code Generators',
    ],
    setup_requires=['setuptools_scm'],
    use_scm_version={
        'write_to': 'grust/version.py'
    },
    packages=find_packages(),
    package_data={
        'grust': ['templates/*/*.tmpl']
    },
    entry_points={
        'console_scripts': [
            'grust-gen = grust.genmain:generator_main'
        ],
    },
    install_requires = ['Mako >= 1.0']
)
