import argparse
import ipaddress
import json
import logging
import getpass
import pyaci
import itertools
import xlsxwriter
from requests.packages.urllib3 import disable_warnings
from pprint import pformat

# GLOBAL VARIABLES
DATA = dict()
BROKEN = list()
STATISTICS = {'nodes': 0, 'tenants': 0, 'vrfs': 0, 'l3outs': 0, 'ens': 0,
    'subnets': 0}

def generate_apic_urls(ips=None):
    """ Generate a list of URLs and append them to APIC_URL_LIST"""
    logging.info("Generating list of apicUrl")

    global DATA

    url_list = list()

    for ip in ips:
        logging.info("Test if {ip} is a valid IP".format(ip=ip))
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            logging.error("{ip} is not a valid IP. Skipping...".format(ip=ip))
            break
        url = "https://{ip}".format(ip=ip)
        DATA[url] = dict()
    
    logging.info("Generating successful. APIC_URL_LIST = {list}".format(
        list=url_list))

def get_tenant_names():
    """ Get names of Tenants for each fabric. Returns a list of Names """

    # Get all Tenants
    logging.info("trying to get all tenants")

    for node in DATA.keys():
        logging.info("getting tenants for {node}".format(node=node))

        result = DATA[node]["node"].mit.GET(
                **pyaci.options.subtreeClass('fvTenant'))

        DATA[node]["tenants"] = dict()
        for tenant in result:
            DATA[node]["tenants"][tenant.name] = dict()

    logging.info("Done getting Tenants")
    #logging.info("DATA:\n{data}".format(data=pformat(DATA)))
    return None

def get_vrfs():
    """ Get names of VRFs in Tenant. """

    # Get all VRFs
    logging.info("trying to get VRFs")

    global DATA

    for node in DATA.keys():
        for tenant in DATA[node]["tenants"]:
            
            result = DATA[node]["node"].mit.polUni().fvTenant(tenant).GET(
                    **pyaci.options.subtreeClass('fvCtx'))

            for vrf in result:
                DATA[node]["tenants"][tenant][vrf.name] = dict()

    #logging.info("DATA:\n{data}".format(data=pformat(DATA)))
    logging.info("done getting VRFs")
    return None

def get_l3outs():
    """ Get all L3outs """

    # Get all L3OUTS
    logging.info("trying to get L3OUTS")

    global DATA

    for node in DATA.keys():
        for tenant in DATA[node]["tenants"]:
            result = DATA[node]["node"].mit.polUni().fvTenant(tenant).GET(
                    **pyaci.options.subtreeClass('l3extRsEctx'))


            for l3extRsEctx in result:
                vrf = l3extRsEctx.tnFvCtxName
                l3out = l3extRsEctx.Parent.name
                
                DATA[node]["relation"][l3out] = vrf
                try:
                    DATA[node]["tenants"][tenant][vrf][l3out] = dict()
                except KeyError:
                    logging.info("could not add l3out / vrf")
                    logging.info("node: " + node)
                    logging.info("tenant: " + tenant)
                    logging.info("vrf: " + vrf)
                    logging.info("l3out: " + l3out)
                    logging.info("l3extRsEctx.Dn: " + l3extRsEctx.Dn)
                    pass

    logging.info("done getting L3OUTs")
    #logging.info("DATA:\n{data}".format(data=pformat(DATA)))
    return None

