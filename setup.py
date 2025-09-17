#!/usr/bin/env python3
"""
Setup script for Algo Speaker Home Assistant Integration
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="algo-speaker-ha-integration",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Home Assistant integration for Algo IP speakers",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/algo-speaker-ha-integration",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Home Automation",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "flake8>=6.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "algo-hmac=python_scripts.algo_hmac_generator:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)

