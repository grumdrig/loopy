#!/usr/bin/env python3
# coding=utf-8

"""Usage: loo.py OPTS COMMAND [-- WATCH...]
       loo.py OPTS COMMAND [-- WATCH...] ++ OPTS COMMAND [-- WATCH...] ...
       loo.py --for NAME in FILE do OPTS COMMAND [-- WATCH...] ...
       loo.py [-L ARGS]
       loo.py -F LOOPFILE ARGS

Wait for changes to FILEs NAMEd on the command line, Run the COMMAND
whenever one of them changes. (However, filenames following a '>' in
the command are not watched. AND preceding a filename with @ keeps it
from being watched.)

Initial OPTS:
	-q        Print less info
	-v        Print more info
	-f        Faster polling for changes
	-F FNAME  Load the loopfile FNAME
	-L        Same as `-F Loopfile`
These options must come first, and apply to all command loops.

Per-command OPTS:
	-#        Run command through head -# (for some integer #)
	-w FNAME  Watch FNAME for changes
	-i FNAME  Ignore changes to FNAME even if appears in COMMAND or WATCH
	-I        Ignore all command line names not explicitly in WATCH
	-d        'Daemon' mode - start task in background and restart as needed
	-a        Always restart when command quits
	-x        Run command once on startup without waiting for changes
	--for...  Apply command to multiple parameters, explained below

WATCH: Files listed after -- or specified with -w are watched for changes
			 without being part of the command

Multiple command watch loops can be specified by separating them with ++.

Specifying a loopfile with -F causes the options and commands to be read
from lines in the loopfile. Each nonblank line is parsed as if they were
on the command line. Lines beginning with "#" are treated as comments.

Arguments after -F FNAME or -L are passed to the loopfile as $1, $2, etc.
These and other environment variables are substituted in the loopfile.

Running loo.py without any arguments causes it to look for the loopfile
named "Loopfile" in the current directory. The Loopfile contains command line
arguments that would otherwise be passed to loo.py.

Command loops can be duplicated for multiple files with `--for`. The
pattern is `--for VAR in ARG1 ARG2 ... do ...`. In the command, $VAR will
be replaced with each ARG in turn.

Hitting the enter key causes all commands to run (and/or daemons to be
restarted). Or hitting <task number> <enter> will trigger just that command.

EXAMPLES:
	loo.py gcc test.c
		Recompile test.c whenever it changes

	loo.py a.out
		Run a.out whenever it changes

	loo.py gcc test.c ++ a.out
		Do both

	loo.py make test -- *.c *.h
		Run make whenever a .c or .h file changes

	loo.py sed s/day/night/ \\< dayfile \\> nightfile
		Run sed whenever dayfile changes to produce nightfile. Note that
		the io redirection operators must be escaped. Also note that
		though nightfile is mentioned in the command, it's after a '>'
		and therefore not watched.

	loo.py swiftc -emit-library helper.swift ++ swiftc -lhelper program.swift -- libhelper.dylib ++ ./program
		Recompile the library "helper" when "helper.swift" changes. And:
		Recompile "program" when program.swift or the library changes. And:
		Run the program whenever it is regenerated.

	loo.py --for FILE in *.c do cc -o $FILE
		Compile any C file that changes
"""

import os, sys, time, itertools, signal, glob, subprocess


SLEEPTIME = 1
VERBOSITY = 0
TASKS = []

def main():
	global SLEEPTIME, VERBOSITY, TASKS
	args = sys.argv[1:]
	LOOPFILE = None
	if not args:
		LOOPFILE = "Loopfile"
	while args:
		if args[0] == "-F" and len(args) >= 2:
			args.pop(0)
			LOOPFILE = args.pop(0)
		elif args[0] == "-L":
			LOOPFILE = "Loopfile"
			args.pop(0)
		elif args[0] == '-q':
			args.pop(0)
			VERBOSITY -= 1
		elif args[0] == '-v':
			args.pop(0)
			VERBOSITY += 1
		elif args[0] == '-f':
			args.pop(0)
			SLEEPTIME /= 4
		else:
			break
	if LOOPFILE:
		TASKS = parseLoopfile(LOOPFILE, args)
	else:
		tasks = [list(g) for k,g in itertools.groupby(args, lambda x: x != '++') if k]
		TASKS = processTaskList(tasks)

	while True:
		for task in TASKS:
			task.checkForChanges()

		hit = enterKeyHasBeenHit()
		if hit:
			try:
				hit = int(hit)
				if 0 < hit and hit <= len(TASKS):
					TASKS[hit - 1].mtime = None
			except ValueError:
				for task in TASKS:
					task.mtime = None
		else:
			try:
				time.sleep(SLEEPTIME)
			except KeyboardInterrupt:
				killed = 0
				for task in TASKS:
					if task.pid:
						print("\nKilling", task.pid)
						os.kill(task.pid, signal.SIGTERM)
						task.pid = None
						killed += 1
				if killed:
					print("^C again to quit")
					try:
						time.sleep(1)
					except KeyboardInterrupt:
						print
						sys.exit(0)
				else:
					sys.exit(0)


def expandEnvironmentVars(s):
	# Let bash expand environment vars, which allows stuff like "${var%.newext}.newext"
	subprocess.check_output(["bash","-c","echo \"{}\"".format(a)]).strip()


