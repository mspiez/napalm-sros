### get_facts()

Output from SROS for get_facts():

```
>>> import json
>>> import re
>>> 
>>> from SROSDriver import SROSDriver
>>> 
>>> 
>>> device = SROSDriver('192.168.1.15', 'admin', 'admin')
>>> device.open()
>>> get_facts= device.get_facts()
>>> print json.dumps(get_facts, indent=4)
{
    "os_version": "B-14.0.R4", 
    "uptime": "13 days, 00:08:16.79", 
    "vendor": "Nokia", 
    "interface": [
        "Itf_To_vsr_tst_18", 
        "Itf_To_vsr_tst_19", 
        "toSR-G", 
        "toSR-E", 
        "toSR-D", 
        "Itf_To_cpaa_tst_1", 
        "Itf_To_vsr_tst_16", 
        "system", 
        "toSR-B"
    ], 
    "serial_number": "vRR", 
    "model": "7750 SR-12", 
    "hostname": "SR-A", 
    "fqdn": "SR-A"
}
>>> 
```