def get_ENs():
    """ Get names of L3OUTs in VRF in Tenant. """

    # Get L3OUTS
    logging.info("trying to get ENs")

    global DATA
    global BROKEN

    for n in DATA.keys():
        for t in DATA[n]["tenants"].keys():

            result = DATA[n]["node"].mit.polUni().fvTenant(t).\
                    GET(**pyaci.options.subtreeClass('l3extSubnet'))

            for external_network in result:
                
                en = external_network.Parent.name
                l3out = external_network.Parent.Parent.name
                vrf = DATA[n]["relation"][l3out]
                
                if not vrf in DATA[n]["tenants"][t].keys():
                    error = "Found a L3OUT with a VRF configured which "\
                            + "doesn't exist! Skipping..."
                    logging.error(error)
                    logging.error("EN: {e}".format(e=en))
                    logging.error("L3OUT: {l}".format(l=l3out))
                    logging.error("VRF: {v]".format(v=vrf))
                    break

                try:
                    if not en in DATA[n]["tenants"][t][vrf][l3out].keys():
                        DATA[n]["tenants"][t][vrf][l3out][en] = dict()
                        DATA[n]["tenants"][t][vrf][l3out][en]["subnets"] = list()
                except KeyError:
                    if not l3out in DATA[n]["tenants"][t][vrf].keys():
                        logging.error("ADDING l3out IN EN FUNCTION!")
                        DATA[n]["tenants"][t][vrf][l3out] = dict()
                        DATA[n]["tenants"][t][vrf][l3out][en] = dict()
                        DATA[n]["tenants"][t][vrf][l3out][en]["subnets"] = list()
                
                DATA[n]["tenants"][t][vrf][l3out][en]["subnets"].append(
                        ipaddress.ip_network(external_network.ip, strict=False))             
    
    logging.info("done getting ENs")
    #logging.info("DATA:\n{data}".format(data=pformat(DATA)))
    return None

def analyze():
    """ Analyze Data and write into BROKEN-dict """
    logging.info("Analyzing Data!")

    global STATISTICS

    default_net = ipaddress.ip_network('0.0.0.0/0')
    default6_net = ipaddress.ip_network('::/0')
    for n in DATA.keys():
        STATISTICS['nodes'] += 1
        for t in DATA[n]["tenants"].keys():
            STATISTICS['tenants'] += 1
            for vrf in DATA[n]["tenants"][t].keys():
                STATISTICS['vrfs'] += 1

                tuple_list = list()
                default_set = set()
                default6_set = set()

                for l3out in DATA[n]["tenants"][t][vrf].keys():
                    STATISTICS['l3outs'] += 1

                    for en in DATA[n]["tenants"][t][vrf][l3out].keys():
                        STATISTICS['ens'] += 1

                        for subnet in \
                                DATA[n]["tenants"][t][vrf][l3out][en] \
                                ["subnets"]:
                            STATISTICS['subnets'] += 1
                            try:
                                difference = default_net.compare_networks(
                                        subnet)
                                if difference == 0: 
                                    # if subnet = 0.0.0.0/0
                                    default_set.add(
                                            (n, t, vrf, l3out, en, subnet))
                                else:
                                    tuple_list.append(
                                        (n, t, vrf, l3out, en, subnet))

                            except TypeError:
                                # When comparing IPv4 with IPv6
                                difference = default6_net.compare_networks(
                                        subnet)
                                if difference == 0: 
                                    # if subnet = ::/0
                                    default6_set.add(
                                            (n, t, vrf, l3out, en, subnet))
                                else:
                                    tuple_list.append(
                                        (n, t, vrf, l3out, en, subnet))

                    if len(default_set) > 1:
                        temp = default_set.pop()
                        while len(default_set) > 0:
                            BROKEN.append((
                                temp, default_set.pop()))

                    if len(default6_set) > 1:
                        temp = defaul6_set.pop()
                        while len(default6_set) > 0:
                            BROKEN.append((
                                temp, default6_set.pop()))

                    combinations = itertools.combinations(tuple_list, 2)

                    for combi in combinations:
                        if combi[0][5].overlaps(combi[1][5]):
                            BROKEN.append([combi[0], combi[1]])
                            db = "Found overlap between {c0} and {c1}".format(
                                    c0=combi[0], c1=combi[1])
                            logging.debug(db)

    STATISTICS["errors"] = len(BROKEN)
    logging.info("Done Analyzing")
    return None

def summary():
    """ print a small summary with statistics """

    logging.info("print summary")

    print("ALL DONE!")
    for key in STATISTICS.keys():
        print("{k}: {v}".format(k=key, v=STATISTICS[key]))

    if not STATISTICS["subnets"] == 0:
        print("error%: {v}".format(v=(
            STATISTICS["errors"]/STATISTICS["subnets"]*100)))

    logging.info("done summarizing")
    return None

