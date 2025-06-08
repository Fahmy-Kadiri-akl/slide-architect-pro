from setuptools import setup, find_packages

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
        "vl-convert-python>=1.1.0"  # Required for Altair SVG export
    ],
    scripts=["run_server.py"],
    author="Your Name",
    author_email="your.email@example.com",
    description="A secure, portable MCP server for generating professional slide decks via chat",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/slide-architect-pro",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ],
    python_requires=">=3.9"  # Fixed to match actual compatibility
)