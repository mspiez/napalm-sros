### get_bgp_config()

Output from SROS for get_bgp_config():

```
>>> import json
>>> import re
>>> 
>>> from SROSDriver import SROSDriver
>>> 
>>> 
>>> device = SROSDriver('192.168.1.17', 'admin', 'admin')
>>> device.open()
>>> bgp_config = device.get_bgp_config()
>>> bgp_config.keys()
['RR_vpn_ipv4', 'test']
>>> bgp_config['RR_vpn_ipv4']['neighbors'].keys()
['1.1.1.16', '1.1.1.15', '1.1.1.20', '1.1.1.18', '1.1.1.19']
>>> print json.dumps(bgp_config['RR_vpn_ipv4']['neighbors']['1.1.1.16'], indent=4)
{
    "export_policy": "None Specified / Inherited", 
    "description": "(Not Specified)", 
    "local_as": "100", 
    "route_reflector_client": true, 
    "nhs": false, 
    "prefix_limit": false, 
    "bgp_group": "RR_vpn_ipv4", 
    "remote_as": "100", 
    "import_policy": "None Specified / Inherited", 
    "local_address": "1.1.1.17", 
    "authentication_key": "n/a"
}
>>> 
>>> 
>>> 
>>> 
>>> 
>>> bgp_gr_config = device.get_bgp_config(group='RR_vpn_ipv4')
>>> bgp_gr_config.keys()
['neighbors', 'export_policy', 'description', 'local_as', 'multihop_ttl', 'remote_as', 'remove_private_as', 'multipath', 'prefix_limit', 'import_policy', 'local_address', 'type']
>>> 
>>> 
>>> 
>>> 
>>> 
>>> bgp_neighbor_config = device.get_bgp_config(neighbor='1.1.1.16')
>>> print json.dumps(bgp_neighbor_config, indent=4)
{
    "export_policy": "None Specified / Inherited", 
    "description": "(Not Specified)", 
    "local_as": "719", 
    "route_reflector_client": true, 
    "nhs": false, 
    "prefix_limit": false, 
    "bgp_group": "RR_vpn_ipv4", 
    "remote_as": "719", 
    "import_policy": "None Specified / Inherited", 
    "local_address": "1.1.1.17", 
    "authentication_key": "n/a"
}
>>> 
```
