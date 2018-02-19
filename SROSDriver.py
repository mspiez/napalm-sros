#!/usr/bin/env python

import os
import re
import paramiko
import time

from scp import SCPClient

class SROSDriver(object):
    def __init__(self, hostname, username, password, timeout=60, optional_args=None):
        if optional_args is None:
            optional_args = {}
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout
        self.port = optional_args.get('port', 22)
        self.ssh = paramiko.SSHClient()
        self.device = None

    def open(self):
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(
                            hostname=self.hostname,
                            port=self.port,
                            username=self.username,
                            password=self.password
                            )
        self.device = self.ssh.invoke_shell()

    def close(self):
        self.ssh.close()

    def command(self, cmd):
        self.device.send(cmd)
        time.sleep(1)
        return self.device.recv(65535)

    def scp_file_put(self, source_file, dest_file):
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(
                            hostname=self.hostname,
                            port=self.port,
                            username=self.username,
                            password=self.password
                            )
        scp = SCPClient(self.ssh.get_transport())
        scp.put(source_file, dest_file)

    def scp_file_get(self, dest_file):
        scp = SCPClient(self.ssh.get_transport())
        scp.get(dest_file)

    def get_interfaces(self):
        self.device.send('\n/environment no more\n')
        time.sleep(1)
        self.device.send('/show router interface exclude-services\n')
        time.sleep(1)
        output = self.device.recv(65535)
        ifaces_split = re.split('----+', output)
        all_ifaces = re.findall(r'^(\w.*[\r|\n]+.*)', ifaces_split[1], re.MULTILINE)
        interface_facts = {}
        for iface in all_ifaces:
            iface_name = re.search(r'^(.{1,32})', iface).group(1)
            admin_status = re.search(r'.{33}(\w+)', iface).group(1)
            ipv4_status = re.search(r'.{33}(\w+)', iface).group(1)
            ipv6_status = re.search(r'.{43}\w+/(\w+)', iface).group(1)
            mode = re.search(r'.{55}(\w+)', iface).group(1)
            link_to = re.search(r'.{63}(\.+)', iface).group(1)
            try:
                ip = re.search(r'\s+(\d+.\d+.\d+.\d+/\d+)', iface, re.MULTILINE).group(1)
            except AttributeError:
                ip = False
            interface_facts.update({iface_name: {
                                'admin_status': admin_status,
                                'ipv4_status': ipv4_status,
                                'ipv6_status': ipv6_status,
                                'mode': mode,
                                'ip': ip,
                                'link_to': link_to
                                }
                            })
        return interface_facts

    def get_facts(self):
        sys_info = '/show system information'
        sys_name = '{} | match "System Name"\n'.format(sys_info)
        sys_type = '{} | match "System Type"\n'.format(sys_info)
        serial = '/show chassis\n/show chassis detail\n'
        sys_version = '{} | match "System Version"\n'.format(sys_info)
        sys_uptime = '{} | match "System Up Time"\n'.format(sys_info)
        self.device.send('\n/environment no more\n')
        time.sleep(1)
        self.device.send(sys_name + sys_type + serial + sys_version + sys_uptime)
        time.sleep(1)
        output = self.device.recv(65535)
        hostname = re.search(r'System Name +: (.*)[\r|\n]+', output).group(1)
        try:
            model = re.search(r'System Type +: (.*)[\r|\n]+', output).group(1)
        except AttributeError:
            model = False
        try:
            serial_number = re.search(r'Serial number +: (.*)[\r|\n]+', output).group(1)
        except AttributeError:
            serial_number = False
        os_version = re.search(r'System Version +: (.*)[\r|\n]+', output).group(1)
        try:
            uptime = re.search(r'System Up Time +: (.*) \(', output).group(1)
        except AttributeError:
            uptime = False
        return {
            'vendor': 'Nokia',
            'model': model,
            'serial_number': serial_number,
            'os_version': os_version,
            'hostname': hostname,
            'fqdn': hostname,
            'uptime': uptime,
            'interface': self.get_interfaces().keys()
            }

    def get_arp_table(self):
        self.device.send("/environment no more\n")
        self.device.send("/show router arp\n")
        output = self.device.recv(65535)
        arp_output = output.splitlines()
        arp_table = []
        for arp_entry in arp_output:
            arp_search = re.search('^(\d+.\d+.\d+.\d+)\s+(\S+)\s+(\S+)' \
                            '\s+(\S+)\s+(.*)', arp_entry)
            try:
                ip = arp_search.group(1)
                mac = arp_search.group(2)
                age = float(arp_search.group(3))
                iface = arp_search.group(5)
            except Exception as f:
                pass
            else:
                arp_table.append({'mac': mac,
                                  'ip': ip,
                                  'interface': iface,
                                  'age': age})
        return arp_table

    # def get_bgp_config(self, group='', neighbor=''):
    #     self.device.send("/environment no more\n")
    #     self.device.send("/show router bgp group\n")
    #     output = self.device.recv(65535)
    #     bgp_peers_parms = _get_single_bgp_neighbor(output)
    #     for bgp_peer in bgp_peers_parms:


    def _bgp_neighgbors_parms(self, neighbors_list):
        bgp_neighbors_parms = {}
        for neighgbor in neighbors_list:
            r_neighbor = self._search_func('Peer\s+:\s(\d+.\d+.\d+.\d+)',
                                                neighgbor, '')
            desc = self._search_func('Description\s+:\s(.*)', neighgbor, '')
            im_pol = self._search_func('Import Policy\s+:\s(.*)', neighgbor, '')
            ex_pol = self._search_func('Export Policy\s+:\s(.*)', neighgbor, '')
            loc_add = self._search_func('Local Address\s+:\s(\d+.\d+.\d+.\d+)',
                                                neighgbor, '')
            loc_as = self._search_func('Local AS\s+:\s(\S+)', neighgbor, int)
            peer_as = self._search_func('Peer AS\s+:\s(\S+)', neighgbor, int)
            auth = self._search_func('Auth key chain\s+:\s(\S+)', neighgbor, '')
            prefix_l = self._search_func('Prefix Limit\s+:\s(\S+)', neighgbor, dict)
            rr_client = self._search_func('Cluster Id\s+:\s(\d+.\d+.\d+.\d+)',
                                                neighgbor, False)
            if rr_client:
                rr_client = True
            nhs = self._search_func('Next Hop Self\s+:\s(Enabled)', neighgbor, False)
            if nhs:
                nhs = True
            bgp_neighbors_parms[r_neighbor] = {
                'description': desc,
                'import_policy': im_pol,
                'export_policy': ex_pol,
                'local_address': loc_add,
                'local_as': loc_as,
                'remote_as': peer_as,
                'authentication_key': auth,
                'prefix_limit': prefix_l,
                'route_reflector_client': rr_client,
                'nhs': nhs}
        return bgp_neighbors_parms

    def _get_bgp_neighbors_section(self, bgp_response):
        neighbors = re.findall('^Peer\s+:\s(\d+.\d+.\d+.\d+)',
                               bgp_response, re.MULTILINE)
        neighbors_list_section = []
        neighbors_len = len(neighbors)
        for neighbor in neighbors:
            n_index = neighbors.index(neighbor)
            neighbor_start = bgp_response.index('Peer  : {}'.format(neighbor))
            section = bgp_response[neighbor_start:]
            if (n_index + 1) == neighbors_len:
                neighbor_sect = section
            else:
                neighbor_end = section.index('Peer  : ', 2)
                neighbor_sect = section[:neighbor_end]
            neighbors_list_section.append(neighbor_sect)
        return neighbors_list_section

    def _bgp_group_parms(self, bgp_groups_list):
        bgp_groups_parms = {}
        for bgp_group in bgp_groups_list:
            r_group = self._search_func('Group\s+:\s(.*)',
                                        bgp_group, '').rstrip()
            gr_type = self._search_func('Group Type\s+:\s(.*)',
                                        bgp_group, '')
            desc = self._search_func('Description\s+:\s(.*)', bgp_group, '')
            multihop = self._search_func('Multihop\s+:\s(\d+)', bgp_group, int)
            multipath = self._search_func('Multipath\s+:\s(\d+)', bgp_group, False)
            im_pol = self._search_func('Import Policy\s+:\s(.*)', bgp_group, '')
            ex_pol = self._search_func('Export Policy\s+:\s(.*)', bgp_group, '')
            loc_add = self._search_func('Local Address\s+:\s(\d+.\d+.\d+.\d+)',
                                        bgp_group, '')
            loc_as = self._search_func('Local AS\s+:\s(\S+)', bgp_group, int)
            peer_as = self._search_func('Peer AS\s+:\s(\S+)', bgp_group, int)
            remove_private_as = self._search_func('Remove Private\s+:\s(\S+)',
                                                  bgp_group, False)
            if remove_private_as:
                remove_private_as = True
            prefix_l = self._search_func('Prefix Limit\s+:\s(\S+)',
                                         bgp_group, dict)
            bgp_groups_parms[r_group] = {
                'description': desc,
                'type': gr_type,
                'multihop_ttl': multihop,
                'multipath': multipath,
                'import_policy': im_pol,
                'export_policy': ex_pol,
                'local_address': loc_add,
                'local_as': loc_as,
                'remote_as': peer_as,
                'remove_private_as': remove_private_as,
                'prefix_limit': prefix_l,
                }
        return bgp_groups_parms

    def _get_bgp_group_section(self, bgp_group_response):
        g_groups = re.findall('^Group\s+:\s(.*)',
                            bgp_group_response, re.MULTILINE)
        groups = [group.rstrip() for group in g_groups]
        group_list_section = []
        groups_len = len(groups)
        for group in groups:
            g_index = groups.index(group)
            g_search = re.search(r'(Group[ ]{{12}}: {})'.format(group),
                               bgp_group_response).group(1)
            group_start = bgp_group_response.index(g_search)
            section = bgp_group_response[group_start:]
            if (g_index + 1) == groups_len:
                group_sect = section
            else:
                group_end = section.index(': {}'.format(groups[g_index +1]))
                group_sect = section[:group_end]
            group_list_section.append(group_sect)
        return group_list_section

    def _search_func(self, search_for, search_in, option=None):
        try:
            ser_object = re.search('{}'.format(search_for), search_in).group(1)
        except Exception:
            if option:
                ser_object = option
            else:
                ser_object = False
        return ser_object

    def check_file_exists(self, dest_file):
        self.device.send("\n/environment no more\n")
        time.sleep(1)
        self.device.send('file dir {}\n'.format(dest_file))
        time.sleep(1)
        output = self.device.recv(65535)
        if 'CLI File Not Found' in output:
            return False
        else:
            return True

    def delete_file(self, dest_file):
        self.device.send("\n/environment no more\n")
        self.device.send('file delete {}\n'.format(dest_file))
        time.sleep(1)
        self.device.send('y')
        time.sleep(1)
        output = self.device.recv(65535)
        if 'OK' in output:
            return True
        else:
            return False

    def check_free_space(self, source_file):
        self.device.send("\n/environment no more\n")
        time.sleep(1)
        self.device.send('file dir\n')
        time.sleep(1)
        output = self.device.recv(65535)
        free_space = re.search('(\d+) bytes free', output)
        if free_space:
            free_space = free_space.group(1)
            file_size = os.stat(source_file).st_size
            if free_space > file_size:
                return True
            else:
                return False
        else:
            return False

    def rollback_save(self):
        self.device.send("\n/environment no more\n")
        time.sleep(1)
        self.device.send('admin rollback save\n')
        time.sleep(1)
        output = self.device.recv(65535)
        if 'OK' in output:
            return True
        else:
            return False

    def rollback_view(self):
        self.device.send("\n/environment no more\n")
        time.sleep(1)
        self.device.send('admin rollback view\n')
        time.sleep(1)
        output = self.device.recv(65535)
        return output

    def rollback_compare(self, rollback_id):
        self.device.send("\n/environment no more\n")
        time.sleep(1)
        self.device.send('admin rollback compare {} to active-cfg\n'.format(rollback_id))
        time.sleep(1)
        output = self.device.recv(65535)
        return output

    def exec_file(self, dest_file):
        self.device.send("exec {}\n".format(dest_file))
        output = ''
        endTime = datetime.datetime.now() + datetime.timedelta(seconds=60)
        while True:
            data = self.device.recv(2000)
            if datetime.datetime.now() >= endTime and output == '':
                break
            elif "failed" in data or 'Executed' in data:
                output += data
                break
            else:
                output += data
        return output

    
