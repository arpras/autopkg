#!/usr/bin/python
#
# Copyright 2014 Timothy Sutton
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Routines for working with the GitHub API"""

import json
import os
import sys
import urllib2

from base64 import b64encode
from getpass import getpass
from pprint import pprint

BASE_URL = "https://api.github.com"
TOKEN_LOCATION = os.path.expanduser("~/.autopkg_gh_token")


class RequestWithMethod(urllib2.Request):
    """Custom Request class that can accept arbitrary methods besides
    GET/POST"""
    # http://benjamin.smedbergs.us/blog/2008-10-21/
    #        putting-and-deleteing-in-python-urllib2/
    def __init__(self, method, *args, **kwargs):
        self._method = method
        urllib2.Request.__init__(self, *args, **kwargs)

    def get_method(self):
        return self._method


class GitHubSession(object):
    """Handles a session with the GitHub API"""
    def __init__(self):
        self.token = None

    def setup_token(self):
        """Return a GitHub OAuth token string. Will create one if necessary.
        The string will be stored in TOKEN_LOCATION and used again
        if it exists."""

        #TODO: - support defining alternate scopes
        #      - deal with case of an existing token with the same note
        if not os.path.exists(TOKEN_LOCATION):
            print """You will now be asked to enter credentials to a GitHub
account in order to create an API token. This token has only
a 'public' scope, meaning it cannot be used to retrieve
personal information from your account, or push to any repos
you may have access to. You can verify this token within your
profile page at https://github.com/settings/tokens and
revoke it at any time. This token will be stored in your user's
home folder at %s.""" % TOKEN_LOCATION
            username = raw_input("Username: ")
            password = getpass("Password: ")
            auth = b64encode(username + ":" + password)

            # https://developer.github.com/v3/oauth/#scopes
            req = urllib2.Request(BASE_URL + "/authorizations")
            req.add_header("Authorization", "Basic %s" % auth)
            json_resp = urllib2.urlopen(req)
            data = json.load(json_resp)

            req_post = {"note": "AutoPkg CLI"}
            req_json = json.dumps(req_post)
            create_resp = urllib2.urlopen(req, req_json)
            data = json.load(create_resp)

            token = data["token"]
            try:
                with open(TOKEN_LOCATION, "w") as tokenf:
                    tokenf.write(token)
                os.chmod(TOKEN_LOCATION, 0600)
            except IOError as err:
                print >> sys.stderr, (
                    "Couldn't write token file at %s! Error: %s"
                    % (TOKEN_LOCATION, err))
        else:
            try:
                with open(TOKEN_LOCATION, "r") as tokenf:
                    token = tokenf.read()
            except IOError as err:
                print >> sys.stderr, (
                    "Couldn't read token file at %s! Error: %s"
                    % (TOKEN_LOCATION, err))

            # TODO: validate token given we found one but haven't checked its
            # auth status

        self.token = token


    def call_api(self, endpoint, method="GET", query=None, data=None,
                 headers=None, accept="application/vnd.github.v3+json"):
        """Return a tuple of a serialized JSON response and HTTP status code
        from a call to a GitHub API endpoint. Certain APIs return no JSON
        result and so the first item in the tuple (the response) will be None.

        endpoint: REST endpoint, beginning with a forward-slash
        method: optional alternate HTTP method to use other than GET
        query: optional additional query to include with URI (passed directly)
        data: optional dict that will be sent as JSON with request
        headers: optional dict of additional headers to send with request
        accept: optional Accept media type for exceptional APIs (like release
                assets)."""

        url = BASE_URL + endpoint
        if query:
            url += "?" + query
        if data:
            data = json.dumps(data)

        # Setup custom request and its headers
        req = RequestWithMethod(method, url)
        req.add_header("User-Agent", "AutoPkg")
        req.add_header("Accept", accept)
        if self.token:
            req.add_header("Authorization", "token %s" % self.token)
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)

        try:
            urlfd = urllib2.urlopen(req, data=data)
            status = urlfd.getcode()
            response = urlfd.read()
            if response:
                resp_data = json.loads(response)
            else:
                resp_data = None
        except urllib2.HTTPError as err:
            status = err.code
            print >> sys.stderr, "API error: %s" % err
            try:
                error_json = json.loads(err.read())
                resp_data = error_json
            except BaseException:
                print >> sys.stderr, err.read()
                resp_data = None
        except urllib2.URLError as err:
            print >> sys.stderr, "Error opening URL: %s" % url
            print >> sys.stderr, err.reason
            (resp_data, status) = (None, None)

        return (resp_data, status)
