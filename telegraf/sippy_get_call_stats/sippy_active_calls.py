#!/usr/bin/python

#
# Script to get call stats from sippy via API 
# and DB
#
# Author Trevor Steyn <trevor@webon.co.za>

import os
#os.environ["PYTHONHTTPSVERIFY"] = "0"
import re
import json
import requests
import xmlrpclib
import logging
import psycopg2
import argparse

# Fix for http digest auth

class HTTPSDigestTransport(xmlrpclib.SafeTransport):
    """
    Transport that uses urllib2 so that we can do Digest authentication.
    
    Based upon code at http://bytes.com/topic/python/answers/509382-solution-xml-rpc-over-proxy
    """

    def __init__(self, username, pw, realm, verbose = None, use_datetime=0):
        self.__username = username
        self.__pw = pw
        self.__realm = realm
        self.verbose = verbose
        self._use_datetime = use_datetime

    def request(self, host, handler, request_body, verbose):
        import urllib2

        url = 'https://'+host+handler
        if verbose or self.verbose:
            print "ProxyTransport URL: [%s]"%url

        request = urllib2.Request(url)
        request.add_data(request_body)
        # Note: 'Host' and 'Content-Length' are added automatically
        request.add_header("User-Agent", self.user_agent)
        request.add_header("Content-Type", "text/xml") # Important

        # setup digest authentication
        authhandler = urllib2.HTTPDigestAuthHandler()
        authhandler.add_password(self.__realm, url, self.__username, self.__pw)
        opener = urllib2.build_opener(authhandler)

        # proxy_handler = urllib2.ProxyHandler()
        # opener = urllib2.build_opener(proxy_handler)
        f = opener.open(request)
        return(self.parse_response(f))


def get_active_calls():
	digestTransport = HTTPSDigestTransport(CFG_API_USER, CFG_API_PASS, "XML API")
	server = xmlrpclib.ServerProxy(CFG_API_URL, transport=digestTransport)
	calls = server.listActiveCalls()
	return calls

def get_sippy_info():

	'''
		This function will get all info
		customer names, account descriptions
		vendor names as well as connections
	'''
	info 		    = {}
	info['vendor'] 	    = {}
	info['customer']    = {}
	info['account']     = {}

	vendor_query = '''
		SELECT a.i_connection, a.name, b.name as vendor 
		FROM connections a 
		INNER JOIN vendors b 
			ON a.i_vendor=b.i_vendor 
		WHERE a.i_vendor is not NULL
	'''

	customer_query = '''
		SELECT i_customer,i_wholesaler,name
		FROM customers;
	'''

	account_query = 'SELECT i_account,' + CFG_ACC_FIELD + ',i_customer from Accounts'
	
	conn = psycopg2.connect("dbname=%s user='%s' host='%s' password='%s'" % (CFG_DB_NAME,CFG_DB_USER,CFG_DB_HOST,CFG_DB_PASS))
	cur = conn.cursor()
	cur.execute(vendor_query)
	for record in cur:
		i_connection = int(record[0])
		info['vendor'][i_connection]    		= {}
		info['vendor'][i_connection]['name']		= record[1]
		info['vendor'][i_connection]['vendor_name'] 	= record[2]

	cur.execute(customer_query)
	for record in cur:
		i_customer = str(int(record[0]))
		info['customer'][i_customer] 			= {}
		info['customer'][i_customer]['i_wholesaler']	= str(int(record[1]))
		info['customer'][i_customer]['name']		= record[2]

	cur.execute(account_query)
	for record in cur:
		i_account = str(int(record[0]))
		info['account'][i_account] 			= {}
		info['account'][i_account]['name'] 		= record[1]
		info['account'][i_account]['i_customer']	= str(int(record[2]))

	return info

# Config

CFG_DB_HOST     = '127.0.0.1'
CFG_DB_PORT     = '5432'
CFG_DB_USER     = 'USERNAME'
CFG_DB_PASS     = 'PASSWORD'
CFG_DB_NAME     = 'sippy'

# API Setting

CFG_API_URL     = 'https://127.0.0.1/xmlapi/xmlapi'
CFG_API_USER    = 'API_USER'
CFG_API_PASS    = 'API_PASS'

# Preference for Account

CFG_ACC_FIELD   = 'username'

#### Main Code here ####	

sippy_info = get_sippy_info()
calls = get_active_calls()


CUSTOMER_STATS 	= {}
VENDOR_STATS 	= {}

#print sippy_info
#print json.dumps(calls, indent=4, sort_keys=True)

