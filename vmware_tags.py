#!/usr/bin/env python

"""
(c) 2019, Ronan Chabert
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""


import os
import requests
import json
import re
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()

s = requests.Session()
s.verify = False


"""
Get the environment variables
"""


vmware_server = os.environ.get('VMWARE_HOST')
vmware_username = os.environ.get('VMWARE_USER')
vmware_password = os.environ.get('VMWARE_PASSWORD')
vmware_roottag = os.environ.get('VMWARE_ROOTTAG', False)
vmware_resource_pool = os.environ.get('VMWARE_RESOURCE_POOL', False)
vmware_validate_certs = os.environ.get('VMWARE_VALIDATE_CERTS', False)
if vmware_validate_certs in ['no', 'false', 'False', False]:
    vmware_validate_certs = False

if vmware_validate_certs:
    print("vmware_validate_certs True is not supported yet")
    exit(1)


"""
Functions related to the vCenter API exchange
"""


# Function to get the vCenter server session
def get_vc_session():
    s.post('https://' + vmware_server + '/rest/com/vmware/cis/session', auth=(vmware_username, vmware_password))
    return s


# Function to get the resource pool full list
def get_resource_pool_ids():
    api_resource_pool = s.get('https://' + vmware_server + '/rest/vcenter/resource-pool/')
    resource_pool_list = dict()
    for resource_pool in json.loads(api_resource_pool.content)['value']:
        resource_pool_list.update({resource_pool.get('name'): resource_pool.get('resource_pool')})
    return resource_pool_list


# Function to get all the tags
def get_tag_ids():
    api_tags = s.get('https://' + vmware_server + '/rest/com/vmware/cis/tagging/tag')
    return json.loads(api_tags.content)['value']


# Function to get all the present tags and attached objects
def get_tags():
    tags = dict()
    # Foreach tags
    for tag in get_tag_ids():
        vm_by_tag = list()
        # Get the tag name
        api_tag_name = s.get('https://' + vmware_server + '/rest/com/vmware/cis/tagging/tag/id:' + tag)
        tag_prop = json.loads(api_tag_name.content)["value"]
        # Get the objects attached to the tag
        api_tag_items = s.post('https://' + vmware_server + '/rest/com/vmware/cis/tagging/tag-association/id:' + tag + '?~action=list-attached-objects')
        tag_items = json.loads(api_tag_items.content)["value"]
        # Update the dictionary
        if len(tag_items):
            for vm in tag_items:
                vm_by_tag.append(vm.get('id'))
            tags.update({tag_prop.get('name'): vm_by_tag})
    return tags


# Function to get vm tool info
def get_vm_identity(vm_id):
    api_hosts = s.get('https://' + vmware_server + '/rest/vcenter/vm/' + vm_id + '/guest/identity')
    return json.loads(api_hosts.content)['value']


# Function to get all vmware hosts
def get_hosts(cluster=False):
    uri = 'https://' + vmware_server + '/rest/vcenter/host/'
    if cluster:
        uri += '?filter.clusters=' + cluster
    api_hosts = s.get(uri)
    return json.loads(api_hosts.content)['value']


# Function to get all vmware clusters
def get_clusters_tree():
    topology = {"hosts": [], "clusters": {}}
    api_clusters = s.get('https://' + vmware_server + '/rest/vcenter/cluster')
    for cluster in json.loads(api_clusters.content)['value']:
        hosts = get_hosts(cluster=cluster.get('cluster'))
        topology["clusters"].update({cluster.get('name'): hosts})
        for host in hosts:
            host.update({'cluster': cluster.get('name')})
            topology["hosts"].append(host)
        # topology["hosts"].extend(hosts)
    return(topology)

# Function to get the vm info
def get_vms():
    topology = get_clusters_tree()
    vms = dict()
    # Get the resource pool id if needed
    if vmware_resource_pool:
        resource_pool_id = get_resource_pool_ids().get(vmware_resource_pool)
    # For each host
    for host in topology.get("hosts"):
        # Get the vm list of this host
        uri = 'https://' + vmware_server + '/rest/vcenter/vm/?filter.hosts=' + host.get('host')
        if vmware_resource_pool and resource_pool_id:
            uri += '&filter.resource_pools=' + resource_pool_id
        api_vms = s.get(uri)
        for vm in json.loads(api_vms.content)['value']:
            vm_name = vm.get('vm')
            vm.update({'host': host.get('name')})
            vm.update({'cluster': host.get('cluster')})
            vms.update({vm_name: vm})
    return vms


"""
Functions related to the inventory object
"""


def _empty_inventory():
    # Create an empty inventory
    return {"all": {"hosts": []}, "_meta": {"hostvars": {}}}


"""
Main
"""


def main():
    get_vc_session()
    inventory = _empty_inventory()
    vm_by_tag = get_tags()

    # Exit if the roottag does not exists
    if vmware_roottag:
        if not vm_by_tag.get(vmware_roottag):
            print('Roottag not found')
            exit(1)

    vm_list = get_vms()

    # For all the vms referenced in the vCenter
    for vm in vm_list.values():
        vm_name = vm.get('name')
        vm_id = vm.get('vm')

        # Skip this vm if it does not belong to roottag
        if vmware_roottag:
            if vm_id not in vm_by_tag.get(vmware_roottag):
                continue

        # Adding hostvars
        ansible_variables = dict()
        if vm.get('power_state') == 'POWERED_ON':
            vm.update({'identity': get_vm_identity(vm_id)})
            if vm.get("identity").get("ip_address"):
                ansible_variables.update({"ansible_host": vm.get("identity").get("ip_address")})

            inventory["all"]["hosts"].append(vm_name)
            if ansible_variables:
                inventory["_meta"]["hostvars"].update({vm_name: ansible_variables})


    # For all tags
    for tag in vm_by_tag.keys():
        # And for all host in that tag
        for vm in vm_by_tag.get(tag):
            try:
                vm_name = vm_list.get(vm).get('name')
            except:
                pass
            else:
                # If that host exists in the current inventory
                if vm_name in inventory.get('all').get('hosts'):
                    if tag not in inventory:
                        inventory[tag] = {"hosts": []}
                    inventory[tag]["hosts"].append(vm_name)
                    
    print(json.dumps(inventory, indent=2))


# Start program
if __name__ == "__main__":
    main()
