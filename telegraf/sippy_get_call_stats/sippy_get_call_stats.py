#!/usr/bin/python

#
# Script to get call stats from sippy via API 
# and DB
#
# Author Trevor Steyn <trevor@webon.co.za>

import re
import json
import requests
import xmlrpclib
import logging
import psycopg2
import argparse
from config import *

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


################ Defs Go Here #####################

def get_active_calls():
    digestTransport = HTTPSDigestTransport(CFG_API_USER, CFG_API_PASS, "XML API")
    server = xmlrpclib.ServerProxy(CFG_API_URL, transport=digestTransport)
    calls = server.listActiveCalls()
    return calls



################ Main Code Here #####################

test = get_active_calls()
print test
