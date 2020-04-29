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

## Examples

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

More complete report:
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

try:
    print("--- Inventory ----------------------")
    radm.inventory.show()

    print("--- iDRAC Configuration ---------")
    print("Network configuration:")
    print("    DHCPEnable: %s" % (radm.bios.idrac_ipv4['DHCPEnable']))
    print("    Address: %s" % (radm.bios.idrac_ipv4['Address']))
    print("    Netmask: %s" % (radm.bios.idrac_ipv4['Netmask']))
    print("    Gateway: %s" % (radm.bios.idrac_ipv4['Gateway']))
    print("    DNS1: %s" % (radm.bios.idrac_ipv4['DNS1']))
    print("    DNS2: %s" % (radm.bios.idrac_ipv4['DNS2']))

    print("\n--- BIOS Settings ------------------")
    print("Boot settings:")
    print("    BootMode: %s" % (radm.bios.bios_boot_settings['BootMode']))
    print("    BootSeq: %s" % (radm.bios.bios_boot_settings['BootSeq']))
    print("    UefiBootSeq: %s" % (
        radm.bios.bios_boot_settings['UefiBootSeq']))
    print("System profile settings:")
    print("    SysProfile: %s" % (
        radm.bios.sys_profile_settings['SysProfile']))

    print("\n--- Updates ------------------------")
    radm.updates.repo_type = "HTTPS"
    radm.updates.refresh_updates_list('downloads.dell.com')
    radm.updates.show(['Firmware', 'BIOS'])

    print("\n--- Events -------------------------")
    for event in radm.get_sel(severity=["Critical", "Non-Critical"]):
        print(event)

finally:
    radm.logout()
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
