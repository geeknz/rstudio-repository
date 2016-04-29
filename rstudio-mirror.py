#!/usr/bin/env python
from deb_pkg_tools import control
from deb_pkg_tools import repo
import gzip
import json
import os
import re
import requests
import shutil
import tempfile
import time

def toTuple(version):
	version = version.split('.')
	version = map(int, version)
	return tuple(version)

def versionRange(v1, v2):
	major1, minor1, patch1 = toTuple(v1)
	major2, minor2, patch2 = toTuple(v2)

	for major in xrange(major1, major2 + 1):
		for minor in xrange(minor1, minor2 + 1):
			for patch in xrange(patch1 + 1, patch2 + 1):
				yield '{0}.{1}.{2}'.format(major, minor, patch)

class Application(object):

	def __init__(self, fh):
		self.__file = fh

	def export(self, arch = None):
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

		with gzip.open('Packages.gz', 'wt') as f:
			for entry in data:
				entry['Filename'] = 'pool/main/r/rstudio/{0}'.format(entry['Filename'])
				for field in sorted(entry.keys(), key = sort_key):
					f.write('{0}: {1}\n'.format(field, entry[field]))
				f.write('\n')

	def update(self):
		data = json.load(self.__file)

		current_release = data[0]['Version']
		latest_release = getVersions()[0]

		print 'Current release: {0}'.format(current_release)
		print 'Latest release: {0}'.format(latest_release)

		if latest_release == current_release:
			print 'Respositry is already upto date'
			return

		for version in versionRange(current_release, latest_release):
			if isValid(version):
				print 'Adding release: {0}'.format(version)
				amd64 = packageInfo(version, True)
				i386 = packageInfo(version)
				data.insert(0, amd64)
				data.insert(0, i386)

		self.__file.seek(0)
		json.dump(data, f, indent = 4, sort_keys = True)
		self.__file.truncate()
		print 'Respositry updated'

def getVersions():
	pattern = re.compile('\((\d+\.\d+\.\d+)\)')
	url = 'https://support.rstudio.com/hc/en-us/articles/200716783-RStudio-Release-History'
	doc = requests.get('https://support.rstudio.com/hc/en-us/articles/200716783-RStudio-Release-History')
	versions = pattern.finditer(doc.text)
	versions = map(lambda v: v.groups()[0], versions)
	versions = set(versions)
	return sorted(versions, reverse = True, key = toTuple)

def isValid(version):
	url = 'https://download1.rstudio.org/rstudio-{0}-i386.deb'.format(version)
	url_64 = 'https://download1.rstudio.org/rstudio-{0}-amd64.deb'.format(version)
	return requests.head(url).status_code == 200 and requests.head(url_64).status_code == 200

def download(version, directory = '.', _64 = False):
	name = 'rstudio-{0}-{1}.deb'.format(version, ('i386', 'amd64')[_64])
	path = os.path.join(directory, name)
	url = 'https://download1.rstudio.org/{0}'.format(name)

	with open(path, 'wb') as file:
		response = requests.get(url, stream = True)

		if not response.ok:
			return False

		for block in response.iter_content(1024):
			file.write(block)

		return path

def inspect(deb):
	info = repo.inspect_package_fields(deb)
	info = dict(info)
	info.update(repo.get_packages_entry(deb))
	return dict(control.unparse_control_fields(info))

def packageInfo(version, amd64 = False):
	tmpdir = tempfile.mkdtemp()
	try:
		deb = download(version, tmpdir, amd64)
		return inspect(deb)
	finally:
		shutil.rmtree(tmpdir)

def updateData():
	with open('data.json', 'r+') as file:
		data = json.load(file)

		if len(data) < 1:
			print 'Problem with data'
			exit(1)

		latest = data[0]['Version']
		newest = getVersions()[0]

		if latest == newest:
			print 'Respositry is upto date'
			exit()

		latest = latest.split('.')
		latest = map(int, latest)
		latest = tuple(latest)
		newest = newest.split('.')
		newest = map(int, newest)
		newest = tuple(newest)

		newVersions = []
		for major in range(latest[0], newest[0] + 1):
			for minor in range(latest[1], newest[1] + 1):
				for patch in range(latest[2] + 1, newest[2] + 1):
					version = '{0}.{1}.{2}'.format(major, minor, patch)
					print 'Checking for version: {0}'.format(version)
					if isValid(version):
						print 'Found version: {0}'.format(version)
						newVersions.append(version)

		for version in newVersions:
			print 'Working on version: {0}'.format(version)
			amd64 = packageInfo(version, True)
			i386 = packageInfo(version)
			data.insert(0, amd64)
			data.insert(0, i386)

		print 'Updating data.json'
		file.seek(0)
		json.dump(data, file, indent = 4, sort_keys = True)
		file.truncate()	

def export(data):
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

	with gzip.open('Packages.gz', 'wt') as f:
		for entry in data:
			for field in sorted(entry.keys(), key = sort_key):
				f.write('{0}: {1}\n'.format(field, entry[field]))
			f.write('\n')

def writePackageFile(architecture):
	with open('data.json') as file:
		data = json.load(file)
		data = [d for d in data if d['Architecture'] == architecture]
		for d in data:
			d['Filename'] = 'pool/main/r/rstudio/{0}'.format(d['Filename'])
		export(data)

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
	action_subparser = parser.add_subparsers(dest='action')
	export_parser = action_subparser.add_parser('export', help='exports the repository as Packages.gz', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	export_parser.add_argument('--architecture', type=str, choices=['i386', 'amd64'], nargs='+', default=['i386', 'amd64'])
	export_parser.add_argument('--debroot', type=str, default='pool/main/r/rstudio/', help='')
	update_parser = action_subparser.add_parser('update', help='updates the repository with the latest versions of rstudio', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	args = parser.parse_args()

	with open('data.json', 'r+') as f:
		app = Application(f)

		if 'update' == args.action:
			app.update()

		if 'export' == args.action:
			app.export(arch = args.architecture)
