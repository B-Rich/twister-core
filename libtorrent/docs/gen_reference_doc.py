import glob
import os
import sys

paths = ['include/libtorrent/*.hpp', 'include/libtorrent/kademlia/*.hpp', 'include/libtorrent/extensions/*.hpp']

files = []

for p in paths:
	files.extend(glob.glob(os.path.join('..', p)))

functions = []
classes = []
enums = []

# maps filename to overview description
overviews = {}

# maps names -> URL
symbols = {}

verbose = '--verbose' in sys.argv
dump = '--dump' in sys.argv
internal = '--internal' in sys.argv

category_mapping = {
	'error_code.hpp': 'Error Codes',
	'file.hpp': 'File',
	'storage.hpp': 'Storage',
	'storage_defs.hpp': 'Storage',
	'file_storage.hpp': 'Storage',
	'file_pool.hpp': 'Storage',
	'extensions.hpp': 'Plugins',
	'ut_metadata.hpp': 'Plugins',
	'ut_pex.hpp': 'Plugins',
	'ut_trackers.hpp': 'Plugins',
	'metadata_transfer.hpp': 'Plugins',
	'smart_ban.hpp': 'Plugins',
	'lt_trackers.hpp': 'Plugins',
	'create_torrent.hpp': 'Create Torrents',
	'alert.hpp': 'Alerts',
	'alert_types.hpp': 'Alerts',
	'bencode.hpp': 'Bencoding',
	'lazy_entry.hpp': 'Bencoding',
	'entry.hpp': 'Bencoding',
	'time.hpp': 'Time',
	'ptime.hpp': 'Time',
	'escape_string.hpp': 'String',
	'string_util.hpp': 'String',
	'utf8.hpp': 'String',
	'enum_net.hpp': 'Network',
	'broadcast_socket.hpp': 'Network',
	'socket.hpp': 'Network',
	'socket_io.hpp': 'Network',
	'rss.hpp': 'RSS',
	'bitfield.hpp': 'Utility',
	'peer_id.hpp': 'Utility',
	'identify_client.hpp': 'Utility',
	'thread.hpp': 'Utility',
	'ip_filter.hpp': 'Filter',
}

def categorize_symbol(name, filename):
	f = os.path.split(filename)[1]
	if f in category_mapping:
		return category_mapping[f]

	if name.endswith('_category') \
		or name.endswith('_error_code') \
		or name.endswith('error_code_enum'):
		return 'Error Codes'

	return 'Core'

def first_item(itr):
	for i in itr:
		return i
	return None

def is_visible(desc):
	if desc.strip() == 'internal': return False
	if desc.strip() == 'hidden': return False
	return True

def highlight_signature(s):
	name = s.split('(')
	name2 = name[0].split(' ')
	name2[-1] = '**' + name2[-1] + '** '
	name[0] = ' '.join(name2)
	return '('.join(name)

def html_sanitize(s):
	ret = ''
	for i in s:
		if i == '<': ret += '&lt;'
		elif i == '>': ret += '&gt;'
		elif i == '&': ret += '&amp;'
		else: ret += i
	return ret

def looks_like_variable(line):
	line = line.strip()
	if not line.endswith(';'): return False
	if not ' ' in line and not '\t' in line: return False
	if line.startswith('friend '): return False
	if line.startswith('enum '): return False
	if line.startswith(','): return False
	if line.startswith(':'): return False
	return True

def looks_like_function(line):
	if '::' in line.split('(')[0].split(' ')[-1]: return False
	if line.startswith(','): return False
	if line.startswith(':'): return False
	return '(' in line;

