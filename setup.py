from setuptools import setup

setup(
    name='grust-gen',
    setup_requires=['setuptools_scm'],
    use_scm_version={
        'write_to': 'grust/version.py'
    },
    packages=['grust'],
    package_data={
        'grust': ['*.tmpl']
    },
    entry_points={
        'console_scripts': [
            'grust-gen = grust.genmain:generator_main'
        ],
    },
    install_requires = ['Mako >= 1.0']
)
