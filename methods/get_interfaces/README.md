### get_interfaces()

Output from SROS for get_interfaces():

```
>>> import json
>>> import re
>>> 
>>> from SROSDriver import SROSDriver
>>> 
>>> 
>>> device = SROSDriver('192.168.1.15', 'admin', 'admin')
>>> device.open()
>>> ifaces = device.get_interfaces()
>>> ifaces.keys()
['Itf_To_vsr_tst_18', 'Itf_To_vsr_tst_19', 'toSR-G', 'toSR-E', 'toSR-D', 'Itf_To_cpaa_tst_1', 'Itf_To_vsr_tst_16', 'system', 'toSR-B']
>>> print json.dumps(ifaces['toSR-B'], indent=4)
{
    "ipv4_status": "Up", 
    "link_to": "1/1/1", 
    "ip": "10.0.0.1/30", 
    "ipv6_status": "Down", 
    "admin_status": "Up", 
    "mode": "Network"
}
>>>
```
