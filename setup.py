from setuptools import setup, find_packages

setup(
    name='grust-gen',
    url='https://github.com/gi-rust/grust-gen',
    author='Mikhail Zabaluev',
    author_email='mikhail.zabaluev@gmail.com',
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