for call in calls:
	if call['I_CONNECTION'] in sippy_info['vendor'] and call['I_CONNECTION'] != 1:
		direction = 'OUT'
		i_connection = call['I_CONNECTION']
		vendor_name = sippy_info['vendor'][i_connection]['vendor_name'].upper()
		vendor_name = vendor_name.replace(" ","_")
		connection_name = sippy_info['vendor'][i_connection]['name'].upper()
		connection_name = connection_name.replace(" ","_")
		if vendor_name not in VENDOR_STATS:
			VENDOR_STATS[vendor_name] = {}
		if connection_name not in VENDOR_STATS[vendor_name]:
			VENDOR_STATS[vendor_name][connection_name] = {}
			VENDOR_STATS[vendor_name][connection_name]['ROUTING'] = 0
			VENDOR_STATS[vendor_name][connection_name]['CONNECTED'] = 0
		if call['CC_STATE'] == 'Connected':
			VENDOR_STATS[vendor_name][connection_name]['CONNECTED'] = VENDOR_STATS[vendor_name][connection_name]['CONNECTED'] + 1
		elif call['CC_STATE'] == 'ARComplete':
			VENDOR_STATS[vendor_name][connection_name]['ROUTING'] = VENDOR_STATS[vendor_name][connection_name]['ROUTING'] + 1
	else:
		direction = 'IN'
	i_account = str(call['I_ACCOUNT'])
	i_customer = sippy_info['account'][i_account]['i_customer']
	acc_name = sippy_info['account'][i_account]['name'].upper()
	acc_name = acc_name.replace(" ","_")
	if acc_name == '':
		acc_name == 'ORPHANED_ACCOUNT'
	account_name =  'acc:' + acc_name
	if i_customer not in CUSTOMER_STATS:
		CUSTOMER_STATS[i_customer] = {}
	if account_name not in CUSTOMER_STATS[i_customer]:
		CUSTOMER_STATS[i_customer][account_name] = {}
		CUSTOMER_STATS[i_customer][account_name]['ROUTING'] = {}
		CUSTOMER_STATS[i_customer][account_name]['CONNECTED'] = {}
		CUSTOMER_STATS[i_customer][account_name]['ROUTING']['IN'] = 0
		CUSTOMER_STATS[i_customer][account_name]['ROUTING']['OUT'] = 0
		CUSTOMER_STATS[i_customer][account_name]['CONNECTED']['IN'] = 0
		CUSTOMER_STATS[i_customer][account_name]['CONNECTED']['OUT'] = 0
	if call['CC_STATE'] == 'Connected':
		CUSTOMER_STATS[i_customer][account_name]['CONNECTED'][direction] = CUSTOMER_STATS[i_customer][account_name]['CONNECTED'][direction] + 1
	elif call['CC_STATE'] == 'ARComplete':
		CUSTOMER_STATS[i_customer][account_name]['ROUTING'][direction] = CUSTOMER_STATS[i_customer][account_name]['ROUTING'][direction] + 1
	while i_customer != '1':
		i_parent = sippy_info['customer'][i_customer]['i_wholesaler']
		account_name = 'cust:' + sippy_info['customer'][i_customer]['name'].upper()
		account_name = account_name.replace(" ","_")
		if i_parent not in CUSTOMER_STATS:
			CUSTOMER_STATS[i_parent] = {}
		if account_name not in CUSTOMER_STATS[i_parent]:
			CUSTOMER_STATS[i_parent][account_name] = {}
			CUSTOMER_STATS[i_parent][account_name]['ROUTING'] = {}
			CUSTOMER_STATS[i_parent][account_name]['CONNECTED'] = {}
			CUSTOMER_STATS[i_parent][account_name]['ROUTING']['IN'] = 0
			CUSTOMER_STATS[i_parent][account_name]['ROUTING']['OUT'] = 0
			CUSTOMER_STATS[i_parent][account_name]['CONNECTED']['IN'] = 0
			CUSTOMER_STATS[i_parent][account_name]['CONNECTED']['OUT'] = 0
		if call['CC_STATE'] == 'Connected':
			CUSTOMER_STATS[i_parent][account_name]['CONNECTED'][direction] = CUSTOMER_STATS[i_parent][account_name]['CONNECTED'][direction] + 1
		elif call['CC_STATE'] == 'ARComplete':
			CUSTOMER_STATS[i_parent][account_name]['ROUTING'][direction] = CUSTOMER_STATS[i_parent][account_name]['ROUTING'][direction] + 1
		i_customer = i_parent
		
for i_customer in CUSTOMER_STATS:
	customer_name = sippy_info['customer'][i_customer]['name'].upper()
	customer_name = customer_name.replace(" ","_")
	for account in CUSTOMER_STATS[i_customer]:
		routing_in 		= CUSTOMER_STATS[i_customer][account]['ROUTING']['IN']
		routing_out 	= CUSTOMER_STATS[i_customer][account]['ROUTING']['OUT']
		connected_in 	= CUSTOMER_STATS[i_customer][account]['CONNECTED']['IN']
		connected_out 	= CUSTOMER_STATS[i_customer][account]['CONNECTED']['OUT']
		print 'customer_calls,customer=%s,account=%s connected_in=%s,routing_in=%s,connected_out=%s,routing_out=%s' %(customer_name,account,connected_in,routing_in,connected_out,routing_out)

for vendor in VENDOR_STATS:
	vendor = vendor.upper()
	vendor = vendor.replace(" ","_")
	for connection in VENDOR_STATS[vendor]:
		connection  = connection.upper()
		connection  = connection.replace(" ","_")
		connected 	= VENDOR_STATS[vendor][connection]['CONNECTED']
		routing 	= VENDOR_STATS[vendor][connection]['ROUTING']
		print 'vendor_calls,vendor=%s,connection=%s connected=%s,routing=%s' %(vendor,connection,connected,routing)