def parse_function(lno, lines, filename):
	current_fun = {}

	start_paren = 0
	end_paren = 0
	signature = ''

	while lno < len(lines):
		l = lines[lno].strip()
		lno += 1
		if l.startswith('//'): continue

		start_paren += l.count('(')
		end_paren += l.count(')')

		sig_line = l.replace('TORRENT_EXPORT ', '').strip()
		if signature != '': sig_line = '\n   ' + sig_line
		signature += sig_line
		if verbose: print 'fun     %s' % l

		if start_paren > 0 and start_paren == end_paren:
			if signature[-1] != ';':
				# we also need to consume the function body
				start_paren = 0
				end_paren = 0
				for i in range(len(signature)):
					if signature[i] == '(': start_paren += 1
					elif signature[i] == ')': end_paren += 1

					if start_paren > 0 and start_paren == end_paren:
						for k in range(i, len(signature)):
							if signature[k] == ':' or signature[k] == '{':
								signature = signature[0:k].strip()
								break
						break

				lno = consume_block(lno - 1, lines)
				signature += ';'
			return [{ 'file': filename[11:], 'signatures': set([ signature ]), 'names': set([ signature.split('(')[0].split(' ')[-1].strip()])}, lno]
	if len(signature) > 0:
		print '\x1b[31mFAILED TO PARSE FUNCTION\x1b[0m %s\nline: %d\nfile: %s' % (signature, lno, filename)
	return [None, lno]

def parse_class(lno, lines, filename):
	start_brace = 0
	end_brace = 0

	name = ''
	funs = []
	fields = []
	enums = []
	state = 'public'
	context = ''
	class_type = 'struct'
	blanks = 0

	while lno < len(lines):
		l = lines[lno].strip()
		name += lines[lno].replace('TORRENT_EXPORT ', '').split('{')[0].strip()
		if '{' in l: break
		if verbose: print 'class  %s' % l
		lno += 1

	if name.startswith('class'):
		state = 'private'
		class_type = 'class'

	while lno < len(lines):
		l = lines[lno].strip()
		lno += 1

		if l == '':
			blanks += 1
			context = ''
			continue

		if l.startswith('/*'):
			lno = consume_comment(lno - 1, lines)
			continue

		if l.startswith('#'):
			lno = consume_ifdef(lno - 1, lines)
			continue

		if 'TORRENT_DEFINE_ALERT' in l:
			if verbose: print 'xx    %s' % l
			blanks += 1
			continue
		if 'TORRENT_DEPRECATED' in l:
			if verbose: print 'xx    %s' % l
			blanks += 1
			continue

		if l.startswith('//'):
			if verbose: print 'desc  %s' % l
			l = l.split('//')[1]
			if len(l) and l[0] == ' ': l = l[1:]
			context += l + '\n'
			continue

		start_brace += l.count('{')
		end_brace += l.count('}')

		if l == 'private:': state = 'private'
		elif l == 'protected:': state = 'protected'
		elif l == 'public:': state = 'public'

		if start_brace > 0 and start_brace == end_brace:
			return [{ 'file': filename[11:], 'enums': enums, 'fields':fields, 'type': class_type, 'name': name.split(':')[0].replace('class ', '').replace('struct ', '').strip(), 'decl': name, 'fun': funs}, lno]

		if state != 'public' and not internal:
			if verbose: print 'private %s' % l
			blanks += 1
			continue

		if start_brace - end_brace > 1:
			if verbose: print 'scope   %s' % l
			blanks += 1
			continue;

		if looks_like_function(l):
			current_fun, lno = parse_function(lno - 1, lines, filename)
			if current_fun != None and is_visible(context):
				if context == '' and blanks == 0 and len(funs):
					funs[-1]['signatures'].update(current_fun['signatures'])
					funs[-1]['names'].update(current_fun['names'])
				else:
					current_fun['desc'] = context
					funs.append(current_fun)
			context = ''
			blanks = 0
			continue

		if looks_like_variable(l):
			if not is_visible(context):
				context = ''
				continue
			n = l.split(' ')[-1].split(':')[0].split(';')[0]
			if context == '' and blanks == 0 and len(fields):
				fields[-1]['names'].append(n)
				fields[-1]['signatures'].append(l)
			else:
				fields.append({'signatures': [l], 'names': [n], 'desc': context})
			context = ''
			blanks = 0
			continue

		if l.startswith('enum '):
			enum, lno = parse_enum(lno - 1, lines, filename)
			if enum != None and is_visible(context):
				enum['desc'] = context
				enums.append(enum)
			context = ''
			continue

		context = ''
		if verbose: print '??      %s' % l
   
	if len(name) > 0:
		print '\x1b[31mFAILED TO PARSE CLASS\x1b[0m %s\nfile: %s:%d' % (name, filename, lno)
	return [None, lno]

