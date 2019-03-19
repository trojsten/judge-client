import setuptools

setuptools.setup(
    name="trojsten_judge_client",
    version="1.0.1",
    url="https://github.com/trojsten/judge-client",

    author="Michal Hozza",
    author_email="mhozza@gmail.com",

    description="Client for Trojsten Judge System.",
    long_description=open('README.rst').read(),

    packages=setuptools.find_packages(),
    test_suite='tests',
    install_requires=['six'],

    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)
