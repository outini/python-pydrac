[![PythonSupport][1]][1l][![License][2]][2l]

python-pydrac - Dell iDRAC python interface

**Contact:** Denis 'jawa' Pompilio <denis.pompilio@gmail.com>

**Sources:** https://github.com/outini/python-pydrac

## About

This package provides intuitive and easy to use python interface to control
Dell iDRAC.

## Installation

```bash
python setup.py install
```

## Helpers

To be documented

## Exemples

Basic initialization:
```python
import pydrac

IDRAC_USER = "root"
IDRAC_PASSWORD = "calvin"


idrac = {
    'endpoint': "idrac-x0x0x0x0.oob.corp.net",
    'user': IDRAC_USER,
    'password': IDRAC_PASSWORD
}
radm = pydrac.RacAdm(idrac)

# Show hardware inventory of the server
radm.inventory.show()

# Reset the server
radm.serveraction("reset")
```

## License

MIT LICENSE *(see LICENSE file)*

## Miscellaneous

```
    ╚⊙ ⊙╝
  ╚═(███)═╝
 ╚═(███)═╝
╚═(███)═╝
 ╚═(███)═╝
  ╚═(███)═╝
   ╚═(███)═╝
```

[1]: https://img.shields.io/badge/python-3-blue.svg
[1l]: https://github.com/outini/python-pydrac
[2]: https://img.shields.io/badge/license-MIT-blue.svg
[2l]: https://github.com/outini/python-pydrac