def parse_enum(lno, lines, filename):
	start_brace = 0
	end_brace = 0

	l = lines[lno].strip()
	name = l.replace('enum ', '').split('{')[0].strip()
	if len(name) == 0:
		print 'WARNING: anonymous enum at: %s:%d' % (filename, lno)
		lno = consume_block(lno - 1, lines)
		return [None, lno]

	values = []
	context = ''
	if not '{' in l:
		if verbose: print 'enum  %s' % lines[lno]
		lno += 1

	while lno < len(lines):
		l = lines[lno].strip()
		lno += 1

		if l.startswith('//'):
			if verbose: print 'desc  %s' % l
			l = l.split('//')[1]
			if len(l) and l[0] == ' ': l = l[1:]
			context += l + '\n'
			continue

		if l.startswith('#'):
			lno = consume_ifdef(lno - 1, lines)
			continue

		start_brace += l.count('{')
		end_brace += l.count('}')

		if '{' in l: 
			l = l.split('{')[1]
		l = l.split('}')[0]

		if len(l):
			if verbose: print 'enumv %s' % lines[lno-1]
			for v in l.split(','):
				if v == '': continue
				if is_visible(context):
					values.append({'name': v.strip(), 'desc': context})
				context = ''
		else:
			if verbose: print '??    %s' % lines[lno-1]

		if start_brace > 0 and start_brace == end_brace:
			return [{'file': filename[11:], 'name': name, 'values': values}, lno]

	if len(name) > 0:
		print '\x1b[31mFAILED TO PARSE ENUM\x1b[0m %s\nline: %d\nfile: %s' % (name, lno, filename)
	return [None, lno]

def consume_block(lno, lines):
	start_brace = 0
	end_brace = 0

	while lno < len(lines):
		l = lines[lno].strip()
		if verbose: print 'xx    %s' % l
		lno += 1

		start_brace += l.count('{')
		end_brace += l.count('}')

		if start_brace > 0 and start_brace == end_brace:
			break
	return lno

def consume_comment(lno, lines):
	while lno < len(lines):
		l = lines[lno].strip()
		if verbose: print 'xx    %s' % l
		lno += 1
		if '*/' in l: break

	return lno

def consume_ifdef(lno, lines):
	l = lines[lno].strip()
	lno += 1

	start_if = 1
	end_if = 0

	if verbose: print 'prep  %s' % l

	if l == '#ifndef TORRENT_NO_DEPRECATE' or \
		l == '#ifdef TORRENT_DEBUG' or \
		l == '#ifdef TORRENT_ASIO_DEBUGGING' or \
		(l.startswith('#if') and 'defined TORRENT_DEBUG' in l) or \
		(l.startswith('#if') and 'defined TORRENT_ASIO_DEBUGGING' in l):
		while lno < len(lines):
			l = lines[lno].strip()
			lno += 1
			if verbose: print 'prep  %s' % l
			if l.startswith('#endif'): end_if += 1
			if l.startswith('#if'): start_if += 1
			if l == '#else' and start_if - end_if == 1: break
			if start_if - end_if == 0: break
		return lno

	return lno

