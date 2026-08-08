from setuptools import setup

setup(
    name="simple-python-ide",
    version="1.0.0",
    description="A full-featured Python IDE with AI assistance",
    py_modules=["app", "launch"],
    install_requires=["PySide6>=6.6.0"],
    extras_require={"ai": ["gpt4all>=2.0.0"]},
)