def write_excel(outfile):
    """ Write an Excel-File with relevant information"""

    # wb = Workbook, ws = Worksheet
    wb = xlsxwriter.Workbook(outfile)
    ws = wb.add_worksheet("ENs")

    ws.write('A1', "External-Network Subnet-Combinations")
    ws.write(2, 0, "Node")
    ws.write(2, 1, "Tenant")
    ws.write(2, 2, "VRF")
    ws.write(2, 3, "L3OUT")
    ws.write(2, 4, "EN A")
    ws.write(2, 5, "Subnet A")
    ws.write(2, 6, "L3OUT B")
    ws.write(2, 7, "EN B")
    ws.write(2, 8, "Subnet B")

    # Excel_row
    e_r = 3

    # b_r = BROKEN_row
    for b_r in BROKEN:
        for i in range(5):
            ws.write(e_r, i, b_r[0][i])
        ws.write(e_r, 5, b_r[0][5].with_prefixlen)
        ws.write(e_r, 6, b_r[1][3])
        ws.write(e_r, 7, b_r[1][4])
        ws.write(e_r, 8, b_r[1][5].with_prefixlen)
        e_r += 1

    ws.autofilter(2, 0, e_r, 8)

    wb.close()
    logging.info("See {outfile} for your report".format(outfile=outfile))
    return None

def main():
    """ Main function """

    global DATA

    # Parse options
    parser = argparse.ArgumentParser(description="""
    Check for double 0.0.0.0/0 and overlapping in external networks of 
    L3OUTs""")
    parser.add_argument('APIC_IP_List', type=str,
            help="A list of APIC IPs using the format:  "
            + """'["1.1.1.1","2.2.2.2"]'""")
    parser.add_argument('-l', '--loglevel', 
            help="Set loglevel. Currently implemented: " 
            + "'DEBUG', 'INFO' and 'ERROR'")
    parser.add_argument('-d', '--disablewarnings',
            help="Disable certificate warnings", action="store_true")
    parser.add_argument('-u', '--username',
            help="Your username to connect to the APIC")
    parser.add_argument('-o', '--outfile',
            help="Path to outputfile in XLSX format")

    args = parser.parse_args()

    # If needed, set loglevel
    if args.loglevel == "DEBUG":
        logging.basicConfig(level=logging.DEBUG,
                format="%(asctime)s %(levelname)s: %(message)s")
        logging.debug("DEBUG Mode enabled")
    elif args.loglevel == "INFO":
        logging.basicConfig(level=logging.INFO,
                format="%(asctime)s %(levelname)s: %(message)s")
        logging.info("INFO Mode enabled")
    elif args.loglevel == "ERROR":
        logging.basicConfig(level=logging.ERROR,
                format="%(asctime)s %(levelname)s: %(message)s")
        logging.error("ERROR Mode enabled")

    outfile = args.outfile

    # If needed, disable HTTPS warnings
    if args.disablewarnings:
        logging.info("Disabling URLLIB3 warnings")
        disable_warnings()
        logging.info("Disabling successfull")
    
    # Parse IP-List Argument
    logging.info("Parsing APIC_IP_LIST")
    ip_list = json.loads(args.APIC_IP_List)
    logging.info("Parsing successfull, APIC_IP_LIST = {list}".format(
        list=ip_list))

    # Generate apicUrls
    generate_apic_urls(ip_list)

    # Connect to APIC
    logging.info("connecting to the APIC")

    for node_url in DATA.keys():
        logging.info("creating Node-Object for {url}".format(url=node_url))
        DATA[node_url] = dict()
        DATA[node_url]["node"] = pyaci.Node(node_url)
        DATA[node_url]["relation"] = dict()

    logging.info("Nodes:\n{nodes}".format(nodes=pformat(DATA.keys())))
    
    for node in DATA:
        logging.info("Logging in to Node {node}".format(
            node=DATA[node]["node"]._url))
        password = getpass.getpass("Password for {url}".format(url=node))

        DATA[node]["node"].methods.Login(args.username, password).POST() 

    logging.info("Nodes: {nodes}".format(nodes=DATA.keys()))
    
    # Get all Tenants
    get_tenant_names()

    # Get all VRFs
    get_vrfs()

    # get L3OUTs
    get_l3outs()

    # Get External Networks
    get_ENs()

    # Analyze Data
    analyze()

    # print summary
    summary()

    # write Excel-File
    if args.outfile:
        write_excel(args.outfile)

    return 0

if __name__=="__main__":
    main()
