### get_bgp_neighbors()

Output from SROS for get_bgp_neighbors():

```
>>> import json
>>> import re
>>> 
>>> from SROSDriver import SROSDriver
>>> 
>>> 
>>> device = SROSDriver('192.168.1.17', 'admin', 'admin')
>>> device.open()
>>> neighbors = device.get_bgp_neighbors()
>>> neighbors.keys()
['global']
>>> neighbors['global'].keys()
['1.1.1.16', '1.1.1.15', '1.1.1.20', '1.1.1.18', '1.1.1.19']
>>> print json.dumps(neighbors['global']['1.1.1.16'], indent=4)
{
    "router_id": "1.1.1.17", 
    "is_enabled": true, 
    "uptime": "12d13h07m", 
    "remote_as": "100", 
    "is_up": true, 
    "bgp_state": "Established", 
    "remote_id": "1.1.1.16", 
    "local_as": "719", 
    "address_family": {
        "VpnIPv4": {
            "sent_prefixes": "59", 
            "accepted_prefixes": "0", 
            "received_prefixes": "0"
        }
    }
}
>>>
```
