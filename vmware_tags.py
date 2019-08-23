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
import atexit
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from pyVim import connect
from pyVmomi import vim

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


# Function to get all the tags
def get_tag_ids():
    api_tags = s.get('https://' + vmware_server + '/rest/com/vmware/cis/tagging/tag')
    return json.loads(api_tags.content)['value']


# Function to get all the present tags and attached objects
def get_tags():
    tags = dict()
    for tag in get_tag_ids():
        # Get the tag name
        api_tag_name = s.get('https://' + vmware_server + '/rest/com/vmware/cis/tagging/tag/id:' + tag)
        tag_prop = json.loads(api_tag_name.content)["value"]
        # Get the objects attached to the tag
        api_tag_items = s.post('https://' + vmware_server + '/rest/com/vmware/cis/tagging/tag-association/id:' + tag + '?~action=list-attached-objects')
        tag_items = json.loads(api_tag_items.content)["value"]
        # Update the dictionary
        if len(tag_items):
            tags.update({tag_prop.get('name'): tag_items})
    return tags


"""
Functions related to the pyVmomi
"""


# Function to get the vm info
def get_vms():
    service_instance = connect.SmartConnectNoSSL(host=vmware_server,
                                                 user=vmware_username,
                                                 pwd=vmware_password)

    atexit.register(connect.Disconnect, service_instance)
    content = service_instance.RetrieveContent()
    container = content.rootFolder  # starting point to look into
    viewType = [vim.VirtualMachine]  # object types to look for
    recursive = True  # whether we should look into it recursively
    containerView = content.viewManager.CreateContainerView(container, viewType, recursive)

    return containerView.view


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

    vm_ids = dict()
    # Parse all vms from the vCenter
    for v in get_vms():
        vm_name = v.summary.vm.name
        vm_ids.update({v._moId: vm_name})
        # For all the powered-on vms
        if v.summary.guest is not None and v.summary.runtime.powerState == "poweredOn":
            ip_address = v.summary.guest.ipAddress
            if ip_address:
                # Add the vm to the inventory
                inventory["all"]["hosts"].append(vm_name)
                inventory["_meta"]["hostvars"].update({vm_name: {
                    "ansible_ssh_host": ip_address, "ansible_ssh": ip_address,
                    "vm_folder": v.summary.vm.parent.name,
                    "vm_id": v._moId, "vm_uuid": v.config.instanceUuid,
                    "vm_host": v.runtime.host.name, "vm_cluster": v.runtime.host.parent.name,
                    "vm_datacenter": v.runtime.host.parent.parent.parent.name
                }})

                # Search for trigram then add the vm to the inventory group
                app = re.search("^[a-zA-Z][0-9][0-9]-", vm_name)
                if app:
                    app = app.group().lower()
                    app = app[:3]
                    if app not in inventory:
                        inventory[app] = {"hosts": []}
                    inventory[app]["hosts"].append(vm_name)

    all_tags = get_tags()

    # Parse the tag list
    for k, v in all_tags.items():
        # For all the vms contained into that tag
        for t in v:
            if t["type"] == "VirtualMachine":
                vm_name = vm_ids.get(t["id"])
                if vm_name in inventory.get("all")["hosts"]:
                    if k not in inventory:
                        inventory[k] = {"hosts": []}
                    inventory[k]["hosts"].append(vm_name)

    # Output the result
    print json.dumps(inventory, indent=2)


# Start program
if __name__ == "__main__":
    main()
