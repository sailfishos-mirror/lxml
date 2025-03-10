"""
Web IO test cases (wsgiref)
"""


import unittest
import textwrap
import sys
import gzip

from .common_imports import etree, HelperTestCase, BytesIO, _bytes
from .dummy_http_server import webserver, HTTPRequestCollector


def needs_http(test_method, _skip_when_called=unittest.skip("needs HTTP support in libxml2")):
    if "http" in etree.LIBXML_FEATURES:
        return test_method
    return _skip_when_called(test_method)


class HttpIOTestCase(HelperTestCase):
    etree = etree

    def _parse_from_http(self, data, code=200, headers=None):
        parser = self.etree.XMLParser(no_network=False)
        handler = HTTPRequestCollector(data, code, headers)
        with webserver(handler) as host_url:
            tree = self.etree.parse(host_url + 'TEST', parser=parser)
        self.assertEqual([('/TEST', [])], handler.requests)
        return tree

    @needs_http
    def test_http_client(self):
        tree = self._parse_from_http(b'<root><a/></root>')
        self.assertEqual('root', tree.getroot().tag)
        self.assertEqual('a', tree.getroot()[0].tag)

    @needs_http
    def test_http_client_404(self):
        try:
            self._parse_from_http(b'<root/>', code=404)
        except OSError:
            self.assertTrue(True)
        else:
            self.assertTrue(False, "expected IOError")

    @needs_http
    def test_http_client_gzip(self):
        f = BytesIO()
        gz = gzip.GzipFile(fileobj=f, mode='w', filename='test.xml')
        gz.write(b'<root><a/></root>')
        gz.close()
        data = f.getvalue()
        del f, gz

        headers = [('Content-Encoding', 'gzip')]
        tree = self._parse_from_http(data, headers=headers)
        self.assertEqual('root', tree.getroot().tag)
        self.assertEqual('a', tree.getroot()[0].tag)

    @needs_http
    def test_parser_input_mix(self):
        data = b'<root><a/></root>'
        handler = HTTPRequestCollector(data)
        parser = self.etree.XMLParser(no_network=False)

        with webserver(handler) as host_url:
            tree = self.etree.parse(host_url, parser=parser)
            root = tree.getroot()
            self.assertEqual('a', root[0].tag)

            root = self.etree.fromstring(data)
            self.assertEqual('a', root[0].tag)

            tree = self.etree.parse(host_url, parser=parser)
            root = tree.getroot()
            self.assertEqual('a', root[0].tag)

            root = self.etree.fromstring(data)
            self.assertEqual('a', root[0].tag)

        root = self.etree.fromstring(data)
        self.assertEqual('a', root[0].tag)

    @needs_http
    def test_network_dtd(self):
        data = [_bytes(textwrap.dedent(s)) for s in [
            # XML file
            '''\
            <?xml version="1.0"?>
            <!DOCTYPE root SYSTEM "./file.dtd">
            <root>&myentity;</root>
            ''',
            # DTD
            '<!ENTITY myentity "DEFINED">',
        ]]

        responses = []
        def handler(environ, start_response):
            start_response('200 OK', [])
            return [responses.pop()]

        with webserver(handler) as host_url:
            # DTD network loading enabled
            responses = data[::-1]
            tree = self.etree.parse(
                host_url + 'dir/test.xml',
                parser=self.etree.XMLParser(
                    load_dtd=True, no_network=False))
            self.assertFalse(responses)  # all read
            root = tree.getroot()
            self.assertEqual('DEFINED', root.text)

            # DTD network loading disabled
            responses = data[::-1]
            try:
                self.etree.parse(
                    host_url + 'dir/test.xml',
                    parser=self.etree.XMLParser(
                        load_dtd=True, no_network=True))
            except self.etree.XMLSyntaxError:
                self.assertTrue("myentity" in str(sys.exc_info()[1]))
                self.assertEqual(1, len(responses))  # DTD not read
            except OSError:
                self.assertTrue("failed to load" in str(sys.exc_info()[1]))
                self.assertEqual(2, len(responses))  # nothing read
            else:
                self.assertTrue(False)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTests([unittest.defaultTestLoader.loadTestsFromTestCase(HttpIOTestCase)])
    return suite


if __name__ == '__main__':
    print('to test use test.py %s' % __file__)
