from setuptools import find_packages, setup

with open("requirements.txt") as f:
    requirements = [l for l in f.read().splitlines() if l]
with open("requirements.dev.txt") as f:
    dev_requirements = [l for l in f.read().splitlines() if l]

setup(
    name='wechat-django',
    version='0.1.0.0',
    author='Xavier-Lam',
    author_email='Lam.Xavier@hotmail.com',
    url='https://github.com/Xavier-Lam/django-wechat',
    packages=find_packages(),
    keywords='wechat, weixin, wx, micromessenger',
    description='WeChat Django Extension',
    install_requires=requirements,
    include_package_data=True,
    # tests_require=dev_requirements,
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Web Environment",
        "Framework :: Django :: 1.11",
        "Framework :: Django :: 2.0",
        "Framework :: Django :: 2.1",
        "Framework :: Django :: 2.2",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: Chinese (Simplified)",
        "Natural Language :: Chinese (Traditional)",
        "Natural Language :: English",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Internet :: WWW/HTTP :: Site Management",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities"
    ],
    extras_require={
        'cryptography': ["cryptography"],
        'pycrypto': ["pycryptodome"],
    }
)