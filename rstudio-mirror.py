#!/usr/bin/env python
from deb_pkg_tools import control
from deb_pkg_tools import repo
import errno
import json
import multiprocessing.pool
import os
import posixpath
import re
import requests
import shutil
import sys
import tempfile
import threading
import threading
import time

def inspect(path):
	info = repo.inspect_package_fields(path)
	info = dict(info)
	info.update(repo.get_packages_entry(path))
	return dict(control.unparse_control_fields(info))

def packageInfo(version, arch):
	tmpdir = tempfile.mkdtemp()
	try:
		deb = download(version, arch, tmpdir)
		return inspect(deb)
	finally:
		shutil.rmtree(tmpdir)

def getLatestVersion():
	pattern = re.compile('RStudio Desktop (\d+\.\d+\.\d+)')
	url = 'https://www.rstudio.com/products/rstudio/download/'
	doc = requests.get(url, headers = {
		'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.94 Safari/537.36'
	})
	match = pattern.search(doc.text)
	return match.group(1)

def toTuple(version):
	version = version.split('.')
	version = map(int, version)
	return tuple(version)

def vrange(v1, v2):
	major1, minor1, patch1 = toTuple(v1)
	major2, minor2, patch2 = toTuple(v2)

	for major in xrange(major1, major2 + 1):
		for minor in xrange(minor1, minor2 + 1):
			for patch in xrange(patch1 + 1, patch2 + 1):
				yield '{0}.{1}.{2}'.format(major, minor, patch)

def isValid(version):
	url = 'https://download1.rstudio.org/rstudio-{0}-i386.deb'.format(version)
	url_64 = 'https://download1.rstudio.org/rstudio-{0}-amd64.deb'.format(version)
	return requests.head(url).status_code == 200 and requests.head(url_64).status_code == 200

def download(version, arch, directory = '.'):
	name = 'rstudio-{0}-{1}.deb'.format(version, arch)
	path = os.path.join(directory, name)
	url = 'https://download1.rstudio.org/{0}'.format(name)

	with open(path, 'wb') as file:
		response = requests.get(url, stream = True)

		if not response.ok:
			return False

		for block in response.iter_content(1024):
			file.write(block)

		return path

class Application(object):

	def __init__(self, fh):
		self.__file = fh

	def export(self, arch = None, path = ''):
		data = json.load(self.__file)

		if arch:
			data = [d for d in data if d['Architecture'] in arch]

		sort_order = {
			'Package': 0,
			'Version': 1,
			'Architecture': 2,
			'Maintainer': 3,
			'Installed-Size': 4,
			'Depends': 5,
			'Recommends': 6,
			'Filename': 7,
			'Size': 8,
			'MD5sum': 9,
			'SHA1': 10,
			'SHA256': 11,
			'Section': 12,
			'Priority': 13,
			'Description': 15
		}
		sort_key = lambda f: sort_order[f] if f in sort_order else 14

		try:

			for entry in data:
				entry['Filename'] = posixpath.join(path, entry['Filename'])
				for field in sorted(entry.keys(), key = sort_key):
					sys.stdout.write('{0}: {1}\n'.format(field, entry[field]))
				sys.stdout.write('\n')

		except IOError as e:
			if errno.EPIPE == e.errno:
				return

	def update(self):
		data = json.load(self.__file)

		current_release = data[0]['Version']
		latest_release = getLatestVersion()

		if latest_release == current_release:
			sys.stdout.write('Repository is upto date\n')
			return

		pool = multiprocessing.pool.ThreadPool(4)

		versions = [v for v in vrange(current_release, latest_release)]
		versions = [v for v, p in zip(versions, pool.map(isValid, versions)) if p]

		for version in versions:
			sys.stdout.write('Adding version: {0}\n'.format(version))

			amd64 = packageInfo(version, 'amd64')
			i386 = packageInfo(version, 'i386')
			data.insert(0, amd64)
			data.insert(0, i386)

		self.__file.seek(0)
		json.dump(data, f, indent = 4, sort_keys = True)
		self.__file.truncate()
		sys.stdout.write('Repository is upto date\n')

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument('-d', '--data', type=str, default='data.json', help='repository data file')
	action_subparser = parser.add_subparsers(dest='action')
	export_parser = action_subparser.add_parser('export', help='exports the repository to stdout', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	export_parser.add_argument('--architecture', type=str, choices=['i386', 'amd64'], nargs='+', default=['i386', 'amd64'])
	export_parser.add_argument('--path', type=str, default='pool/main/r/rstudio/')
	update_parser = action_subparser.add_parser('update', help='updates the repository with the latest versions of rstudio', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	args = parser.parse_args()

	with open(args.data, 'r+') as f:
		app = Application(f)

		if 'update' == args.action:
			app.update()

		if 'export' == args.action:
			app.export(arch = args.architecture, path = args.path)
