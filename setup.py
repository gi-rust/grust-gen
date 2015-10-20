from setuptools import setup

setup(
    name='grust-gen',
    setup_requires=['setuptools_scm'],
    use_scm_version={
        'write_to': 'lib/grust/version.py'
    },
    packages=['grust'],
    package_dir={
        'grust': 'lib/grust'
    },
    package_data={
        'grust': ['templates']
    },
    entry_points={
        'console_scripts': [
            'grust-gen = grust.genmain:generator_main'
        ],
    },
    install_requires = ['Mako >= 1.0']
)
