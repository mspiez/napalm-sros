### get_arp_table()

Output from SROS for get_arp_table()

```
>>> import json
>>> import re
>>> 
>>> from SROSDriver import SROSDriver
>>> 
>>> 
>>> device = SROSDriver('192.168.1.15', 'admin', 'admin')
>>> device.open()
>>> arp_table = device.get_arp_table()
>>> print json.dumps(arp_table[:3], indent=4)
[
    {
        "interface": "system", 
        "ip": "1.1.1.15", 
        "mac": "02:0f:ff:00:00:00", 
        "age": 0
    }, 
    {
        "interface": "Itf_To_vsr_tst_16", 
        "ip": "10.1.1.0", 
        "mac": "02:0f:ff:00:01:41", 
        "age": 0
    }, 
    {
        "interface": "Itf_To_vsr_tst_18", 
        "ip": "10.1.1.2", 
        "mac": "02:0f:ff:00:01:42", 
        "age": 0
    }
]
>>> 
```
