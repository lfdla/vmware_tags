# Makes good use of VMware tags with Ansible

Organize your virtual infrastructure with tags in order to better target your playbook executions.
 
Imagine you have a very large virtualization infrastructure running ESXi hosts and a lot of virtual machines. Your vCenter your day-to-day tool and is also the best way of getting the most accurate real-time representation of the infrastructure. So it's quite intuitive to use the vCenter as a <a href="https://docs.ansible.com/ansible/latest/user_guide/intro_dynamic_inventory.html">dynamic inventory</a> source for your Ansible playbooks. Now here is the thing: maybe you don't want to manage all the virtual machines referenced in the vCenter. Imagine that some of the VMs are legacy old machines that you don't have access to anyway. Or maybe you just want to target some specific machines based on a declarative definitions that sits on the vCenter that other people in the organisation can manage for you.
 
Here comes VMware tags. Among other tools like folders and custom attributes, tags are great to organize your vSphere inventory. Because you can assign multiple tags to one virtual machine, this tool is very versatile and can be used to determine:
 
  - witch application runs on the vm
  - business and department ownership
  - tier (prod, dev, test)
  - some kind of class of service (bronze, silver, gold)
  - basically whatever make sense in your organisation
 
I'm going to use colours as tag to make this example generic. Here's a representation of what it looks like:

The goal here is to use those tags to target our Ansible executions. For instance, let's run a ping on machines that are taged red but not green.


<pre>[ronan@ansible]$ ansible -i lab.vmware.yml &apos;red:!green&apos; -m ping
<font color="#4E9A06">satellite-client-01 | SUCCESS =&gt; {</font>
<font color="#4E9A06">    &quot;changed&quot;: false, </font>
<font color="#4E9A06">    &quot;ping&quot;: &quot;pong&quot;</font>
<font color="#4E9A06">}</font>
<font color="#4E9A06">satellite-client-03 | SUCCESS =&gt; {</font>
<font color="#4E9A06">    &quot;changed&quot;: false, </font>
<font color="#4E9A06">    &quot;ping&quot;: &quot;pong&quot;</font>
<font color="#4E9A06">}</font>
</pre>
 
That's nice! Here is how to do that.
 
## Using VMware dynamic inventory plugin
 
The use of the VMware dynamic inventory plugin is well documented in the <a href="https://docs.ansible.com/ansible/latest/scenario_guides/vmware_scenarios/vmware_inventory.html">Ansible guide</a>.
 
The plugin require the installation of the <a href="https://github.com/vmware/vsphere-automation-sdk-python">VMware vSphere Automation SDK for Python</a> and PyVmomi. 
 
```
pip install pyvmomi
pip install setuptools
pip install git+https://github.com/vmware/vsphere-automation-sdk-python.git
```

You may want to use the `--ignore-installed` option in the last command if you encounter some conflict with your existing python modules.
 
Now make sure the plugin is enabled in your ansible.cfg configuration:

```ini
[inventory]
enable_plugins = vmware_vm_inventory
```

Then, create a file that ends in .vmware.yml or .vmware.yaml in your working directory. For instance:

```
[ronan@ansible]$ cat lab.vmware.yml 
plugin: vmware_vm_inventory
strict: False
hostname: <hostname>
username: <username>
password: <pass>
validate_certs: False
with_tags: True
```

I've made some change in the plugin itself to better suit my needs:
  - use the VM name as a key in the inventory instead of the name + UUID combination
  - disable the additional groups based on the VM state (poweredOn, powerredOff etc.)
  - disable the additional groups based on the guest id (rhel7_64Guest, centos64Guest etc.)
 
Let's list the inventory content:
 