for filename in files:
	h = open(filename)
	lines = h.read().split('\n')

	if verbose: print '\n=== %s ===\n' % filename

	blanks = 0
	lno = 0
	while lno < len(lines):
		l = lines[lno].strip()
		lno += 1

		if l == '':
			blanks += 1
			context = ''
			continue

		if l.startswith('//') and l[2:].strip() == 'OVERVIEW':
			# this is a section overview
			current_overview = ''
			while lno < len(lines):
				l = lines[lno].strip()
				lno += 1
				if not l.startswith('//'):
					# end of overview
					overviews[filename[11:]] = current_overview
					current_overview = ''
					break
				current_overview += l[2:] + '\n'

		if l.startswith('//'):
			if verbose: print 'desc  %s' % l
			l = l.split('//')[1]
			if len(l) and l[0] == ' ': l = l[1:]
			context += l + '\n'
			continue

		if l.startswith('/*'):
			lno = consume_comment(lno - 1, lines)
			continue

		if l.startswith('#'):
			lno = consume_ifdef(lno - 1, lines)
			continue

		if l == 'namespace detail' or \
			l == 'namespace aux':
			lno = consume_block(lno, lines)
			continue

		if 'TORRENT_CFG' in l:
			blanks += 1
			if verbose: print 'xx    %s' % l
			continue
		if 'TORRENT_DEPRECATED' in l:
			blanks += 1
			if verbose: print 'xx    %s' % l
			continue

		if 'TORRENT_EXPORT ' in l or l.startswith('inline '):
			if 'class ' in l or 'struct ' in l:
				current_class, lno = parse_class(lno -1, lines, filename)
				if current_class != None and is_visible(context):
					current_class['desc'] = context
					classes.append(current_class)
				context = ''
				blanks += 1
				continue

			if looks_like_function(l):
				current_fun, lno = parse_function(lno - 1, lines, filename)
				if current_fun != None and is_visible(context):
					if context == '' and blanks == 0 and len(functions):
						functions[-1]['signatures'].update(current_fun['signatures'])
						functions[-1]['names'].update(current_fun['names'])
					else:
						current_fun['desc'] = context
						functions.append(current_fun)
					blanks = 0
				context = ''
				continue

		if ('class ' in l or 'struct ' in l) and not ';' in l:
			lno = consume_block(lno - 1, lines)
			context = ''
			blanks += 1
			continue

		if l.startswith('enum '):
			current_enum, lno = parse_enum(lno - 1, lines, filename)
			if current_enum != None and is_visible(context):
				current_enum['desc'] = context
				enums.append(current_enum)
			context = ''
			blanks += 1
			continue

		blanks += 1
		if verbose: print '??    %s' % l

		context = ''
	h.close()

if dump:

	if verbose: print '\n===============================\n'

	for c in classes:
		print '\x1b[4m%s\x1b[0m %s\n{' % (c['type'], c['name'])
		for f in c['fun']:
			for s in f['signatures']:
				print '   %s' % s.replace('\n', '\n   ')

		if len(c['fun']) > 0 and len(c['fields']) > 0: print ''

		for f in c['fields']:
			for s in f['signatures']:
				print '   %s' % s

		if len(c['fields']) > 0 and len(c['enums']) > 0: print ''

		for e in c['enums']:
			print '   \x1b[4menum\x1b[0m %s\n   {' % e['name']
			for v in e['values']:
				print '      %s' % v['name']
			print '   };'
		print '};\n'

	for f in functions:
		print '%s' % f['signature']

	for e in enums:
		print '\x1b[4menum\x1b[0m %s\n{' % e['name']
		for v in e['values']:
			print '   %s' % v['name']
		print '};'

categories = {}

for c in classes:
	cat = categorize_symbol(c['name'], c['file'])
	if not cat in categories:
		categories[cat] = { 'classes': [], 'functions': [], 'enums': [], 'filename': 'reference-%s.rst' % cat.replace(' ', '_')}

	if c['file'] in overviews:
		categories[cat]['overview'] = overviews[c['file']]

	categories[cat]['classes'].append(c)
	symbols[c['name']] = categories[cat]['filename'].replace('.rst', '.html') + '#' + c['name']

