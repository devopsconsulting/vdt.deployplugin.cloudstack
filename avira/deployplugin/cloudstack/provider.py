import subprocess
from cloudstack.client import Client
from avira.deploy import api, pretty
from avira.deploy.clean import run_machine_cleanup, \
    remove_machine_port_forwards, node_clean, clean_foreman
from avira.deploy.userdata import UserData
from avira.deploy.utils import find_by_key, \
    find_machine, wrap, sort_by_key, is_puppetmaster, check_call_with_timeout
from avira.deploy.certificate import add_pending_certificate
from avira.deploy.config import cfg

__all__ = ('Provider',)


class Provider(api.CmdApi):
    """Cloudstack Deployment CMD Provider"""
    prompt = "cloudstack> "

    def __init__(self):
        self.client = Client(cfg.APIURL, cfg.APIKEY, cfg.SECRETKEY)
        api.CmdApi.__init__(self)

    def do_status(self, all=False):
        """
        Shows running instances, specify 'all' to show all instances

        Usage::

            cloudstack> status [all]
        """
        machines = self.client.listVirtualMachines({
            'domainid': cfg.DOMAINID
        })
        machines = sort_by_key(machines, 'displayname')
        if not all:
            ACTIVE = ['Running', 'Stopping', 'Starting']
            machines = [x for x in machines if x['state'] in ACTIVE]

        pretty.machine_print(machines)

    def do_deploy(self, displayname, base=False, networkids="", **userdata):
        """
        Create a vm with a specific name and add some userdata.

        Optionally specify extra network ids.

        Usage::

            cloudstack> deploy <displayname> <userdata>
                    optional: <networkids> <base>

        To specify the puppet role in the userdata, which will install and
        configure the machine according to the specified role use::

            cloudstack> deploy loadbalancer1 role=lvs

        To specify additional user data, specify additional keywords::

            cloudstack> deploy loadbalancer1 role=lvs environment=test etc=more

        This will install the machine as a Linux virtual server.

        You can also specify additional networks using the following::

            cloudstack> deploy loadbalancer1 role=lvs networkids=312,313

        if you don't want pierrot-agent (puppet agent) automatically installed,
        you can specify 'base' as a optional parameter. This is needed for the
        puppetmaster which needs manual installation::

            cloudstack> deploy puppetmaster role=puppetmaster base

        """
        if not userdata:
            print "Specify the machine userdata, (at least it's role)"
            return

        vms = self.client.listVirtualMachines({
            'domainid': cfg.DOMAINID
        })

        KILLED = ['Destroyed', 'Expunging']
        existing_displaynames = \
            [x['displayname'] for x in vms if x['state'] not in KILLED]

        if displayname not in existing_displaynames:
            cloudinit_url = cfg.CLOUDINIT_BASE if base else cfg.CLOUDINIT_PUPPET

            args = {
                'serviceofferingid': cfg.SERVICEID,
                'templateid': cfg.TEMPLATEID,
                'zoneid': cfg.ZONEID,
                'domainid': cfg.DOMAINID,
                'displayname': displayname,
                'userdata': UserData(cloudinit_url,
                                     cfg.PUPPETMASTER,
                                     **userdata).base64(),
                'networkids': networkids,
            }

            response = self.client.deployVirtualMachine(args)

            # we add the machine id to the cert req file, so the puppet daemon
            # can sign the certificate
            if not base:
                add_pending_certificate(response['id'])

            print "%s started, machine id %s" % (displayname, response['id'])

        else:
            print "A machine with the name %s already exists" % displayname

    def do_destroy(self, machine_id):
        """
        Destroy a machine.

        Usage::

            cloudstack> destroy <machine_id>
        """

        machines = self.client.listVirtualMachines({
            'domainid': cfg.DOMAINID
        })

        machine = find_machine(machine_id, machines)

        if machine is None:
            print "No machine found with the id %s" % machine_id
        else:
            if is_puppetmaster(machine.id):
                print "You are not allowed to destroy the puppetmaster"
                return
            print "running cleanup job on %s." % machine.name
            run_machine_cleanup(machine)

            print "Destroying machine with id %s" % machine.id
            self.client.destroyVirtualMachine({
                'id': machine.id
            })

            # first we are also going to remove the portforwards
            remove_machine_port_forwards(machine, self.client)

            # now we cleanup the puppet database and certificates
            print "running puppet node clean"
            node_clean(machine)

            # now clean all offline nodes from foreman
            clean_foreman()

    def do_start(self, machine_id):
        """
        Start a stopped machine.

        Usage::

            cloudstack> start <machine_id>
        """

        machines = self.client.listVirtualMachines({
            'domainid': cfg.DOMAINID
        })
        machine = find_machine(machine_id, machines)

        if machine is not None:
            print "starting machine with id %s" % machine.id
            self.client.startVirtualMachine({'id': machine.id})
        else:
            print "machine with id %s is not found" % machine_id

    def do_stop(self, machine_id):
        """
        Stop a running machine.

        Usage::

            cloudstack> stop <machine_id>
        """

        machines = self.client.listVirtualMachines({
            'domainid': cfg.DOMAINID
        })
        machine = find_machine(machine_id, machines)

        if machine is not None:
            print "stopping machine with id %s" % machine.id
            self.client.stopVirtualMachine({'id': machine.id})
        else:
            print "machine with id %s is not found" % machine_id

    def do_reboot(self, machine_id):
        """
        Reboot a running machine.

        Usage::

            cloudstack> reboot <machine_id>
        """

        machines = self.client.listVirtualMachines({
            'domainid': cfg.DOMAINID
        })
        machine = find_machine(machine_id, machines)

        if machine is not None:
            print "rebooting machine with id %s" % machine.id
            self.client.rebootVirtualMachine({'id': machine.id})
        else:
            print "machine with id %s is not found" % machine_id

    def do_list(self, resource_type):
        """
        List information about current cloudstack configuration.

        Usage::

            cloudstack> list <templates|serviceofferings|
                          diskofferings|ip|networks|portforwardings|
                          firewall>
        """

        if resource_type == "templates":
            zone_map = {x['id']: x['name'] for x in self.client.listZones({})}
            templates = self.client.listTemplates({
                "templatefilter": "executable"
            })
            templates = sort_by_key(templates, 'name')
            pretty.templates_print(templates, zone_map)

        elif resource_type == "serviceofferings":
            serviceofferings = self.client.listServiceOfferings()
            pretty.serviceofferings_print(serviceofferings)

        elif resource_type == "diskofferings":
            diskofferings = self.client.listDiskOfferings()
            pretty.diskofferings_print(diskofferings)

        elif resource_type == "ip":
            ipaddresses = self.client.listPublicIpAddresses()
            pretty.public_ipaddresses_print(ipaddresses)

        elif resource_type == "networks":
            networks = self.client.listNetworks({
                'zoneid': cfg.ZONEID
            })
            networks = sort_by_key(networks, 'id')
            pretty.networks_print(networks)

        elif resource_type == "portforwardings":
            portforwardings = self.client.listPortForwardingRules({
                'domain': cfg.DOMAINID
            })
            portforwardings = sort_by_key(portforwardings, 'privateport')
            portforwardings.reverse()
            pretty.portforwardings_print(portforwardings)
        elif resource_type == "firewall":
            firewall_rules = self.client.listFirewallRules({
                'domain': cfg.DOMAINID
            })
            firewall_rules = sort_by_key(firewall_rules, 'ipaddress')
            firewall_rules.reverse()
            pretty.firewallrules_print(firewall_rules)
        else:
            print "Not implemented"

    def do_request(self, request_type):
        """
        Request a public ip address on the virtual router

        Usage::

            cloudstack> request ip
        """
        if request_type == "ip":
            response = self.client.associateIpAddress({
                'zoneid': cfg.ZONEID
            })
            print "created ip address with id %(id)s" % response

        else:
            print "Not implemented"

    def do_release(self, request_type, release_id):
        """
        Release a public ip address with a specific id.

        Usage::

            cloudstack> release ip <release_id>
        """
        if request_type == "ip":
            response = self.client.disassociateIpAddress({
                'id': release_id
            })
            print "releasing ip address, job id: %(jobid)s" % response
        else:
            print "Not implemented"

    def do_portfw(self, machine_id, ip_id, public_port, private_port):
        """
        Create a portforward for a specific machine and ip

        Usage::

            cloudstack> portfw <machine id> <ip id> <public port> <private port>

        You can get the machine id by using the following command::

            cloudstack> status

        You can get the listed ip's by using the following command::

            cloudstack> list ip
        """

        self.client.createPortForwardingRule({
            'ipaddressid': ip_id,
            'privateport': private_port,
            'publicport': public_port,
            'protocol': 'TCP',
            'virtualmachineid': machine_id
        })
        print "added portforward for machine %s (%s -> %s)" % (
            machine_id, public_port, private_port)

    def do_ssh(self, machine_id, ssh_public_port):
        """
        Make a machine accessible through ssh.

        Usage::

            cloudstack> ssh <machine_id> <ssh_public_port>

        This adds a port forward under the machine id to port 22 on the machine
        eg:

        machine id is 5034, after running::

            cloudstack> ssh 5034 22001

        I can now access the machine though ssh on all my registered ip
        addresses as follows::

            ssh ipaddress -p 22001
        """
        machines = self.client.listVirtualMachines({
            'domainid': cfg.DOMAINID
        })
        machine = find_machine(machine_id, machines)
        if machine is None:
            print "machine with id %s is not found" % machine_id
            return

        portforwards = wrap(self.client.listPortForwardingRules())

        def select_ssh_pfwds(pf):
            return pf.virtualmachineid == machine.id and pf.publicport == ssh_public_port
        existing_ssh_pfwds = filter(select_ssh_pfwds, portforwards)

        # add the port forward to each public ip, if it doesn't exist yet.
        ips = wrap(self.client.listPublicIpAddresses()['publicipaddress'])
        for ip in ips:
            current_fw = find_by_key(existing_ssh_pfwds, ipaddressid=ip.id)
            if current_fw is not None:
                print "machine %s already has a ssh portforward with ip %s to port %s" % (
                    machine_id, ip.ipaddress, ssh_public_port)
                continue
            else:
                self.client.createPortForwardingRule({
                    'ipaddressid': ip.id,
                    'privateport': "22",
                    'publicport': str(ssh_public_port),
                    'protocol': 'TCP',
                    'virtualmachineid': machine.id,
                    'openfirewall': "True",
                })
                print "machine %s is now reachable (via %s:%s)" % (
                    machine_id, ip.ipaddress, ssh_public_port)

    def do_kick(self, machine_id=None, role=None):
        """
        Trigger a puppet run on a server.

        This command only works when used on the puppetmaster.
        The command will either kick a single server or all server with a
        certian role.

        Usage::

            cloudstack> kick <machine_id>

        or::

            cloudstack> kick role=<role>

        """
        KICK_CMD = ['mco', "puppetd", "runonce", "-F"]
        if role is not None:
            KICK_CMD.append("role=%s" % role)
        else:
            machines = self.client.listVirtualMachines({
                'domainid': cfg.DOMAINID
            })
            machine = find_machine(machine_id, machines)
            if machine is None:
                print "machine with id %s is not found" % machine_id
                return
            KICK_CMD.append('hostname=%(name)s' % machine)

        try:
            print subprocess.check_output(KICK_CMD, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            print e.output

    def do_quit(self, _=None):
        """
        Quit the deployment tool.

        Usage::

            cloudstack> quit
        """
        return True

    def do_mco(self, *args, **kwargs):
        """
        Run mcollective

        Usage::

            cloudstack> mco find all
            cloudstack> mco puppetd status -F role=puppetmaster
        """
        command = ['mco'] + list(args) + ['%s=%s' % (key, value) for (key, value) in kwargs.iteritems()]
        check_call_with_timeout(command, 5)