```json
[ronan@ansible]$ ansible-inventory --list -i lab.vmware.yml
{
    "_meta": {
        "hostvars": {
            "satellite-client-01": {
                "ansible_host": "10.0.0.1", 
                "config.cpuHotAddEnabled": false, 
                "config.cpuHotRemoveEnabled": false, 
                "config.hardware.numCPU": 1, 
                "config.instanceUuid": "500ca010-ee71-0d35-1b8e-554ab4f1ea2a", 
                "config.name": "satellite-client-01", 
                "config.template": false, 
                "guest.guestId": "", 
                "guest.guestState": "running", 
                "guest.hostName": "satellite-client-01", 
                "guest.ipAddress": "10.0.0.1", 
                "name": "satellite-client-01", 
                "runtime.maxMemoryUsage": 2048
            }, 
            "satellite-client-02": {
                "ansible_host": "10.0.0.2", 
                "config.cpuHotAddEnabled": false, 
                "config.cpuHotRemoveEnabled": false, 
                "config.hardware.numCPU": 1, 
                "config.instanceUuid": "500cc016-6efa-bb38-7b8b-965cadaa697c", 
                "config.name": "satellite-client-02", 
                "config.template": false, 
                "guest.guestId": "", 
                "guest.guestState": "running", 
                "guest.hostName": "satellite-client-02", 
                "guest.ipAddress": "10.0.0.2", 
                "name": "satellite-client-02", 
                "runtime.maxMemoryUsage": 2048
            }, 
            "satellite-client-03": {
                "ansible_host": "10.0.0.3", 
                "config.cpuHotAddEnabled": false, 
                "config.cpuHotRemoveEnabled": false, 
                "config.hardware.numCPU": 1, 
                "config.instanceUuid": "500ce1d5-de4a-e1db-0c06-3d190e7f5f88", 
                "config.name": "satellite-client-03", 
                "config.template": false, 
                "guest.guestId": "", 
                "guest.guestState": "running", 
                "guest.hostName": "satellite-client-03", 
                "guest.ipAddress": "10.0.0.3", 
                "name": "satellite-client-03", 
                "runtime.maxMemoryUsage": 2048
            }, 
[...]
        }
    }, 
    "blue": {
        "hosts": [
            "satellite-client-02", 
            "satellite-server-02"
        ]
    }, 
    "green": {
        "hosts": [
            "satellite-client-02", 
            "satellite-server-02"
        ]
    }, 
    "red": {
        "hosts": [
            "satellite-client-01", 
            "satellite-client-02", 
            "satellite-client-03"
        ]
    }
[...]
}
```
 
Now Ansible has access to an accurate inventory of all your machines with additional groups based on VMware tags.
 
Some variables are also set for each host, including the IP address that is discovered trough the VMware tools. Ansible is now able to reach the host without DNS resolution.
 
## Using a custom inventory script
 
Writing a custom inventory script that talks directly to the vSphere API is also pretty simple. Unlike the VMware dynamic inventory plugin, it doesn't require the installation of the <a href="https://github.com/vmware/vsphere-automation-sdk-python">VMware vSphere Automation SDK for Python</a>.
 
This script only reference powered-on virtual machines with a discovered IP address.
 
Just copy the script in the current directory and make it executable. Then setup connection information by exporting some variables.

```
[ronan@ansible]$ export VMWARE_HOST=<hostname>
[ronan@ansible]$ export VMWARE_USER=<username>
[ronan@ansible]$ export VMWARE_PASSWORD=<password>
```

Thoses variables makes the script compatible with AWX / Ansible Tower. More on that in a future post.

```json
[ronan@ansible]$ ansible-inventory --list -i vmware_tags.py 
{
    "_meta": {
        "hostvars": {
            "satellite-client-01": {
                "ansible_ssh": "10.0.0.1", 
                "ansible_ssh_host": "10.0.0.1", 
                "vm_cluster": "cluster01", 
                "vm_datacenter": "Datacenter", 
                "vm_folder": "Satellite", 
                "vm_host": "esxi01.local", 
                "vm_id": "vm-508690", 
                "vm_uuid": "500ca010-ee71-0d35-1b8e-554ab4f1ea2a"
            }, 
            "satellite-client-02": {
                "ansible_ssh": "10.0.0.2", 
                "ansible_ssh_host": "10.0.0.2", 
                "vm_cluster": "cluster01", 
                "vm_datacenter": "Datacenter", 
                "vm_folder": "Satellite", 
                "vm_host": "esxi01.local", 
                "vm_id": "vm-508697", 
                "vm_uuid": "500cc016-6efa-bb38-7b8b-965cadaa697c"
            }, 
            "satellite-client-03": {
                "ansible_ssh": "10.0.0.2", 
                "ansible_ssh_host": "10.0.0.2", 
                "vm_cluster": "cluster01", 
                "vm_datacenter": "Datacenter", 
                "vm_folder": "Satellite", 
                "vm_host": "esxi01.local", 
                "vm_id": "vm-508698", 
                "vm_uuid": "500ce1d5-de4a-e1db-0c06-3d190e7f5f88"
            },
[...]
        }
    }, 
    "blue": {
        "hosts": [
            "satellite-client-02", 
            "satellite-server-02"
        ]
    }, 
    "green": {
        "hosts": [
            "satellite-client-02", 
            "satellite-server-02"
        ]
    }, 
    "red": {
        "hosts": [
            "satellite-client-01", 
            "satellite-client-02", 
            "satellite-client-03"
        ]
    }
[...]
}
```
