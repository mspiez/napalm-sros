#!/usr/bin/env python

import paramiko
import re
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
        output = output.split('exclude-services')
        interfaces_split = re.split('--------+', output[1])
        all_int = re.split('(\w.*\n.*)\n', interfaces_split[1])
        int_list = []
        for interface in all_int:
            if interface != '\n' and interface != '' and interface != '\r\n':
                int_list.append(interface)
        interface_facts = {}
        for interface in int_list:
            interface_name = re.search('(^\S+)', interface).group(1)
            admin_status = re.search(' +(\w+)', interface).group(1)
            ipv4_status = re.search(' +\w+ +(\w+)/\S+', interface).group(1)
            ipv6_status = re.search(' +\w+ +\w+/(\S+)', interface).group(1)
            try:
                mode = re.search(' +\w+/\S+ +(\w+) ', interface).group(1)
            except AttributeError:
                mode = ''
            link_to = re.search(' +\w+/\S+ +\w+ +(\S+)\r\n', interface).group(1)
            try:
                ip = re.search('\n\s+(\d+.\d+.\d+.\d+/\d+)', interface).group(1)
            except AttributeError:
                ip = ''
            link_to = re.search(' +\w+/\S+ +\w+ +(\S+)\r\n', interface).group(1)
            interface_facts.update({interface_name: {
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
        sys_name = "/show system information | match \"System Name\"\n"
        sys_type = "/show system information | match \"System Type\"\n"
        serial = "/show chassis\n/show chassis detail\n"
        sys_version = "/show system information | match \"System Version\"\n"
        sys_uptime = "/show system information | match \"System Up Time\"\n"
        self.device.send("\n/environment no more\n")
        time.sleep(1)
        self.device.send(sys_name + sys_type + serial + sys_version + sys_uptime)
        time.sleep(1)
        output = self.device.recv(65535)
        hostname = re.search('System Name +: (.*)\r\n', output).group(1)
        try:
            model = re.search('System Type +: (.*)\r\n', output).group(1)
        except AttributeError:
            model = ''
        try:
            serial_number = re.search('Serial number +: (.*)\r\n', output).group(1)
        except AttributeError:
            serial_number = ''
        os_version = re.search('System Version +: (.*)\r\n', output).group(1)
        try:
            uptime = re.search('System Up Time +: (.*) \(', output).group(1)
        except AttributeError:
            uptime = ''
        return {
            'vendor': u'Nokia',
            'model': model,
            'serial_number': serial_number,
            'os_version': os_version,
            'hostname': hostname,
            'fqdn': hostname,
            'uptime': uptime,
            'interface': self.get_interfaces().keys()
            }

