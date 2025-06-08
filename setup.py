from setuptools import setup, find_packages
import os

# Read the README file if it exists
def read_readme():
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "A secure, portable MCP server for generating professional slide decks via chat"

setup(
    name="slide-architect-pro",
    version="3.2.4",
    packages=find_packages(),
    install_requires=[
        "python-pptx==0.6.23",
        "pydantic==2.9.2",
        "aiohttp==3.10.5",
        "mistune==3.0.2",
        "altair==5.2.0",
        "cairosvg==2.7.1",
        "bleach==6.1.0",
        "fastapi==0.115.0",
        "uvicorn==0.30.6",
        "requests==2.31.0",
        "Pillow==10.1.0",
        "vl-convert-python>=1.1.0",
        "websockets>=11.0.0"
    ],
    scripts=["run_server.py"],
    author="Your Name",
    author_email="your.email@example.com",
    description="A secure, portable MCP server for generating professional slide decks via chat",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/slide-architect-pro",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ],
    python_requires=">=3.9"
)