for f in functions:
	cat = categorize_symbol(first_item(f['names']), f['file'])
	if not cat in categories:
		categories[cat] = { 'classes': [], 'functions': [], 'enums': [], 'filename': 'reference-%s.rst' % cat.replace(' ', '_')}

	if f['file'] in overviews:
		categories[cat]['overview'] = overviews[f['file']]

	for n in f['names']:
		symbols[n] = categories[cat]['filename'].replace('.rst', '.html') + '#' + n
	categories[cat]['functions'].append(f)

for e in enums:
	cat = categorize_symbol(e['name'], e['file'])
	if not cat in categories:
		categories[cat] = { 'classes': [], 'functions': [], 'enums': [], 'filename': 'reference-%s.rst' % cat.replace(' ', '_')}
	categories[cat]['enums'].append(e)
	symbols[e['name']] = categories[cat]['filename'].replace('.rst', '.html') + '#' + e['name']

def print_declared_in(out, o):
	out.write('Declared in "%s"\n\n' % print_link(o['file'], '../include/%s' % o['file']))

link_targets = []

def print_link(name, target):
	global link_targets
	link_targets.append(target)
	return "`%s`__" % name

def dump_link_targets():
	global link_targets
	ret = ''
	for l in link_targets:
		ret += '__ %s\n' % l
	link_targets = []
	return ret

def heading(string, c):
	return '\n' + string + '\n' + (c * len(string)) + '\n'

out = open('reference.rst', 'w+')
out.write('''==================================
libtorrent reference documentation
==================================

.. raw:: html

	<div style="column-count: 4; -webkit-column-count: 4; -moz-column-count: 4">

''')

for cat in categories:
	print >>out, '%s' % heading(cat, '-')

	category_filename = categories[cat]['filename'].replace('.rst', '.html')
	for c in categories[cat]['classes']:
		print >>out, '| ' + print_link(c['name'], symbols[c['name']])
	for f in categories[cat]['functions']:
		for n in f['names']:
			print >>out, '| ' + print_link(n + '()', symbols[n])
	for e in categories[cat]['enums']:
		print >>out, '| ' + print_link(e['name'], symbols[e['name']])
	print >>out, ''

print >>out, dump_link_targets()

out.write('''

.. raw:: html

	</div>

''')
out.close()