def processTaskList(tasks):
	"""Turn text task lists into Task objects"""
	# expand --for loops
	for i in range(len(tasks)-1, -1, -1):
		task = tasks[i]
		if task and (task[0] == "--for"):
			try:
				variable = task[1]
				if task[2] != 'in':
					usage()
				ido = task.index('do')
				values, task = task[3:ido], task[ido+1:]
				if LOOPFILE:
					values = [found for value in values for found in (glob.glob(value) if value != "$*" else args)]
				def repl(a, variable, value):
					os.environ[variable] = value
					return expandEnvironmentVars(a)
				subtasks = map(lambda value: map(lambda a: repl(a, variable, value), task), values)
				tasks[i:i+1] = subtasks

			except IndexError:
				usage()

	for i in range(len(tasks)):
		tasks[i] = Task(tasks[i], "[%d] " % (i + 1) if len(tasks) > 1 else "")

	return tasks


class Task:
	def __init__(self, args, index):
		IGNORE = set()
		WATCH = set()
		AUTOWATCH = True
		WAIT = True
		self.HEAD = ''
		self.BACKGROUND = False
		self.ALWAYS = False
		self.index = index

		while args and args[0].startswith('-'):
			opt = args.pop(0)
			if not args:
				usage()
			if opt == '-w':
				WATCH.add(args.pop(0))
			elif opt == '-i':
				IGNORE.add(args.pop(0))
			elif opt == '-I':
				AUTOWATCH = False
			elif opt == '-d':
				self.BACKGROUND = True
			elif opt == '-a':
				self.ALWAYS = True
			elif opt == '-x':
				WAIT = False
			else:
				self.HEAD = ' 2>&1 | head ' + opt

		for i in range(len(args)):
			if args[i][:1] == '@':
				args[i] = args[i][1:]
				IGNORE.add(args[i])

		if not args:
			usage()

		# Split args into [COMMAND, WATCH]
		cfi = [list(g) for k,g in itertools.groupby(args, lambda x: x != '--') if k]

		self.command = cfi.pop(0)
		filenames = [a for a,b in zip(self.command, [0] + self.command[:-1]) if b != '>']
		filenames = set([f for f in filenames if os.path.exists(f) and AUTOWATCH])
		filenames |= set(cfi and cfi.pop(0))
		filenames |= WATCH
		filenames -= IGNORE
		self.filenames = filenames

		if not self.BACKGROUND:
			self.command = ' '.join(self.command)

		self.pid = None
		self.mtime = None
		if WAIT and not self.BACKGROUND:
			self.mtime = [os.stat(filename).st_mtime for filename in self.filenames
										if os.path.exists(filename)]
		if VERBOSITY >= 0:
			print(self.index + 'Looping:', self.command, '--', ' '.join(self.filenames))


	def checkForChanges(self):
		m = [os.stat(filename).st_mtime for filename in self.filenames
				 if os.path.exists(filename)]
		if self.ALWAYS:
			m = None

		if not self.BACKGROUND:

			if self.mtime != m:
				if VERBOSITY >= 0:
					print("―" * 78)
					print(self.index + 'Running:', self.command)
				os.system(self.command + self.HEAD)
				self.mtime = m
				if VERBOSITY - (1 if self.ALWAYS else 0) >= 0:
					print("―" * 78)
					print(self.index + 'Watching:', ', '.join(self.filenames))
		else:

			if self.mtime != m:
				self.pid = restart(self.pid, self.command)
				self.mtime = m
			else:
				try:
					os.kill(self.pid, 0)  # look for the running process
				except:
					self.pid = restart(self.pid, self.command)


class LoopfileTask:
	def __init__(self, loopfile, args):
		self.loopfile = loopfile
		self.args = args
		self.mtime = os.stat(loopfile).st_mtime

	def checkForChanges(self):
		global TASKS
		if self.mtime != os.stat(self.loopfile).st_mtime:
			if VERBOSITY >= 0:
				print('Reloading loopfile:', self.loopfile)
			TASKS = parseLoopfile(self.loopfile, self.args)


def usage():
		print(__doc__)
		sys.exit()


def enterKeyHasBeenHit():
	import select
	i,o,e = select.select([sys.stdin],[],[],0.0001)
	for s in i:
		if s == sys.stdin:
			return sys.stdin.readline()
	return False


def restart(pid, command):
	if pid:
		print("Killing pid", pid)
		os.kill(pid, signal.SIGTERM)
	pid = os.spawnlp(os.P_NOWAIT, command[0], *command)
	print("Started pid", pid)
	return pid


def parseLoopfile(loopfile, args):
	if not os.path.exists(loopfile):
		usage()
	os.environ["#"] = str(len(args))
	for i,a in enumerate(args):
		os.environ[str(i+1)] = a
	# perhaps I'll want to change this call to expandEvironmentVars if need better handling of command line args
	tasks = [os.path.expandvars(line).split() for line in open(loopfile, "rt").readlines() if line.strip() and line[0] != "#"]

	tasks = processTaskList(tasks)

	# also watch for changes to the loopfile itself
	tasks.append(LoopfileTask(loopfile, args))

	return tasks



if __name__ == '__main__':
	main()
