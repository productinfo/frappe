# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.modules.export_file import export_doc
import os
import subprocess

class PackageRelease(Document):
	def set_version(self):
		# set the next patch release by default
		if not self.major:
			self.major = frappe.db.max('Package Release', 'major', dict(package=self.package))
		if not self.minor:
			self.minor = frappe.db.max('Package Release', 'minor', dict(package=self.package))
		if not self.patch:
			self.patch = frappe.db.max('Package Release', 'patch', dict(package=self.package)) + 1

	def autoname(self):
		self.set_version()
		self.name = '{}-{}.{}.{}'.format(
			frappe.db.get_value('Package', self.package, 'package_name'),
			self.major, self.minor, self.patch)

	def validate(self):
		if self.publish:
			self.export_files()

	def export_files(self):
		'''Export all the documents in this package to site/packages folder'''
		package = frappe.get_doc('Package', self.package)

		self.export_modules()
		self.export_package_files(package)
		self.make_tarfile(package)

	def export_modules(self):
		for m in frappe.db.get_all('Module Def', dict(package=self.package)):
			module = frappe.get_doc('Module Def', m.name)
			for l in module.meta.links:
				if l.link_doctype == 'Module Def':
					continue
				# all documents of the type in the module
				for d in frappe.get_all(l.link_doctype, dict(module=m.name)):
					export_doc(frappe.get_doc(l.link_doctype, d.name))

	def export_package_files(self, package):
		# write readme
		with open(frappe.get_site_path('packages', package.package_name, 'README.md'), 'w') as readme:
			readme.write(package.readme)

		# write license
		if package.license:
			with open(frappe.get_site_path('packages', package.package_name, 'LICENSE.md'), 'w') as license:
				license.write(package.license)

		# write package.json as `frappe_package.json`
		with open(frappe.get_site_path('packages', package.package_name, package.package_name + '.json'), 'w') as packagefile:
			packagefile.write(frappe.as_json(package.as_dict(no_nulls=True)))

	def make_tarfile(self, package):
		# make tarfile
		filename = '{}.tar.gz'.format(self.name)
		subprocess.check_output(['tar', 'czf', filename, package.package_name],
			cwd=frappe.get_site_path('packages'))

		# move file
		subprocess.check_output(['mv', frappe.get_site_path('packages', filename),
			frappe.get_site_path('public', 'files')])

		# make attachment
		file = frappe.get_doc(dict(
			doctype = 'File',
			file_url = '/' + os.path.join('files', filename),
			attached_to_doctype = self.doctype,
			attached_to_name = self.name
		))

		file.flags.ignore_duplicate_entry_error = True
		file.insert()
