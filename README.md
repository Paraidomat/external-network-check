# external_network_check

Is a script to check the external networks per existing VRF on the APIC in order
to identify if the external network 0.0.0.0/0 is set more than once.

## Related information:

PyACI Documentation: https://pyaci.readthedocs.io/en/latest

## Install

- Install this into a `virtualenv` (or equivalent)
- Install everything from the `requirements.txt` into your virtualenv
- Install PyACI: https://pyaci.readthedocs.io/en/latest/user/installation.html
  - Don't forget to run the meta generation

## Usage

```
usage: external_network_check.py [-h] [-l LOGLEVEL] [-d] [-u USERNAME]
                                 [-o OUTFILE]
                                 APIC_IP_List

Check for double 0.0.0.0/0 and overlapping in external networks of L3OUTs

positional arguments:
  APIC_IP_List          A list of APIC IPs using the format:
                        '["1.1.1.1","2.2.2.2"]'

optional arguments:
  -h, --help            show this help message and exit
  -l LOGLEVEL, --loglevel LOGLEVEL
                        Set loglevel. Currently implemented: 'DEBUG', 'INFO'
                        and 'ERROR'
  -d, --disablewarnings
                        Disable certificate warnings
  -u USERNAME, --username USERNAME
                        Your username to connect to the APIC
  -o OUTFILE, --outfile OUTFILE
                        Path to outputfile in XLSX format
```
