"""
Env Setup
"""

import setuptools

# Read README for long description
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

# Read requirements.txt
with open('requirements.txt') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setuptools.setup(
    name='SyncMind',
    version="0.1.0",
    author='Xuehang Guo',
    author_email='xuehangguo@gmail.com',
    description='SyncMind: Measuring Agent Out-of-Sync Recovery in Collaborative Software Engineering\nSyncBench: An Evaluation Benchmark for Agent Out-of-Sync',
    keywords='nlp, llm, benchmark, software engineering',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/xhguo7/SyncMind',
    project_urls={
        'Repository': 'https://github.com/xhguo7/SyncMind',
        'Issues and PRs': 'https://github.com/xhguo7/SyncMind/issues',
        'SyncMind': 'https://github.com/xhguo7/SyncMind/syncmind',
        'SyncBench': 'https://github.com/xhguo7/SyncMind/syncbench',
        'SyncBench Dataset': 'huggingface'
    },
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
    ],
    python_requires='>=3.10',
    install_requires=requirements,
    extras_require={
        'inference': [
            'anthropic',
            'flash_attn',
            'jedi',
            'openai',
            'peft',
            'protobuf',
            'sentencepiece',
            'tiktoken',
            'torch',
            'transformers',
            'triton',
        ],
        'test': [
            'pytest',
            'pytest-cov',
            'pytest-mock',
        ]
    },
    include_package_data=True,
)
