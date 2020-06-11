# -*- coding: utf-8 -*-
#
#
#  Dell iDRAC python interface (python-pydrac)
#
#  Copyright (C) 2018 Denis Pompilio (jawa) <denis.pompilio@gmail.com>
#
#  This file is part of python-pydrac
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the MIT License.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  MIT License for more details.
#
#  You should have received a copy of the MIT License along with this
#  program; if not, see <https://opensource.org/licenses/MIT>.

import os
import setuptools


if __name__ == '__main__':
    readme_file = os.path.join(os.path.dirname(__file__), 'README.md')
    release = "0.2.1"
    setuptools.setup(
        name="python-pydrac",
        version=release,
        url="https://github.com/outini/python-pydrac",
        author="Denis Pompilio (jawa)",
        author_email="denis.pompilio@gmail.com",
        maintainer="Denis Pompilio (jawa)",
        maintainer_email="denis.pompilio@gmail.com",
        description="Dell iDRAC python interface",
        long_description=open(readme_file, encoding='utf-8').read(),
        long_description_content_type='text/markdown',
        license="MIT",
        platforms=['UNIX'],
        scripts=[],
        packages=['pydrac'],
        package_dir={'pydrac': 'pydrac'},
        data_files=[
            ('share/doc/python-pydrac', ['README.md', 'LICENSE', 'CHANGES']),
        ],
        keywords=['dell', 'idrac', 'automation'],
        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Operating System :: POSIX :: BSD',
            'Operating System :: POSIX :: Linux',
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 3',
            'Topic :: Utilities',
            ],
        requires=['pexpect'],
        install_requires=['pexpect']
    )
