#!/usr/bin/env python

import datetime
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
        self.device.send('/environment no more\n')
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
        all_ifaces = re.findall(r'^(\w.*[\r\n]+.*)', ifaces_split[1], re.MULTILINE)
        interface_facts = {}
        for iface in all_ifaces:
            iface_name = re.search(r'^(.{1,32})', iface).group(1)
            admin_status = re.search(r'.{33}(\w+)', iface).group(1)
            ipv4_status = re.search(r'.{43}(\w+)', iface).group(1)
            ipv6_status = re.search(r'.{43}\w+/(\w+)', iface).group(1)
            mode = re.search(r'.{55}(\w+)', iface).group(1)
            link_to = re.search(r'.{63}(.+)[\r\n]+', iface).group(1)
            try:
                ip = re.search(r'\s+(\d+.\d+.\d+.\d+/\d+)', iface, re.MULTILINE).group(1)
            except AttributeError:
                ip = False
            interface_facts.update({iface_name.rstrip(): {
                                'admin_status': admin_status,
                                'ipv4_status': ipv4_status,
                                'ipv6_status': ipv6_status,
                                'mode': mode,
                                'ip': ip,
                                'link_to': link_to.rstrip()
                                }})
        return interface_facts

    def get_facts(self):
        sys_info = '/show system information'
        sys_name = '{} | match "System Name"\n'.format(sys_info)
        sys_type = '{} | match "System Type"\n'.format(sys_info)
        serial = '/show chassis\n/show chassis detail\n'
        sys_version = '{} | match "System Version"\n'.format(sys_info)
        sys_uptime = '{} | match "System Up Time"\n'.format(sys_info)
        self.device.send(sys_name + sys_type + serial + sys_version + sys_uptime)
        time.sleep(1)
        output = self.device.recv(65535)
        hostname = re.search(r'System Name +: (.*)', output).group(1)
        try:
            model = re.search(r'System Type +: (.*)', output).group(1)
        except AttributeError:
            model = False
        try:
            serial_number = re.search(r'Serial number +: (.*)', output).group(1)
        except AttributeError:
            serial_number = False
        os_version = re.search(r'System Version +: (.*)', output).group(1)
        try:
            uptime = re.search(r'System Up Time +: (.*) \(', output).group(1)
        except AttributeError:
            uptime = False
        return {
            'vendor': 'Nokia',
            'model': model.rstrip(),
            'serial_number': serial_number.rstrip(),
            'os_version': os_version.rstrip(),
            'hostname': hostname.rstrip(),
            'fqdn': hostname.rstrip(),
            'uptime': uptime,
            'interface': self.get_interfaces().keys()
            }

    def get_arp_table(self):
        self.device.send("/show router arp\n")
        time.sleep(1)
        output = self.device.recv(65535)
        arp_output = output.splitlines()
        arp_table = []
        for arp_entry in arp_output:
            arp_search = re.search('^(\d+.\d+.\d+.\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.*)', arp_entry)
            try:
                ip = arp_search.group(1)
                mac = arp_search.group(2)
                age = 0
                iface = arp_search.group(5)
            except Exception as f:
                pass
            else:
                arp_table.append({'mac': mac,
                                  'ip': ip,
                                  'interface': iface,
                                  'age': age})
        return arp_table

    def get_bgp_config(self, group='', neighbor='', vrf=''):
        bgp_response = self.command('/show router {} bgp neighbor\n'.format(vrf))
        neigh_list_section = self._get_bgp_neighbors_section(bgp_response)
        bgp_n_parms = self._get_bgp_neighbors_parms(neigh_list_section)
        bgp_gr_response = self.command('/show router {} bgp group\n'.format(vrf))
        gr_list_section = self._get_bgp_group_section(bgp_gr_response)
        bgp_gr_parms = self._get_bgp_group_parms(gr_list_section)
        for bgp_gr in bgp_gr_parms.keys():
            neighbors = [x for x in bgp_n_parms.keys()
                         if bgp_n_parms[x]['bgp_group'] == bgp_gr]
            neighb_dict = {x:bgp_n_parms[x] for x in neighbors}
            bgp_gr_parms[bgp_gr].update({'neighbors': neighb_dict})
        if group and group in bgp_gr_parms:
            return bgp_gr_parms[group]
        if neighbor and neighbor in bgp_n_parms:
            return bgp_n_parms[neighbor]
        return bgp_gr_parms


    def _get_bgp_neighbors_parms(self, neighbors_list):
        bgp_neighbors_parms = {}
        for neighbor in neighbors_list:
            bgp_group = self._search_func('Group\s+:\s(.*)',neighbor, '')
            r_neighbor = self._search_func('Peer\s+:\s(\d+.\d+.\d+.\d+)',
                                                neighbor, '')
            desc = self._search_func('Description\s+:\s(.*)', neighbor, '')
            im_pol = self._search_func('Import Policy\s+:\s(.*)', neighbor, '')
            ex_pol = self._search_func('Export Policy\s+:\s(.*)', neighbor, '')
            loc_add = self._search_func('Local Address\s+:\s(\d+.\d+.\d+.\d+)',
                                                neighbor, '')
            loc_as = self._search_func('Local AS\s+:\s(\S+)', neighbor, 0)
            peer_as = self._search_func('Peer AS\s+:\s(\S+)', neighbor, 0)
            auth = self._search_func('Auth key chain\s+:\s(\S+)', neighbor, '')
            prefix_l = self._search_func('Prefix Limit\s+:\s(\S+)', neighbor, {})
            rr_client = self._search_func('Cluster Id\s+:\s(\d+.\d+.\d+.\d+)',
                                                neighbor, False)
            if rr_client:
                rr_client = True
            nhs = self._search_func('Next Hop Self\s+:\s(Enabled)', neighbor, False)
            if nhs:
                nhs = True
            bgp_neighbors_parms[r_neighbor] = {
                'bgp_group': bgp_group,
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
            n_search = re.search(r'(Peer[ ]{{1,17}}: {})'.format(neighbor),
                                 bgp_response).group(1)
            neighbor_start = bgp_response.index(n_search)
            section = bgp_response[neighbor_start:]
            if (n_index + 1) == neighbors_len:
                neighbor_sect = section
            else:
                neighbor_end = section.index(': {}'.format(neighbors[n_index + 1]))
                neighbor_sect = section[:neighbor_end]
            neighbors_list_section.append(neighbor_sect)
        return neighbors_list_section

    def _get_bgp_group_parms(self, bgp_groups_list):
        bgp_groups_parms = {}
        for bgp_group in bgp_groups_list:
            r_group = self._search_func('Group\s+:\s(.*)',
                                        bgp_group, '').rstrip()
            gr_type = self._search_func('Group Type\s+:\s(\w+)',
                                        bgp_group, '')
            desc = self._search_func('Description\s+:\s(.*)', bgp_group, '')
            multihop = self._search_func('Multihop\s+:\s(\d+)', bgp_group, 0)
            multipath = self._search_func('Multipath\s+:\s(\d+)', bgp_group, False)
            im_pol = self._search_func('Import Policy\s+:\s(.*)', bgp_group, '')
            ex_pol = self._search_func('Export Policy\s+:\s(.*)', bgp_group, '')
            loc_add = self._search_func('Local Address\s+:\s(\d+.\d+.\d+.\d+)',
                                        bgp_group, '')
            loc_as = self._search_func('Local AS\s+:\s(\S+)', bgp_group, 0)
            peer_as = self._search_func('Peer AS\s+:\s(\S+)', bgp_group, 0)
            remove_private_as = self._search_func('Remove Private\s+:\s(\S+)',
                                                  bgp_group, False)
            if remove_private_as:
                remove_private_as = True
            prefix_l = self._search_func('Prefix Limit\s+:\s(\S+)',
                                         bgp_group, {})
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
            g_search = re.search(r'(Group[ ]{{1,12}}: {})'.format(group),
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

    def get_bgp_neighbors(self, vrf=''):
        neighbors_parms = {}
        bgp_response = self.command('/show router {} '
                                        'bgp summary\n'.format(vrf))
        if bgp_response:
            loc_as = self._search_func('Local AS:(\d+)', bgp_response, 0)
            router_id = self._search_func('BGP Router ID:(\d+.\d+.\d+.\d+)',
                                                    bgp_response, 0)
            neighbors = self._get_bgp_summary_section(bgp_response)
            if vrf:
                vrf_id = vrf
            else:
                vrf_id = 'global'
            neighbors_parms[vrf_id] = {}
            for neighbor_sec in neighbors:
                neighbor = re.search(r'^(\d+.\d+.\d+.\d+)',
                                     neighbor_sec).group(1)
                shutdown = self._search_func(r'(Shutdown)',
                                     neighbor_sec, False)
                is_enabled = not shutdown
                uptime = self._search_func('(\d+[dhmsy]\d\d[dhms]\d\d[hms])',
                                                        neighbor_sec, False)
                n_split_sec = neighbor_sec.splitlines()[1:]
                bgp_conf = self.get_bgp_config(group='',
                                            neighbor=neighbor, vrf=vrf)
                peer_as = bgp_conf['remote_as']
                if re.search(r'(\d+)/(\d+)/(\d+)', neighbor_sec):
                    is_up = True
                    bgp_state = 'Established'
                else:
                    is_up = False
                    bgp_state = self._search_func('{}\s(\w+)'.format(uptime),
                                                  neighbor_sec, False)
                family_dict = {}
                for section in n_split_sec:
                    if is_enabled:
                        family = self._search_func('\((.*)\)', section, False)
                        if family:
                            prefixes = re.search(r'(\d+)/(\d+)/(\d+)', section)
                            r_pref = prefixes.group(1)
                            a_pref = prefixes.group(2)
                            s_pref = prefixes.group(3)
                            family_dict[family] = {'received_prefixes': r_pref,
                                                'accepted_prefixes': a_pref,
                                                'sent_prefixes': s_pref}
                neighbors_parms[vrf_id].update({neighbor: {
                    'local_as': loc_as,
                    'remote_as': peer_as,
                    'router_id': router_id,
                    'uptime': uptime,
                    'remote_id': neighbor,
                    'is_enabled': is_enabled,
                    'bgp_state': bgp_state,
                    'is_up': is_up,
                    'address_family': family_dict}})
            return neighbors_parms

    def _get_bgp_summary_section(self, bgp_response):
        neighbors = re.findall(r'^(\d+.\d+.\d+.\d+)', bgp_response,
                                                            re.MULTILINE)
        neighbors = [x.strip() for x in neighbors]
        neighbors_list_section = []
        neighbors_len = len(neighbors)
        for neighbor in neighbors:
            n_index = neighbors.index(neighbor)
            n_search = re.search(r'^({})\D+'.format(neighbor),
                                 bgp_response, re.MULTILINE).group(1)
            neighbor_start = bgp_response.index(n_search)
            section = bgp_response[neighbor_start:]
            if (n_index + 1) == neighbors_len:
                neighbor_sect = section
            else:
                neighbor_end = section.index('{}'.format(neighbors[n_index + 1]))
                neighbor_sect = section[:neighbor_end]
            neighbors_list_section.append(neighbor_sect)
        return neighbors_list_section

    def get_bgp_config_detail(self, neighbor='', vrf=''):
        bgp_response = self.command('/show router {} bgp summary\n'.format(vrf))
        neighbors = re.findall(r'^(\d+.\d+.\d+.\d+)', bgp_response, re.M)
        if neighbor:
            neighbors = [neighbor]
        bgp_details = self._get_bgp_neigh_detail(neighbors, vrf=vrf)
        return bgp_details

    def _get_bgp_neigh_detail(self, neighbors_list, vrf=''):
        bgp_neighbors_parms = {}
        for neighbor in neighbors_list:
            show = '/show router {}'.format(vrf).rstrip()
            bgp_response = self.command('{} bgp neighbor {} '
                            'detail\n'.format(show, neighbor))
            is_up = self._search_func('State\s+:\s(Established)', bgp_response, '')
            if is_up:
                x_is_up = True
            else:
                x_is_up = False
            loc_as = self._search_func('Local AS\s+:\s(\S+)', bgp_response, 0)
            peer_as = self._search_func('Peer AS\s+:\s(\S+)', bgp_response, 0)
            router_id = neighbor
            loc_add = self._search_func('Local Address\s+:\s(\d+.\d+.\d+.\d+)',
                                        bgp_response, '')
            remote_add = self._search_func('Peer Address\s+:\s(\d+.\d+.\d+.\d+)',
                                        bgp_response, '')
            loc_port = self._search_func('Local Port\s+:\s(\d+)',
                                        bgp_response, '')
            multihop = self._search_func('Multihop\s+:\s(\d+)',
                                         bgp_response, '')
            r_multihop = not multihop
            mutltipath = self._search_func('Local AddPath\.*:\s(Disabled)',
                                         bgp_response, '')
            r_multipath = not mutltipath
            remove_priv = self._search_func('Remove Private\s+:\s(Disabled)',
                                           bgp_response, '')
            r_remove_priv = not remove_priv
            bgp_group = self._search_func('Group\s+:\s(.*)', bgp_response, '')
            cmd = '/configure router bgp group {} neighbor '\
                            '{}\ninfo\n'.format(bgp_group, neighbor)
            policy_check = self.command(cmd)
            import_policies = self._policy_search('import', policy_check)
            export_policies = self._policy_search('export', policy_check)
            in_mess = self._search_func('i/p Messages\s+:\s(\d+)', bgp_response, 0)
            out_mess = self._search_func('o/p Messages\s+:\s(\d+)', bgp_response, 0)
            in_update = self._search_func('i/p Updates\s+:\s(\d+)', bgp_response, 0)
            out_update = self._search_func('o/p Updates\s+:\s(\d+)', bgp_response, 0)
            m_queued_out = self._search_func('Output Queue\s+:\s(\d+)', bgp_response, 0)
            state = self._search_func('State\s+:\s(\w+)', bgp_response, '')
            prev_state = self._search_func('Last State\s+:\s(\w+)', bgp_response, '')
            last_state = self._search_func('Last Event\s+:\s(\w+)', bgp_response, '')
            hold_time = self._search_func('Hold Time\s+:\s(\w+)', bgp_response, 0)
            keepalive = self._search_func('Keep Alive\s+:\s(\w+)', bgp_response, 0)
            active_ipv4 = self._search_func('IPv4 Active Prefixes\s+:\s(\w+)', bgp_response, 0)
            active_vpn_ipv4 = self._search_func('VPN-IPv4 Active Pfxs\s+:\s(\w+)', bgp_response, 0)
            receive_ipv4 = self._search_func('IPv4 Recd. Prefixes\s+:\s(\w+)', bgp_response, 0)
            receive_vpn_ipv4 = self._search_func('VPN-IPv4 Recd. Pfxs\s+:\s(\w+)', bgp_response, 0)
            sup_pfx_count = self._search_func('IPv4 Suppressed Pfxs\s+:\s(\w+)', bgp_response, 0)
            sup_pfx_count_vpn = self._search_func('VPN-IPv4 Suppr. Pfxs\s+:\s(\w+)', bgp_response, 0)
            flap = self._search_func('Num of Update Flaps\s+:\s(\w+)', bgp_response, 0)
            bgp_neighbors_parms[neighbor] = {
                'is_up': x_is_up,
                'local_as': loc_as,
                'remote_as': peer_as,
                'router_id': router_id,
                'local_address': loc_add,
                'remote_add': remote_add,
                'loc_port': loc_port,
                'multihop': r_multihop,
                'multipath': r_multipath,
                'remove_private_as': r_remove_priv,
                'import_policy': import_policies,
                'export_policy': export_policies,
                'input_messages': in_mess,
                'output_messages': out_mess,
                'input_updates': in_update,
                'output_updates': out_update,
                'messages_queued_out': m_queued_out,
                'connection_state': state,
                'previous_connection_state': prev_state,
                'last_event': last_state,
                'holdtime': hold_time,
                'keepalive': keepalive,
                'active_prefix_count': active_ipv4,
                'active_pfx_vpn_ipv4_count': active_vpn_ipv4,
                'receive_prefix_count': receive_ipv4,
                'receive_pfx_vpn_ipv4_count': receive_vpn_ipv4,
                'suppressed_prefix_count': sup_pfx_count,
                'suppressed_pfx_count_vpn_ipv4': sup_pfx_count_vpn,
                'flap_count': flap}
        return bgp_neighbors_parms

    def _policy_search(self, direction, bgp_response):
        try:
            pol_start = bgp_response.index(direction)
        except Exception:
            return False
        else:
            section = bgp_response[pol_start:]
            try:
                pol_end_search = re.search(r'\s{20}(\w+)', section, re.M).group(1)
            except Exception:
                pol_end_search = False
            if pol_end_search:
                pol_end = section.index(pol_end_search)
                policy_sec = section[:pol_end]
            else:
                policy_sec = section
            policies = re.findall(r'".*?"', policy_sec)
            return policies

    def _search_func(self, search_for, search_in, option=None):
        try:
            ser_object = re.search('{}'.format(search_for), search_in).group(1)
        except AttributeError:
            if option:
                ser_object = option
            else:
                ser_object = False
        if type(ser_object) == str:
            ser_object = ser_object.strip()
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