for cat in categories:
	out = open(categories[cat]['filename'], 'w+')

	classes = categories[cat]['classes']
	functions = categories[cat]['functions']
	enums = categories[cat]['enums']

	if 'overview' in categories[cat]:
		out.write('%s\n%s' % (heading(cat, '='), categories[cat]['overview']))

	for c in classes:

		print >>out, '.. raw:: html\n'
		print >>out, '\t<a name="%s"></a>' % c['name']
		print >>out, ''

		out.write('%s\n' % heading(c['name'], '-'))
		print_declared_in(out, c)
		out.write('%s\n\n.. parsed-literal::\n\t' % c['desc'])

		block = '\n%s\n{\n' % c['decl']
		for f in c['fun']:
			for s in f['signatures']:
				block += '   %s\n' % highlight_signature(s.replace('\n', '\n   '))

		if len(c['fun']) > 0 and len(c['enums']) > 0: block += '\n'

		first = True
		for e in c['enums']:
			if not first:
				block += '\n'
			first = False
			block += '   enum %s\n   {\n' % e['name']
			for v in e['values']:
				block += '      %s,\n' % v['name']
			block += '   };\n'

		if len(c['fun']) + len(c['enums']) > 0 and len(c['fields']): block += '\n'

		for f in c['fields']:
			for s in f['signatures']:
				block += '   %s\n' % s

		block += '};'

		print >>out, block.replace('\n', '\n\t') + '\n'

		for f in c['fun']:
			if f['desc'] == '': continue
			title = ''
			print >>out, '.. raw:: html\n'
			for n in f['names']:
				print >>out, '\t<a name="%s"></a>' % n
			print >>out, ''
			for n in f['names']:
				title += '%s() ' % n
			print >>out, heading(title.strip(), '.')

			block = '.. parsed-literal::\n\n'

			for s in f['signatures']:
				block += highlight_signature(s.replace('\n', '\n   ')) + '\n'
			print >>out, '%s\n' % block.replace('\n', '\n\t')
			print >>out, '%s' % f['desc']

		for e in c['enums']:
			if e['desc'] == '': continue
			print >>out, '.. raw:: html\n'
			print >>out, '\t<a name="%s"></a>' % e['name']
			print >>out, ''
			print >>out, heading('enum %s' % e['name'], '.')
			width = [len('value'), len('description')]
			for v in e['values']:
				width[0] = max(width[0], len(v['name']))
				for d in v['desc'].split('\n'):
					width[1] = max(width[1], len(d))

			print >>out, '+-' + ('-' * width[0]) + '-+-' + ('-' * width[1]) + '-+'
			print >>out, '| ' + 'value'.ljust(width[0]) + ' | ' + 'description'.ljust(width[1]) + ' |'
			print >>out, '+=' + ('=' * width[0]) + '=+=' + ('=' * width[1]) + '=+'
			for v in e['values']:
				d = v['desc'].split('\n')
				if len(d) == 0: d = ['']
				print >>out, '| ' + v['name'].ljust(width[0]) + ' | ' + d[0].ljust(width[1]) + ' |'
				for s in d[1:]:
					print >>out, '| ' + (' ' * width[0]) + ' | ' + s.ljust(width[1]) + ' |'
				print >>out, '+-' + ('-' * width[0]) + '-+-' + ('-' * width[1]) + '-+'
			print >>out, ''

		for f in c['fields']:
			if f['desc'] == '': continue

			print >>out, '.. raw:: html\n'
			for n in f['names']:
				print >>out, '\t<a name="%s"></a>' % n
			print >>out, ''

			for n in f['names']:
				print >>out, '%s ' % n,
			print >>out, ''
			print >>out, '\t%s' % f['desc'].replace('\n', '\n\t')


	for f in functions:
		h = ''
		print >>out, '.. raw:: html\n'
		for n in f['names']:
			print >>out, '\t<a name="%s"></a>' % n
		print >>out, ''
		for n in f['names']:
			h += '%s() ' % n
		print >>out, heading(h, '.')
		print_declared_in(out, f)

		block = '.. parsed-literal::\n\n'
		for s in f['signatures']:
			block += highlight_signature(s) + '\n'

		print >>out, '%s\n' % block.replace('\n', '\n\t')
		print >>out, f['desc']

	for e in enums:
		print >>out, '.. raw:: html\n'
		print >>out, '\t<a name="%s"></a>' % e['name']
		print >>out, ''

		print >>out, heading('enum %s' % e['name'], '.')
		print_declared_in(out, e)

		width = [len('value'), len('description')]
		for v in e['values']:
			width[0] = max(width[0], len(v['name']))
			for d in v['desc'].split('\n'):
				width[1] = max(width[1], len(d))

		print >>out, '+-' + ('-' * width[0]) + '-+-' + ('-' * width[1]) + '-+'
		print >>out, '| ' + 'value'.ljust(width[0]) + ' | ' + 'description'.ljust(width[1]) + ' |'
		print >>out, '+=' + ('=' * width[0]) + '=+=' + ('=' * width[1]) + '=+'
		for v in e['values']:
			d = v['desc'].split('\n')
			if len(d) == 0: d = ['']
			print >>out, '| ' + v['name'].ljust(width[0]) + ' | ' + d[0].ljust(width[1]) + ' |'
			for s in d[1:]:
				print >>out, '| ' + (' ' * width[0]) + ' | ' + s.ljust(width[1]) + ' |'
			print >>out, '+-' + ('-' * width[0]) + '-+-' + ('-' * width[1]) + '-+'
		print >>out, ''

	print >>out, dump_link_targets()

	out.close()

