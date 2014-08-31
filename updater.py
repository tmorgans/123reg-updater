import mechanize
import json
import ConfigParser
import re

from time import sleep, ctime
from urllib import urlencode, urlopen

def findRowFormByAction(formlist, action):
    form = 0
    for f in formlist:
        if f.attrs.get("action") == action:
            break
        form += 1
        
    return form
    
def validateIpAddr(ipstring):
    parts = ipstring.split('.')
    if len(parts) != 4:
        raise ValueError('Incorrect number of IP blocks. Must be four.')
        
    for b in parts:
        b_i = int(b)
        if (b_i<0) or (b_i>255):
            raise ValueError('IP Block out of range: '+b)
            
    
def printDnsEntries(entries):
    print('Found {0} DNS entries'.format(len(entries)))
    print('------------------------------')
    print('TYPE     HOST     VALUE      TTL')
    for e in entries:
        print('{0}  {1}  {2}  {3}'.format(e['type'], e['host'], e['data'], e['record_ttl']))
        
def findSubdomain(subdomain, dnsrecords):
    # This function searchs for a subdomain in DNS record JSON and returns
    # the record.
    
    for record in dnsrecords:
        if (record["host"] == subdomain) and (record['type'] == 'A'):
            return record
            
def getExternalIP():
    "http://checkip.dyndns.org/"
    site = urlopen("http://checkip.dyndns.org/").read()
    grab = re.findall('\d{2,3}.\d{2,3}.\d{2,3}.\d{2,3}', site)
    address = grab[0]
    return address
            
def updateDnsRecords(username, password, domain, hosts, ipaddr):
    # Validate IP
    validateIpAddr(ipaddr)    
    
    # Create browser instance
    br = mechanize.Browser()
    br.set_handle_robots(False)
    br.open("https://www.123-reg.co.uk/public/login")

    fid = findRowFormByAction(br.forms(), "/public/login")
        
    br.select_form(nr=fid)
    br.form['username'] = username
    br.form['password'] = password
    br.submit()
    
    # Here we switch to the 123-reg JSON interface
    # Get list of current DNS records
    response = br.open("https://www.123-reg.co.uk/secure/cpanel/manage-dns/get_dns?domain="+domain)
    jsondata = json.load(response)
    response.close()
    # Select DNS
    dnsrecords = jsondata['json']['dns']['records']
    
    #printDnsEntries(dnsrecords)
    
    for s in hosts:
        record = findSubdomain(s, dnsrecords)
        if record is not None:
            # Valid record... Submit update
            printMessage('   Updating host "'+s+'"')
            record['mx_priority'] = 0
            record['domain'] = domain
            record['record_ttl'] = ''
            record['data'] = ipaddr
            request_data = urlencode(record)         
            response = br.open("https://www.123-reg.co.uk/secure/cpanel/manage-dns/edit_dns_record", data=request_data)
            success = json.load(response)['json']['is_success']
            response.close()
            if success == 1:
                printMessage('     Success.')
            else:
                printMessage('     Error updating "'+s+'"')
        else:
            printMessage('   Matching record for "'+s+'" not found. Skipping')
                
    br.close()
    
def printMessage(message):
    print('[{0}] {1}'.format(ctime(), message))
    

if __name__ == '__main__':
    # Read configuration file
    CONFIG_PATH = '123reg-update.conf'
    
    config = ConfigParser.ConfigParser()
    config.read(CONFIG_PATH)

    username = config.get('global', 'username')
    password = config.get('global', 'password')
    domain = config.get('global', 'domain')
    subdoms = config.get('global', 'subdomains').split(',')
    interval = config.getint('global', 'interval_hours')*3600
    
    last_ip = config.get('cache', 'lastip')

    while True:
        # Check lastip to current
        external_ip = getExternalIP()
        if external_ip != last_ip:
            printMessage('New IP address! Updating...')
            updateDnsRecords(username, password, domain, subdoms, external_ip)
            
            # Update cache
            last_ip = external_ip
            config.set('cache', 'lastip', external_ip)
            with open(CONFIG_PATH, 'w') as h:
                config.write(h)
        else:
            printMessage('IP not changed.')
            
        sleep(interval)
    
    